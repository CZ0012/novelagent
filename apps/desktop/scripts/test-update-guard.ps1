# Windows PowerShell 5.1 or PowerShell on Windows. Run after build:installer.
# Builds an isolated installer using the real hook and Tauri process-check macro.
# No installed application, registry, signing key, or novel workspace is modified.
param(
    [string]$NsisRoot = (Join-Path $env:LOCALAPPDATA 'tauri\NSIS')
)

$ErrorActionPreference = 'Stop'
$desktopDir = Split-Path -Parent $PSScriptRoot
$repoDir = [IO.Path]::GetFullPath((Join-Path $desktopDir '..\..'))
$generatedDir = Join-Path $desktopDir 'src-tauri\target\release\nsis\x64'
$hookPath = Join-Path $desktopDir 'src-tauri\installer\hooks.nsh'
$utilsPath = Join-Path $generatedDir 'utils.nsh'
$makeNsis = Join-Path $NsisRoot 'makensis.exe'
$pluginDir = Join-Path $NsisRoot 'Plugins\x86-unicode\additional'
foreach ($required in @($makeNsis, $utilsPath, $hookPath, (Join-Path $pluginDir 'nsis_tauri_utils.dll'))) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Missing $required. Run npm --prefix apps/desktop run build:installer first."
    }
}
$rustc = (Get-Command rustc -ErrorAction Stop).Source

# Check the rendered production installer, not only our fixture's intended order.
$productionScript = [IO.File]::ReadAllText((Join-Path $generatedDir 'installer.nsi'))
$version = [IO.File]::ReadAllText((Join-Path $repoDir 'VERSION')).Trim()
if ($productionScript -notmatch ('(?m)^!define VERSION "' + [regex]::Escape($version) + '"\s*$')) {
    throw 'Generated installer is stale. Run build:installer before this regression check.'
}
$hookInclude = [regex]::Match($productionScript, '(?m)^!include "([^"\r\n]*hooks\.nsh)"\s*$')
if (-not $hookInclude.Success -or [IO.Path]::GetFullPath($hookInclude.Groups[1].Value) -ne $hookPath) {
    throw 'Generated installer does not include the production update guard.'
}
$section = [regex]::Match($productionScript, '(?ms)^Section Install\s*\r?\n(.*?)^SectionEnd')
$guardIndex = $section.Groups[1].Value.IndexOf('!insertmacro NSIS_HOOK_PREINSTALL')
$firstWrite = [regex]::Match($section.Groups[1].Value, '(?m)^\s*(File|WriteUninstaller|WriteReg\w*)\s')
if (-not $section.Success -or $guardIndex -lt 0 -or -not $firstWrite.Success -or $guardIndex -ge $firstWrite.Index) {
    throw 'Production pre-install guard must run before application file or version writes.'
}

$fixtureRoot = [IO.Path]::GetFullPath((Join-Path $repoDir '.storygraph\update-repair'))
$runId = [guid]::NewGuid().ToString('N')
$runDir = [IO.Path]::GetFullPath((Join-Path $fixtureRoot ('guard-' + $runId)))
if (-not $runDir.StartsWith($fixtureRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Fixture escaped the repository test directory.'
}
[IO.Directory]::CreateDirectory($runDir) | Out-Null
$mainName = 'storygraph-guard-main-' + $runId
$installerPath = Join-Path $runDir 'fixture-installer.exe'
$stubPath = Join-Path $runDir 'backend-fixture.exe'
$mainPayload = Join-Path $runDir 'new-main.txt'
$backendPayload = Join-Path $runDir 'new-backend.txt'
[IO.File]::WriteAllText($mainPayload, 'NEW_MAIN_FIXTURE')
[IO.File]::WriteAllText($backendPayload, 'NEW_BACKEND_FIXTURE')
$newMain = [IO.File]::ReadAllBytes($mainPayload)
$newBackend = [IO.File]::ReadAllBytes($backendPayload)
$stubSource = Join-Path $runDir 'backend-fixture.rs'
[IO.File]::WriteAllText($stubSource, 'fn main() { std::thread::sleep(std::time::Duration::from_secs(90)); }')
& $rustc --edition=2021 $stubSource -o $stubPath
if ($LASTEXITCODE -ne 0) { throw 'Could not build the isolated backend process fixture.' }

$nsisSource = @'
Unicode true
!include MUI2.nsh
!include LogicLib.nsh
!include x64.nsh
!include "@@UTILS@@"
!addplugindir "@@PLUGINS@@"
!define MAINBINARYNAME "@@MAIN@@"
!define PRODUCTNAME "StoryGraph isolated update guard test"
!define INSTALLMODE "currentUser"
Var PassiveMode
Name "${PRODUCTNAME}"
OutFile "@@INSTALLER@@"
InstallDir "@@DEFAULTDIR@@"
RequestExecutionLevel user
SilentInstall silent
AutoCloseWindow true
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "SimpChinese"
LangString appRunning ${LANG_ENGLISH} "Fixture is running."
LangString appRunningOkKill ${LANG_ENGLISH} "Close fixture."
LangString failedToKillApp ${LANG_ENGLISH} "Could not close fixture."
LangString appRunning ${LANG_SIMPCHINESE} "Fixture is running."
LangString appRunningOkKill ${LANG_SIMPCHINESE} "Close fixture."
LangString failedToKillApp ${LANG_SIMPCHINESE} "Could not close fixture."
!include "@@HOOK@@"
Function .onInit
  StrCpy $PassiveMode 1
FunctionEnd
Section Install
  SetOutPath $INSTDIR
  !insertmacro NSIS_HOOK_PREINSTALL
  !insertmacro CheckIfAppIsRunning "${MAINBINARYNAME}.exe" "${PRODUCTNAME}"
  File "/oname=${MAINBINARYNAME}.exe" "@@MAINPAYLOAD@@"
  File "/oname=storygraph-backend.exe" "@@BACKENDPAYLOAD@@"
SectionEnd
'@
$substitutions = @{
    UTILS = $utilsPath; PLUGINS = $pluginDir; MAIN = $mainName; INSTALLER = $installerPath
    DEFAULTDIR = (Join-Path $runDir 'unused-default'); HOOK = $hookPath
    MAINPAYLOAD = $mainPayload; BACKENDPAYLOAD = $backendPayload
}
foreach ($key in $substitutions.Keys) {
    $nsisSource = $nsisSource.Replace('@@' + $key + '@@', $substitutions[$key].Replace('$', '$$'))
}
$nsisPath = Join-Path $runDir 'fixture.nsi'
[IO.File]::WriteAllText($nsisPath, $nsisSource)
& $makeNsis /V2 $nsisPath
if ($LASTEXITCODE -ne 0) { throw 'Could not compile the real update guard into the isolated installer.' }

function New-Fixture([string]$Name, [switch]$ExecutableBackend, [switch]$MissingBackend) {
    $directory = [IO.Path]::GetFullPath((Join-Path $runDir $Name))
    if (-not $directory.StartsWith($runDir + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Fixture installation escaped its test directory.'
    }
    [IO.Directory]::CreateDirectory($directory) | Out-Null
    [IO.File]::WriteAllText((Join-Path $directory ($mainName + '.exe')), 'OLD_MAIN_FIXTURE')
    $backend = Join-Path $directory 'storygraph-backend.exe'
    if ($ExecutableBackend) { [IO.File]::Copy($stubPath, $backend) }
    elseif (-not $MissingBackend) { [IO.File]::WriteAllText($backend, 'OLD_BACKEND_FIXTURE') }
    return $directory
}

function Invoke-Fixture([string]$Directory) {
    # NSIS /D must be last and unquoted: it consumes the remaining text, including spaces.
    $installer = Start-Process -FilePath $installerPath -ArgumentList ('/S /D=' + $Directory) -WindowStyle Hidden -PassThru
    try {
        if (-not $installer.WaitForExit(30000)) {
            $installer.Kill()
            [void]$installer.WaitForExit(3000)
            throw 'Fixture installer timed out.'
        }
        return $installer.ExitCode
    } finally { $installer.Dispose() }
}

function Matches-Bytes([string]$Path, [byte[]]$Expected) {
    return [Convert]::ToBase64String([IO.File]::ReadAllBytes($Path)) -eq [Convert]::ToBase64String($Expected)
}

function Assert-Updated([string]$Directory, [int]$ExitCode) {
    if ($ExitCode -ne 0 -or
        -not (Matches-Bytes (Join-Path $Directory ($mainName + '.exe')) $newMain) -or
        -not (Matches-Bytes (Join-Path $Directory 'storygraph-backend.exe') $newBackend)) {
        throw "Fixture update failed: $Directory (exit $ExitCode)."
    }
}

$results = [System.Collections.Generic.List[object]]::new()
$results.Add([ordered]@{case = 'production_hook_order'; version = $version; passed = $true})
foreach ($caseName in @('unlocked', 'missing_backend')) {
    $directory = New-Fixture $caseName -MissingBackend:($caseName -eq 'missing_backend')
    $exitCode = Invoke-Fixture $directory
    Assert-Updated $directory $exitCode
    $results.Add([ordered]@{case = $caseName; exit_code = $exitCode; both_updated = $true})
}

$locked = New-Fixture 'locked'
$lockedBackend = Join-Path $locked 'storygraph-backend.exe'
$fileLock = [IO.File]::Open($lockedBackend, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
try { $exitCode = Invoke-Fixture $locked }
finally { $fileLock.Dispose() }
$mainPreserved = [IO.File]::ReadAllText((Join-Path $locked ($mainName + '.exe'))) -eq 'OLD_MAIN_FIXTURE'
$backendPreserved = [IO.File]::ReadAllText($lockedBackend) -eq 'OLD_BACKEND_FIXTURE'
if ($exitCode -ne 2 -or -not $mainPreserved -or -not $backendPreserved) {
    throw 'Locked backend did not abort before replacing application files.'
}
$results.Add([ordered]@{case = 'locked'; exit_code = $exitCode; old_main_preserved = $true; old_backend_preserved = $true})

$matching = New-Fixture 'matching installation with spaces' -ExecutableBackend
$unrelated = New-Fixture 'unrelated installation' -ExecutableBackend
$ownedProcesses = [System.Collections.Generic.List[Diagnostics.Process]]::new()
try {
    foreach ($directory in @($matching, $unrelated)) {
        $ownedProcesses.Add((Start-Process -FilePath (Join-Path $directory 'storygraph-backend.exe') -WindowStyle Hidden -PassThru))
    }
    $exitCode = Invoke-Fixture $matching
    Assert-Updated $matching $exitCode
    if (-not $ownedProcesses[0].HasExited -or $ownedProcesses[1].HasExited) {
        throw 'Guard must stop only the backend at the exact installation path.'
    }
    $results.Add([ordered]@{case = 'exact_path_scope'; exit_code = $exitCode; matching_exited = $true; unrelated_alive = $true; both_updated = $true})
} finally {
    # Clean up retained handles we created, never processes selected by name.
    foreach ($ownedProcess in $ownedProcesses) {
        try {
            if (-not $ownedProcess.HasExited) { $ownedProcess.Kill(); [void]$ownedProcess.WaitForExit(3000) }
        } finally { $ownedProcess.Dispose() }
    }
}

$resultsPath = Join-Path $runDir 'results.json'
$results | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $resultsPath -Encoding utf8
$results | ConvertTo-Json -Depth 3
Write-Host "Update guard passed. Isolated artifacts: $runDir"
