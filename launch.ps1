# AutoProteus keeps its optional runtime inside this project. Windows Hypervisor Platform is required for tasks.
param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskRuntime = Join-Path $taskRoot '.runtime\python'
$taskPython = Join-Path $taskRuntime 'pythonw.exe'

try {
    if (-not (Test-Path -LiteralPath $taskPython)) {
        $taskExisting = Get-Command python.exe -ErrorAction SilentlyContinue
        if ($taskExisting -and $taskExisting.Source -notlike '*WindowsApps*') {
            $taskVersion = & $taskExisting.Source -c "import sys; print(int(sys.version_info >= (3, 10)))" 2>$null
            if ($taskVersion -eq '1') {
                $taskSibling = Join-Path (Split-Path -Parent $taskExisting.Source) 'pythonw.exe'
                $taskPython = if (Test-Path -LiteralPath $taskSibling) { $taskSibling } else { $taskExisting.Source }
            }
        }
    }
    if (-not (Test-Path -LiteralPath $taskPython)) {
        Add-Type -AssemblyName System.Windows.Forms
        $taskNotice = New-Object System.Windows.Forms.Form
        $taskNotice.Text = 'Starting AutoProteus'
        $taskNotice.Size = New-Object System.Drawing.Size(440, 155)
        $taskNotice.StartPosition = 'CenterScreen'
        $taskNotice.FormBorderStyle = 'FixedDialog'
        $taskNotice.ControlBox = $false
        $taskLabel = New-Object System.Windows.Forms.Label
        $taskLabel.Text = 'Preparing AutoProteus for its first launch…' + [Environment]::NewLine + 'Downloading a small Python runtime. No installation needed.'
        $taskLabel.AutoSize = $true
        $taskLabel.Location = New-Object System.Drawing.Point(22, 30)
        $taskNotice.Controls.Add($taskLabel)
        $taskNotice.Show()
        [System.Windows.Forms.Application]::DoEvents()
        New-Item -ItemType Directory -Path $taskRuntime -Force | Out-Null
        $taskArchive = Join-Path $taskRoot '.runtime\python-download.zip'
        Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.13.12/python-3.13.12-embed-amd64.zip' -OutFile $taskArchive -UseBasicParsing
        Expand-Archive -LiteralPath $taskArchive -DestinationPath $taskRuntime -Force
        # Embedded Python isolates sys.path; explicitly include the project root.
        $taskPathFile = Join-Path $taskRuntime 'python313._pth'
        Add-Content -LiteralPath $taskPathFile -Value '..\..'
        Remove-Item -LiteralPath $taskArchive
        $taskNotice.Close()
        $taskPython = Join-Path $taskRuntime 'pythonw.exe'
    }
    $taskData = Join-Path $taskRoot '.data'
    New-Item -ItemType Directory -Path $taskData -Force | Out-Null
    $taskApp = Join-Path $taskRoot 'app.py'
    $taskArguments = '"' + $taskApp + '"'
    if ($NoBrowser) { $taskArguments += ' --no-browser' }
    $taskLaunchId = [Guid]::NewGuid().ToString('N').Substring(0, 8)
    $taskErrorLog = Join-Path $taskData ('startup-error-' + $taskLaunchId + '.log')
    $taskOutputLog = Join-Path $taskData ('startup-' + $taskLaunchId + '.log')
    $taskProcess = Start-Process -FilePath $taskPython -ArgumentList $taskArguments -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru -RedirectStandardError $taskErrorLog -RedirectStandardOutput $taskOutputLog
    Start-Sleep -Milliseconds 1300
    if ($taskProcess.HasExited -and $taskProcess.ExitCode -ne 0) {
        throw ('AutoProteus could not start. Details are in ' + $taskErrorLog)
    }
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'AutoProteus needs attention', 'OK', 'Error') | Out-Null
    exit 1
}
