param([string]$HostName = $env:RADAR_BACKUP_HOST)
$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($HostName)) {
    throw 'Pass -HostName or set RADAR_BACKUP_HOST to an SSH host alias.'
}
$Repo = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Repo '.venv\Scripts\python.exe'
$Script = Join-Path $PSScriptRoot 'backup.py'
$Destination = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Trendradar-backups'
$Action = New-ScheduledTaskAction -Execute $Python -Argument ('"{0}" --host "{1}" --directory "{2}"' -f $Script,$HostName,$Destination) -WorkingDirectory $Repo
$Trigger = New-ScheduledTaskTrigger -Daily -At '03:30'
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew
$Principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'Trendradar daily backup' -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Description 'Back up the private news database over SSH to the local workstation.' -Force | Select-Object TaskName,State
