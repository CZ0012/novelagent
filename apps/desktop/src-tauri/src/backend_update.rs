use crate::localization::native_message;
use std::{
    fs::OpenOptions,
    io,
    path::Path,
    process::Child,
    thread,
    time::{Duration, Instant},
};

#[cfg(windows)]
use std::{
    os::windows::{fs::OpenOptionsExt, process::CommandExt},
    process::{Command, Stdio},
};

/// Probe replacement permissions without truncating or changing the executable.
/// The installer repeats this check immediately before copying either binary.
pub fn check_replacement_ready(path: &Path) -> Result<(), String> {
    wait_for_replacement_ready(path, Duration::from_secs(10), Duration::from_millis(100))
}

fn probe_replacement_ready(path: &Path) -> io::Result<()> {
    let mut options = OpenOptions::new();
    options.read(true).write(true);
    #[cfg(windows)]
    options.share_mode(0);
    options.open(path).map(|_| ())
}

fn is_transient_file_lock(error: &io::Error) -> bool {
    #[cfg(windows)]
    return matches!(error.raw_os_error(), Some(32 | 33));
    #[cfg(not(windows))]
    {
        let _ = error;
        false
    }
}

fn wait_for_replacement_ready(
    path: &Path,
    timeout: Duration,
    interval: Duration,
) -> Result<(), String> {
    let deadline = Instant::now() + timeout;
    loop {
        let error = match probe_replacement_ready(path) {
            Ok(()) => return Ok(()),
            Err(error) => error,
        };
        // Windows can keep a terminated one-file executable mapped briefly after
        // taskkill and the retained parent handle report exit. External readers
        // may also hold short-lived locks. Wait without killing another process.
        if is_transient_file_lock(&error) && Instant::now() < deadline {
            thread::sleep(interval.min(deadline.saturating_duration_since(Instant::now())));
            continue;
        }
        return Err(native_message(
            "backend_update_locked",
            &[
                ("path", &path.to_string_lossy()),
                ("error", &error.to_string()),
            ],
        ));
    }
}

/// Stop only the process whose retained Child handle we own and its descendants.
/// Keep the caller's handle on failure so a later explicit stop can retry.
pub fn kill_child_tree(child: &mut Child) -> Result<(), String> {
    if child
        .try_wait()
        .map_err(|error| native_message("stop_backend", &[("error", &error.to_string())]))?
        .is_some()
    {
        return Ok(());
    }

    let deadline = Instant::now() + Duration::from_secs(5);

    #[cfg(windows)]
    {
        let mut stopper = Command::new("taskkill.exe")
            .args(["/PID", &child.id().to_string(), "/T", "/F"])
            .creation_flags(0x08000000)
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|error| native_message("stop_backend", &[("error", &error.to_string())]))?;
        let status = loop {
            match stopper.try_wait() {
                Ok(Some(status)) => break status,
                Ok(None) if Instant::now() < deadline => {
                    thread::sleep(Duration::from_millis(50));
                }
                result => {
                    // Bound the helper as well as the backend. Retain the backend
                    // handle so the UI can report the failure and explicitly retry.
                    let _ = stopper.kill();
                    return Err(match result {
                        Err(error) => {
                            native_message("stop_backend", &[("error", &error.to_string())])
                        }
                        _ => native_message("stop_backend_timeout", &[]),
                    });
                }
            }
        };
        if !status.success() {
            return Err(native_message("stop_backend_tree", &[]));
        }
    }
    #[cfg(not(windows))]
    child
        .kill()
        .map_err(|error| native_message("stop_backend", &[("error", &error.to_string())]))?;

    loop {
        if child
            .try_wait()
            .map_err(|error| native_message("stop_backend", &[("error", &error.to_string())]))?
            .is_some()
        {
            return Ok(());
        }
        if Instant::now() >= deadline {
            return Err(native_message("stop_backend_timeout", &[]));
        }
        thread::sleep(Duration::from_millis(50));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[cfg(windows)]
    #[test]
    fn replacement_probe_rejects_a_running_executable() {
        let started = Instant::now();
        assert!(wait_for_replacement_ready(
            &std::env::current_exe().unwrap(),
            Duration::from_millis(80),
            Duration::from_millis(10),
        )
        .is_err());
        assert!(started.elapsed() < Duration::from_secs(2));
    }

    #[cfg(windows)]
    #[test]
    fn replacement_wait_accepts_a_released_lock_without_changing_bytes() {
        let directory = Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../../.storygraph/update-repair/native-tests");
        std::fs::create_dir_all(&directory).unwrap();
        let path = directory.join(format!("transient-{}.exe", std::process::id()));
        std::fs::write(&path, b"original executable bytes").unwrap();
        let reader = OpenOptions::new()
            .read(true)
            .share_mode(1)
            .open(&path)
            .unwrap();
        assert!(probe_replacement_ready(&path).is_err());
        let release = thread::spawn(move || {
            thread::sleep(Duration::from_millis(120));
            drop(reader);
        });
        let result =
            wait_for_replacement_ready(&path, Duration::from_secs(2), Duration::from_millis(20));
        release.join().unwrap();
        assert!(result.is_ok(), "{result:?}");
        assert_eq!(std::fs::read(&path).unwrap(), b"original executable bytes");
        std::fs::remove_file(&path).unwrap();
    }

    #[cfg(windows)]
    #[test]
    fn replacement_wait_times_out_on_a_persistent_sharing_lock_without_changing_bytes() {
        let directory = Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../../.storygraph/update-repair/native-tests");
        std::fs::create_dir_all(&directory).unwrap();
        let path = directory.join(format!("persistent-{}.exe", std::process::id()));
        let original = b"original executable remains locked";
        std::fs::write(&path, original).unwrap();
        let reader = OpenOptions::new()
            .read(true)
            .share_mode(1)
            .open(&path)
            .unwrap();
        assert_eq!(
            probe_replacement_ready(&path).unwrap_err().raw_os_error(),
            Some(32)
        );
        let started = Instant::now();
        let result =
            wait_for_replacement_ready(&path, Duration::from_millis(80), Duration::from_millis(10));
        let elapsed = started.elapsed();
        assert!(result.is_err());
        assert!(elapsed >= Duration::from_millis(80), "{elapsed:?}");
        assert!(elapsed < Duration::from_secs(2), "{elapsed:?}");
        assert_eq!(
            probe_replacement_ready(&path).unwrap_err().raw_os_error(),
            Some(32)
        );
        drop(reader);
        assert_eq!(std::fs::read(&path).unwrap(), original);
        std::fs::remove_file(&path).unwrap();
    }

    #[cfg(windows)]
    #[test]
    fn only_sharing_and_lock_violations_are_retryable() {
        assert!(is_transient_file_lock(&io::Error::from_raw_os_error(32)));
        assert!(is_transient_file_lock(&io::Error::from_raw_os_error(33)));
        assert!(!is_transient_file_lock(&io::Error::from_raw_os_error(5)));
        assert!(!is_transient_file_lock(&io::Error::from_raw_os_error(2)));
    }

    #[test]
    fn replacement_probe_never_creates_missing_files() {
        let path = Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../../.storygraph/update-repair/missing-executable.exe");
        assert!(!path.exists());
        let started = Instant::now();
        assert!(check_replacement_ready(&path).is_err());
        assert!(started.elapsed() < Duration::from_secs(2));
        assert!(!path.exists());
    }

    #[test]
    fn replacement_probe_preserves_existing_contents() {
        let directory = Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../../.storygraph/update-repair/native-tests");
        std::fs::create_dir_all(&directory).unwrap();
        let path = directory.join(format!("probe-{}.exe", std::process::id()));
        std::fs::write(&path, b"existing backend bytes").unwrap();
        let result = check_replacement_ready(&path);
        let bytes = std::fs::read(&path).unwrap();
        std::fs::remove_file(path).unwrap();
        assert!(result.is_ok());
        assert_eq!(bytes, b"existing backend bytes");
    }

    #[cfg(windows)]
    #[test]
    fn managed_process_stop_waits_for_exit_and_is_idempotent() {
        let mut child = Command::new("powershell.exe")
            .args([
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Start-Sleep -Seconds 30",
            ])
            .creation_flags(0x08000000)
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .unwrap();
        let stopped = kill_child_tree(&mut child);
        if stopped.is_err() {
            let _ = child.kill();
            let _ = child.wait();
        }
        assert!(stopped.is_ok(), "{stopped:?}");
        assert!(child.try_wait().unwrap().is_some());
        assert!(kill_child_tree(&mut child).is_ok());
    }
}
