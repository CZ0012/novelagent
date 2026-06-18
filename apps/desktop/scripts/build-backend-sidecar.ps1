$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktopDir = Split-Path -Parent $scriptDir
$repoRoot = Resolve-Path (Join-Path $desktopDir "..\..")
$sidecarDir = Join-Path $desktopDir "src-tauri\binaries"
$workDir = Join-Path $desktopDir ".backend-build"
$runDir = Join-Path $workDir ("run-" + [Guid]::NewGuid().ToString("N"))
$entryPath = Join-Path $runDir "desktop_backend_entry.py"
$distDir = Join-Path $runDir "dist"
$exePath = Join-Path $distDir "storygraph-backend.exe"
$targetPath = Join-Path $sidecarDir "storygraph-backend-x86_64-pc-windows-msvc.exe"

New-Item -ItemType Directory -Force -Path $sidecarDir | Out-Null
New-Item -ItemType Directory -Force -Path $workDir | Out-Null
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

@'
import uvicorn

from apps.api.desktop import app

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
'@ | Set-Content -LiteralPath $entryPath -Encoding utf8

python -m PyInstaller --version | Out-Null
if ($LASTEXITCODE -ne 0) {
    python -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install PyInstaller. Install it manually or adjust the desktop backend sidecar build."
    }
}

python -m PyInstaller --clean --noconfirm --onefile --name storygraph-backend --distpath $distDir --workpath (Join-Path $runDir "build") --specpath $runDir --paths $repoRoot $entryPath
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed to build the StoryGraph backend sidecar."
}

if (!(Test-Path -LiteralPath $exePath)) {
    throw "PyInstaller did not produce $exePath"
}

$targetFullPath = [System.IO.Path]::GetFullPath($targetPath)
Get-Process | Where-Object {
    try {
        $_.Path -and ([System.IO.Path]::GetFullPath($_.Path) -eq $targetFullPath)
    } catch {
        $false
    }
} | Stop-Process -Force

$copied = $false
for ($attempt = 1; $attempt -le 10; $attempt++) {
    try {
        Copy-Item -LiteralPath $exePath -Destination $targetPath -Force
        $copied = $true
        break
    } catch {
        if ($attempt -eq 10) {
            throw
        }
        Start-Sleep -Milliseconds 500
    }
}

if (-not $copied) {
    throw "Failed to copy backend sidecar to $targetPath"
}

Write-Host "Backend sidecar ready: $targetPath"
