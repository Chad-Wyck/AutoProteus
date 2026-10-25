# AutoProteus keeps its optional runtime inside this project. Windows Hypervisor Platform is required for tasks.
param([switch]$NoBrowser, [ValidateRange(1024, 65515)][int]$Port = 47831)
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskPin = (Get-Content -LiteralPath (Join-Path $taskRoot 'controller\managed-runtime-lock.json') -Raw | ConvertFrom-Json).python_windows
$taskRuntimeParent = Join-Path $taskRoot '.runtime'
$taskRuntime = Join-Path $taskRuntimeParent ('python-' + $taskPin.version)
$taskPython = Join-Path $taskRuntime 'python.exe'

function Test-PrivateRuntime {
    try {
        if (-not (Test-Path -LiteralPath $taskPython)) { return $false }
        $taskRecord = Get-Content -LiteralPath (Join-Path $taskRuntime 'installed-runtime.json') -Raw | ConvertFrom-Json
        if ($taskRecord.version -ne $taskPin.version -or $taskRecord.archive_sha256 -ne $taskPin.sha256) { return $false }
        $taskFiles = @(Get-ChildItem -LiteralPath $taskRuntime -Recurse -File | Where-Object { $_.Name -ne 'installed-runtime.json' })
        if ($taskFiles.Count -ne @($taskRecord.files.PSObject.Properties).Count) { return $false }
        foreach ($taskFile in $taskFiles) {
            if ($taskFile.Attributes -band [IO.FileAttributes]::ReparsePoint) { return $false }
            $taskName = $taskFile.FullName.Substring($taskRuntime.Length + 1).Replace('\', '/')
            if ((Get-FileHash -LiteralPath $taskFile.FullName -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskRecord.files.$taskName) { return $false }
        }
        return $true
    } catch { return $false }
}

try {
    if ((Test-Path -LiteralPath $taskRuntimeParent) -and ((Get-Item -LiteralPath $taskRuntimeParent).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'The private runtime folder must stay inside this project.'
    }
    if (-not (Test-PrivateRuntime)) {
        Add-Type -AssemblyName System.Windows.Forms
        $taskNotice = New-Object System.Windows.Forms.Form
        $taskNotice.Text = 'Starting AutoProteus'
        $taskNotice.Size = New-Object System.Drawing.Size(440, 155)
        $taskNotice.StartPosition = 'CenterScreen'
        $taskNotice.FormBorderStyle = 'FixedDialog'
        $taskNotice.ControlBox = $false
        $taskLabel = New-Object System.Windows.Forms.Label
        $taskLabel.Text = 'Preparing verified AutoProteus components…' + [Environment]::NewLine + 'No separate Python installation needed.'
        $taskLabel.AutoSize = $true
        $taskLabel.Location = New-Object System.Drawing.Point(22, 30)
        $taskNotice.Controls.Add($taskLabel)
        $taskNotice.Show()
        [System.Windows.Forms.Application]::DoEvents()
        New-Item -ItemType Directory -Path $taskRuntimeParent -Force | Out-Null
        $taskArchive = Join-Path $taskRuntimeParent 'python-download.zip'
        Invoke-WebRequest -Uri $taskPin.url -OutFile $taskArchive -UseBasicParsing
        if ((Get-FileHash -LiteralPath $taskArchive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskPin.sha256) {
            throw 'Python failed its integrity check. Reopen the launcher to retry.'
        }
        $taskStage = Join-Path $taskRuntimeParent ('python-stage-' + [Guid]::NewGuid().ToString('N'))
        Expand-Archive -LiteralPath $taskArchive -DestinationPath $taskStage
        Add-Content -LiteralPath (Join-Path $taskStage 'python313._pth') -Value '..\..'
        $taskHashes = @{}
        Get-ChildItem -LiteralPath $taskStage -Recurse -File | ForEach-Object {
            $taskName = $_.FullName.Substring($taskStage.Length + 1).Replace('\', '/')
            $taskHashes[$taskName] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
        @{version=$taskPin.version; archive_sha256=$taskPin.sha256; files=$taskHashes} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $taskStage 'installed-runtime.json') -Encoding UTF8
        $taskBackup = Join-Path $taskRuntimeParent ('python-incomplete-' + [Guid]::NewGuid().ToString('N'))
        foreach ($taskTarget in @($taskStage, $taskRuntime, $taskBackup)) {
            $taskAbsolute = [IO.Path]::GetFullPath($taskTarget)
            if (-not $taskAbsolute.StartsWith([IO.Path]::GetFullPath($taskRuntimeParent) + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid runtime setup location.' }
            if ((Test-Path -LiteralPath $taskTarget) -and ((Get-Item -LiteralPath $taskTarget).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Runtime links are not permitted.' }
        }
        if (Test-Path -LiteralPath $taskRuntime) { Move-Item -LiteralPath $taskRuntime -Destination $taskBackup }
        Move-Item -LiteralPath $taskStage -Destination $taskRuntime
        Remove-Item -LiteralPath $taskArchive
        $taskNotice.Close()
        if (-not (Test-PrivateRuntime)) { throw 'The private runtime failed verification.' }
    }
    $taskData = Join-Path $taskRoot '.data'
    New-Item -ItemType Directory -Path $taskData -Force | Out-Null
    $taskApp = Join-Path $taskRoot 'app.py'
    $taskArguments = '"' + $taskApp + '"'
    if ($NoBrowser) { $taskArguments += ' --no-browser' }
    $taskArguments += ' --port ' + $Port
    $taskLaunchId = [Guid]::NewGuid().ToString('N').Substring(0, 8)
    $taskErrorLog = Join-Path $taskData ('startup-error-' + $taskLaunchId + '.log')
    $taskOutputLog = Join-Path $taskData ('startup-' + $taskLaunchId + '.log')
    # The console executable supplies reliable redirected diagnostics. Its
    # window stays hidden; pythonw can discard exceptions along with stdout.
    $taskProcess = Start-Process -FilePath $taskPython -ArgumentList $taskArguments -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru -RedirectStandardError $taskErrorLog -RedirectStandardOutput $taskOutputLog
    $taskHandle = $taskProcess.Handle
    Start-Sleep -Milliseconds 1300
    if ($taskProcess.HasExited) {
        $taskProcess.WaitForExit()
        if ($null -eq $taskProcess.ExitCode) { throw ('AutoProteus startup status was unavailable. Details are in ' + $taskErrorLog) }
        if ($taskProcess.ExitCode -ne 0) { throw ('AutoProteus could not start (exit ' + $taskProcess.ExitCode + '). Details are in ' + $taskErrorLog) }
    }
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'AutoProteus needs attention', 'OK', 'Error') | Out-Null
    exit 1
}
