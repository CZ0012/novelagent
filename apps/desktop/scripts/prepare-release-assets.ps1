$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktopDir = Split-Path -Parent $scriptDir
$repoRoot = Resolve-Path (Join-Path $desktopDir "..\..")
$version = (Get-Content -LiteralPath (Join-Path $repoRoot "VERSION") -Raw).Trim()
$bundleDir = Join-Path $desktopDir "src-tauri\target\release\bundle\nsis"
$setupName = "StoryGraph Agent_${version}_x64-setup.exe"
$setupPath = Join-Path $bundleDir $setupName
$signaturePath = "$setupPath.sig"
$releaseAssetName = "StoryGraph.Agent_${version}_x64-setup.exe"
$releaseAssetPath = Join-Path $bundleDir $releaseAssetName
$releaseSignaturePath = "$releaseAssetPath.sig"

if (!(Test-Path -LiteralPath $setupPath)) {
    throw "Installer not found: $setupPath"
}

if (!(Test-Path -LiteralPath $signaturePath)) {
    throw "Updater signature not found: $signaturePath"
}

Copy-Item -LiteralPath $setupPath -Destination $releaseAssetPath -Force
Copy-Item -LiteralPath $signaturePath -Destination $releaseSignaturePath -Force

$releaseNotes = $env:STORYGRAPH_RELEASE_NOTES
if (-not $releaseNotes) {
    $releaseNotes = "StoryGraph Agent v$version desktop update."
}

$latest = [ordered]@{
    version = $version
    notes = $releaseNotes
    pub_date = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    platforms = [ordered]@{
        "windows-x86_64" = [ordered]@{
            signature = (Get-Content -LiteralPath $signaturePath -Raw).Trim()
            url = "https://github.com/CZ0012/novelagent/releases/download/v$version/$releaseAssetName"
        }
    }
}

$latestPath = Join-Path $bundleDir "latest.json"
$latest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $latestPath -Encoding utf8

Write-Host "Release assets ready:"
Write-Host "  $releaseAssetPath"
Write-Host "  $releaseSignaturePath"
Write-Host "  $latestPath"
