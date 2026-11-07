param([Parameter(Mandatory=$true)][string]$Request)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
try {
    $options = Get-Content -LiteralPath $Request -Raw -Encoding UTF8 | ConvertFrom-Json
    Add-Type -AssemblyName UIAutomationClient
    Add-Type -AssemblyName UIAutomationTypes
    Add-Type -AssemblyName WindowsBase
    $references = @('System.dll', 'System.Core.dll', [System.Windows.Point].Assembly.Location,
        [System.Windows.Automation.AutomationElement].Assembly.Location,
        [System.Windows.Automation.ControlType].Assembly.Location)
    Add-Type -Path @((Join-Path $PSScriptRoot 'Recorder.cs'), (Join-Path $PSScriptRoot 'CallState.cs'), (Join-Path $PSScriptRoot 'CallRecovery.cs')) -ReferencedAssemblies $references
    if ($options.action -eq 'devices') {
        ConvertTo-Json -InputObject @([CompanionRecording.Native]::Inputs()) -Compress
    } elseif ($options.action -in @('calls','restore')) {
        $packages = @(Get-AppxPackage -ErrorAction Stop)
        $processes = @(Get-Process -Name 'WhatsApp', 'WhatsApp.Root' -ErrorAction SilentlyContinue)
        $results = @()
        foreach ($channel in $options.channels) {
            $package = @($packages | Where-Object { $_.PackageFamilyName -eq $channel.family })
            $matches = @()
            if ($package.Count -eq 1) {
                $root = [IO.Path]::GetFullPath($package[0].InstallLocation).TrimEnd('\') + '\'
                $matches = @($processes | Where-Object {
                    try { $_.MainModule.FileName.StartsWith($root, [StringComparison]::OrdinalIgnoreCase) } catch { $false }
                })
            }
            if ($matches.Count -eq 1) {
                if ($options.action -eq 'restore' -and $matches[0].Id -eq $options.pid) {
                    [CompanionRecording.CallRecovery]::Restore([int]$options.pid, $root, [int]$options.window)
                    exit 0
                }
                $results += [CompanionRecording.CallState]::Probe($matches[0].Id, $root, $channel.channel)
            } else {
                $results += @{channel=$channel.channel; state='unknown'; pid=0; window=0}
            }
        }
        if ($options.action -eq 'restore') { throw 'No matching process' }
        ConvertTo-Json -InputObject @($results) -Compress
    } elseif ($options.action -eq 'record') {
        [CompanionRecording.Recorder]::Run([int]$options.pid, [string]$options.root,
            [string]$options.microphone, [string]$options.output, [int]$options.parent, [int]$options.callWindow, [int]$options.foreground)
    } else { throw 'Unknown action' }
} catch {
    $cause = $_.Exception
    while ($null -ne $cause) {
        if ($cause.GetType().FullName -eq 'CompanionRecording.CallUnavailableException') {
            [Console]::WriteLine('CALL_UNAVAILABLE')
            exit 1
        }
        if ($cause.GetType().FullName -eq 'CompanionRecording.FocusChangedException') {
            [Console]::WriteLine('FOCUS_CHANGED')
            exit 1
        }
        $cause = $cause.InnerException
    }
    [Console]::WriteLine('ERROR')
    exit 1
}
