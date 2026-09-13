use crate::localization::native_message;
use std::{
    fs::OpenOptions,
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
    let mut options = OpenOptions::new();
    options.read(true).write(true);
    #[cfg(windows)]
    options.share_mode(0);
    options.open(path).map(|_| ()).map_err(|error| {
        native_message(
            "backend_update_locked",
            &[
                ("path", &path.to_string_lossy()),
                ("error", &error.to_string()),
            ],
        )
    })
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
        assert!(check_replacement_ready(&std::env::current_exe().unwrap()).is_err());
    }

    #[test]
    fn replacement_probe_never_creates_missing_files() {
        let path = Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../../.storygraph/update-repair/missing-executable.exe");
        assert!(!path.exists());
        assert!(check_replacement_ready(&path).is_err());
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
