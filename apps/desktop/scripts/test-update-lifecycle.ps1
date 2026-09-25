# Windows PowerShell 5.1 or PowerShell on Windows. No installed app or story data is used.
# Requires the same pinned PyInstaller and Rust used by the desktop build.
param([ValidateRange(1, 100)][int]$Iterations = 10)
$ErrorActionPreference = 'Stop'
$desktopDir = Split-Path -Parent $PSScriptRoot
$repoDir = [IO.Path]::GetFullPath((Join-Path $desktopDir '..\..'))
$fixtureRoot = [IO.Path]::GetFullPath((Join-Path $repoDir '.storygraph\update-repair'))
$runDir = [IO.Path]::GetFullPath((Join-Path $fixtureRoot ('lifecycle-' + [guid]::NewGuid().ToString('N'))))
if (-not $runDir.StartsWith($fixtureRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Fixture escaped the repository test directory.'
}
[IO.Directory]::CreateDirectory($runDir) | Out-Null
$python = (Get-Command python -ErrorAction Stop).Source
$rustc = (Get-Command rustc -ErrorAction Stop).Source
$pyInstallerVersion = & $python -m PyInstaller --version
if ($LASTEXITCODE -ne 0 -or $pyInstallerVersion.Trim() -ne '6.21.0') {
    throw 'Install PyInstaller 6.21.0, matching build-backend-sidecar.ps1, before this check.'
}
$entry = Join-Path $runDir 'fixture.py'
@'
import os
import sys
import time
from pathlib import Path
# A real one-file bootloader starts a second process. There is no network or API.
marker = Path(sys.argv[1])
temporary = marker.with_suffix(".tmp")
temporary.write_text(f"{os.getpid()} {os.getppid()}", encoding="utf-8")
temporary.replace(marker)
time.sleep(120)
'@ | Set-Content -LiteralPath $entry -Encoding utf8
$dist = Join-Path $runDir 'dist'
& $python -m PyInstaller --noconfirm --onefile --noconsole --name update-lifecycle-fixture --distpath $dist --workpath (Join-Path $runDir 'build') --specpath $runDir $entry
if ($LASTEXITCODE -ne 0) { throw 'Could not build the one-file lifecycle fixture.' }
$fixtureExe = [IO.Path]::GetFullPath((Join-Path $dist 'update-lifecycle-fixture.exe'))
$harnessPath = Join-Path $runDir 'lifecycle.rs'
$harnessExe = Join-Path $runDir 'lifecycle.exe'
$source = @'
mod localization {
    pub fn native_message(key: &str, values: &[(&str, &str)]) -> String {
        format!("{key} {values:?}")
    }
}
#[path = r"@@MODULE@@"]
mod backend_update;
use std::{fs, path::PathBuf, process::{Command, Stdio}, thread, time::{Duration, Instant}};
use std::os::windows::{fs::OpenOptionsExt, process::CommandExt};
fn main() {
    let args: Vec<String> = std::env::args().collect();
    let executable = PathBuf::from(&args[1]);
    let run_dir = PathBuf::from(&args[2]);
    let iterations: usize = args[3].parse().unwrap();
    let original = fs::read(&executable).unwrap();
    let mut immediate_locks = 0;
    let mut immediate_error_codes = Vec::new();
    let mut longest_wait_ms = 0;
    for index in 0..iterations {
        let ready = run_dir.join(format!("ready-{index}.txt"));
        let mut child = Command::new(&executable).arg(&ready)
            .creation_flags(0x08000000).stdout(Stdio::null()).stderr(Stdio::null())
            .spawn().unwrap();
        let startup = Instant::now();
        while !ready.exists() && startup.elapsed() < Duration::from_secs(15) {
            thread::sleep(Duration::from_millis(10));
        }
        if !ready.exists() {
            let _ = backend_update::kill_child_tree(&mut child);
            panic!("The isolated one-file child did not start");
        }
        let ids = fs::read_to_string(&ready).unwrap().split_whitespace()
            .map(|part| part.parse::<u32>().unwrap()).collect::<Vec<_>>();
        assert_eq!(ids.len(), 2);
        assert_ne!(ids[0], child.id(), "Expected a real PyInstaller worker");
        assert_eq!(ids[1], child.id(), "Expected the retained bootloader parent");
        let stop_result = backend_update::kill_child_tree(&mut child);
        assert!(stop_result.is_ok(), "Stop failed: {stop_result:?}. Check local process permissions.");
        assert!(child.try_wait().unwrap().is_some());
        drop(child);
        if let Err(error) = fs::OpenOptions::new().read(true).write(true).share_mode(0).open(&executable) {
            immediate_locks += 1;
            immediate_error_codes.push(error.raw_os_error().unwrap_or(-1));
        }
        let wait_start = Instant::now();
        let ready_result = backend_update::check_replacement_ready(&executable);
        longest_wait_ms = longest_wait_ms.max(wait_start.elapsed().as_millis());
        assert!(ready_result.is_ok(), "Replacement check failed: {ready_result:?}");
    }
    assert_eq!(fs::read(&executable).unwrap(), original, "Probe changed executable bytes");
    let result = format!("{{\"iterations\":{iterations},\"immediate_locks\":{immediate_locks},\"immediate_error_codes\":{immediate_error_codes:?},\"longest_wait_ms\":{longest_wait_ms},\"all_replacement_checks_passed\":true,\"executable_unchanged\":true}}");
    fs::write(run_dir.join("results.json"), &result).unwrap();
    println!("{result}");
}
'@
$module = Join-Path $desktopDir 'src-tauri\src\backend_update.rs'
$source.Replace('@@MODULE@@', $module) | Set-Content -LiteralPath $harnessPath -Encoding utf8
& $rustc --edition=2021 $harnessPath -o $harnessExe
if ($LASTEXITCODE -ne 0) { throw 'Could not compile the native lifecycle harness.' }
try {
    & $harnessExe $fixtureExe $runDir $Iterations
    if ($LASTEXITCODE -ne 0) { throw 'Native one-file lifecycle regression failed.' }
} finally {
    # On fixture failure, clean only this unique run's exact executable path.
    foreach ($candidate in [Diagnostics.Process]::GetProcessesByName('update-lifecycle-fixture')) {
        try {
            if ([string]::Equals($candidate.MainModule.FileName, $fixtureExe, [StringComparison]::OrdinalIgnoreCase)) {
                $candidate.Kill()
                [void]$candidate.WaitForExit(3000)
            }
        } catch { } finally { $candidate.Dispose() }
    }
}
Write-Host ('Isolated lifecycle results: ' + (Join-Path $runDir 'results.json'))
