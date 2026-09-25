# Windows update recovery / Windows 更新恢复

## What happened

An interrupted update can leave the desktop interface and bundled backend at different versions. The affected installer copied the main executable before the backend, while only checking that the main application had exited. If the backend executable remained locked, installation could stop before replacing it or updating the Windows installation record. The old interface's update check compared only the desktop version, so it could then report “latest” despite an older backend.

The confirmed incident had a v0.1.12 desktop with a running v0.1.10 backend and v0.1.10 installation record. Backend preset/model-list routes were absent. After the author saved and exited, reinstalling the verified v0.1.12 package in the same directory restored the matching backend, routes, and installation record. The author workspace was not replaced.

## Recover an affected installation

1. Save edited drafts and proposals.
2. Use **Quit** in the StoryGraph system-tray menu. Closing the window only hides it.
3. Download the [latest Windows installer](https://github.com/CZ0012/novelagent/releases/latest) and install it into the existing StoryGraph installation directory. Uninstalling first or deleting a workspace is unnecessary.
4. Reopen the application and inspect both desktop and backend versions in **Settings → Version & Updates**. A mismatched or unverified backend requires attention even if the desktop version is current.

Do not dismiss a backend file-write error as a successful update. An access failure can also come from folder permissions or another process holding the executable; the repair release stops before copying application files if that preflight fails.

## v0.1.13 safeguards

- Download the signed package before stopping the backend. Protect unsaved text before proceeding to installation.
- `prepare_backend_update` holds an update gate, stops only the managed process tree, preserves failure information, and checks replacement access. A failed preparation prevents installation. `cancel_backend_update` releases the gate for recovery; it does not start a backend itself.
- The NSIS `NSIS_HOOK_PREINSTALL` repeats checks before copying any application binary. It can clean up a leftover backend only when the process executable matches the exact backend path in this installation. It never terminates every process by image name. This guard also works when an older updater starts the new installer.
- The preflight uses Windows PowerShell 5.1 and a bounded timeout. Locked or unwritable files abort the install before the main executable is replaced. This covers the identified file-lock failure, not power-loss or arbitrary storage-failure atomicity.
- `/health.version` reports the running backend application's version. The interface falls back to OpenAPI `info.version` for older backends and reports unknown versions explicitly. Comparing the desktop version alone cannot certify a complete installation.

These operations concern installed software only. They do not write graph canon, import manuscripts, change Agent settings, or synchronize novel workspaces. Tauri update signatures and Windows Authenticode signatures remain separate.

The hook boundary follows [Tauri's Windows installer documentation](https://v2.tauri.app/distribute/windows-installer/#nsis-installer-hooks). Runtime behavior was also checked against the project's pinned updater implementation and generated NSIS script.

## Verification

| Check | Result |
| --- | --- |
| Desktop API and version-manifest regressions | 7 passed |
| Web regressions | 55 passed |
| Native lifecycle/localization regressions | 8 passed |
| Real NSIS hook: unlocked replacement | Both fixture binaries replaced |
| Real NSIS hook: backend write lock | Exit 2; both old fixture binaries unchanged |
| Real NSIS hook: running target backend | Exact target stopped; same-named process in another folder remained alive; spaced install path worked |
| Real NSIS hook: missing backend | Both fixture binaries installed successfully |
| Production browser, Chinese and English | Legacy OpenAPI v0.1.10 clearly reported as mismatched with interface v0.1.13 |
| Production browser, matching/unknown versions | Health v0.1.13 clears mismatch; missing health/OpenAPI versions remain explicitly unconfirmed |
| Windows installer build | v0.1.13 executable, updater signature, and latest.json produced |

The browser used an isolated local version-metadata fixture, without author projects or provider calls. Installer fixtures use temporary directories and do not write the product's Windows installation record.

The reusable Windows PowerShell 5.1 regression command is `npm --prefix apps/desktop run test:update-guard`. Run `build:installer` first: the test uses the generated production NSIS utilities, cached NSIS compiler, and `rustc`. Each run creates a unique ignored fixture directory under `.storygraph/update-repair/`; it checks production hook ordering as well as executing the lock, scope, and replacement cases.

The v0.1.13 installer signature was independently verified against the configured public key; a tampered copy was rejected. Installer SHA256: `3b3ad297b9a7e3372312050d2a475edddc6d3cf4552f1869f7d0bd05d5cac960`. The existing installation was repaired with this package: desktop version and Windows installation record both read v0.1.13, the installed backend matched the bundled binary, and every file in the original author workspace retained its previous hash.

Publication verified on 2026-09-13: [v0.1.13](https://github.com/CZ0012/novelagent/releases/tag/v0.1.13) is the latest public release at software commit `78c36f7`. All three downloaded release assets match the verified local files. The installed backend was also started in an isolated workspace and reported v0.1.13 with all built-in presets available; the test process tree was stopped afterward.

## 中文说明

此前的安装器先覆盖桌面主程序，再覆盖后端。后端仍被占用时，安装可能中断，出现“界面版本已更新、后端还是旧版”的情况。旧版“已是最新版”只核对界面版本，不能代表整个应用更新成功。

修复时应先保存内容、从托盘退出，再将最新安装器安装到原目录；无需删除小说工作区。v0.1.13 在覆盖文件前检查并释放本安装目录的后端，失败就中止；界面也分别核对桌面与后端版本。安装记录、文件版本和实际运行接口应保持一致。

## v0.1.15 preparation sharing-lock fix

A later incident left both installed components at 0.1.13 and reported Windows `os error 32` from `prepare_backend_update`. The installer had not started: the Web recovery path restored the managed backend. Unlike the installer guard, the new 0.1.13 native preflight tried exclusive access only once immediately after shutdown. A temporary file lock could therefore reject a safe update.

The native check now waits up to 10 seconds, retrying only Windows sharing/lock violations 32/33 without terminating unrelated processes. Missing files, access denial and other errors remain immediate failures; a lasting sharing lock still blocks replacement. The wait uses a blocking worker, keeping the window responsive. Errors show their actual stage and the separate recovery result.

The old client cannot receive this fix until installed. For this one-time recovery, save edits, quit from the system tray, then install the latest signed package into the existing installation directory. The installer already has its own bounded guard. Do not uninstall or remove the novel workspace.

Verification includes a real read-sharing handle released after 120ms, persistent-lock and permanent-error cases, plus repeated real PyInstaller one-file parent/child shutdown using `test:update-lifecycle`. One early ten-run fixture observed an immediate probe failure that subsequently cleared; it did not record the error code, so it cannot identify the exact process responsible for the author's incident. The final instrumented 35-run fixture passed every readiness check and preserved executable bytes. Diagnostics did not stop the author's application.
