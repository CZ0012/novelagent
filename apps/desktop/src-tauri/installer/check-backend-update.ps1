param(
    [Parameter(Mandatory = $true)]
    [string]$InstallDir
)

# Windows PowerShell 5.1 compatible. This guard never reads the story workspace.
# Stop only processes whose executable is this installation's bundled sidecar.
# The NSIS hook runs before replacing the main executable or writing version data.
$ErrorActionPreference = 'Stop'

try {
    $installationPath = [IO.Path]::GetFullPath($InstallDir)
    $backendPath = [IO.Path]::Combine($installationPath, 'storygraph-backend.exe')
    try {
        [void][IO.File]::GetAttributes($backendPath)
    } catch [IO.FileNotFoundException] {
        exit 0
    } catch [IO.DirectoryNotFoundException] {
        exit 0
    }
    $deadline = [DateTime]::UtcNow.AddSeconds(10)
    do {
        foreach ($backendProcess in [Diagnostics.Process]::GetProcessesByName('storygraph-backend')) {
            try {
                # Reading MainModule binds this Process object to its live handle;
                # an inaccessible or unrelated process is never selected by name alone.
                $processPath = $backendProcess.MainModule.FileName
                if ([string]::Equals($processPath, $backendPath, [StringComparison]::OrdinalIgnoreCase)) {
                    $backendProcess.Kill()
                    [void]$backendProcess.WaitForExit(500)
                }
            } catch {
                # A process may exit between enumeration and inspection. Inaccessible
                # matching executables remain protected by the exclusive probe below.
            } finally {
                $backendProcess.Dispose()
            }
        }

        try {
            $probe = [IO.File]::Open($backendPath, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
            $probe.Dispose()
            exit 0
        } catch {
            if ([DateTime]::UtcNow -ge $deadline) { exit 2 }
        }
        Start-Sleep -Milliseconds 200
    } while ([DateTime]::UtcNow -lt $deadline)
    exit 2
} catch {
    exit 3
}
