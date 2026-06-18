$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktopDir = Split-Path -Parent $scriptDir
$webDir = Resolve-Path (Join-Path $desktopDir "..\web")
$localSigningKey = Join-Path $desktopDir ".tauri\storygraph-agent.key"

if (-not $env:TAURI_SIGNING_PRIVATE_KEY -and -not $env:TAURI_SIGNING_PRIVATE_KEY_PATH) {
    if (!(Test-Path -LiteralPath $localSigningKey)) {
        throw "Updater signing key not found at $localSigningKey. Generate it with: npm --prefix apps/desktop run tauri signer generate -- --ci --write-keys .tauri/storygraph-agent.key"
    }
    $env:TAURI_SIGNING_PRIVATE_KEY_PATH = $localSigningKey
}

if (-not $env:TAURI_SIGNING_PRIVATE_KEY -and $env:TAURI_SIGNING_PRIVATE_KEY_PATH) {
    if (!(Test-Path -LiteralPath $env:TAURI_SIGNING_PRIVATE_KEY_PATH)) {
        throw "Updater signing key path does not exist: $env:TAURI_SIGNING_PRIVATE_KEY_PATH"
    }
    $env:TAURI_SIGNING_PRIVATE_KEY = Get-Content -LiteralPath $env:TAURI_SIGNING_PRIVATE_KEY_PATH -Raw
}

if (-not $env:CI) {
    $env:CI = "true"
}

npm --prefix $webDir run build
if ($LASTEXITCODE -ne 0) {
    throw "Web build failed."
}

& (Join-Path $scriptDir "build-backend-sidecar.ps1")
if ($LASTEXITCODE -ne 0) {
    throw "Backend sidecar build failed."
}

Push-Location $desktopDir
try {
    npm run tauri build
    if ($LASTEXITCODE -ne 0) {
        throw "Tauri installer build failed."
    }
} finally {
    Pop-Location
}
