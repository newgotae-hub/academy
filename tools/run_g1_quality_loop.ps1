param(
    [int]$MaxIterations = 1,
    [switch]$Continuous,
    [int]$DelaySeconds = 5,
    [string]$ReportPath = "g1_quality_loop_latest.txt"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $ScriptDir "..")
$ReportFullPath = Join-Path $Root $ReportPath

$Checks = @(
    @{ Name = "body_bank"; Path = (Join-Path $ScriptDir "check_g1_midterm_body_bank.ps1") },
    @{ Name = "premium_gate"; Path = (Join-Path $ScriptDir "check_g1_midterm_premium_gate.ps1") },
    @{ Name = "package"; Path = (Join-Path $ScriptDir "check_g1_midterm_package.ps1") }
)

function Invoke-QualityCheck($check) {
    $result = @{
        Name = $check.Name
        Ok = $true
        Output = @()
    }

    try {
        $result.Output = @(& $check.Path 2>&1)
    }
    catch {
        $result.Ok = $false
        $result.Output = @($_.Exception.Message)
        if ($_.ScriptStackTrace) {
            $result.Output += $_.ScriptStackTrace
        }
    }

    foreach ($line in $result.Output) {
        if ($line -match '^FAIL\s+') {
            $result.Ok = $false
        }
    }

    return $result
}

function Write-LoopReport($iteration, $results) {
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("G1 quality loop")
    $lines.Add("timestamp=$(Get-Date -Format s)")
    $lines.Add("iteration=$iteration")
    $lines.Add("")

    foreach ($result in $results) {
        $status = if ($result.Ok) { "PASS" } else { "FAIL" }
        $lines.Add("[$status] $($result.Name)")
        foreach ($line in $result.Output) {
            $lines.Add("  $line")
        }
        $lines.Add("")
    }

    Set-Content -Encoding UTF8 -LiteralPath $ReportFullPath -Value $lines
}

$iteration = 0
while ($Continuous -or $iteration -lt $MaxIterations) {
    $iteration += 1
    Write-Host "QUALITY_LOOP iteration=$iteration"

    $results = @()
    foreach ($check in $Checks) {
        Write-Host "RUN $($check.Name)"
        $result = Invoke-QualityCheck $check
        $results += $result
        foreach ($line in $result.Output) {
            Write-Host $line
        }
    }

    Write-LoopReport $iteration $results

    $failed = @($results | Where-Object { -not $_.Ok })
    if ($failed.Count -gt 0) {
        Write-Host "QUALITY_LOOP failed report=$ReportFullPath"
        throw "G1 quality loop failed"
    }

    Write-Host "QUALITY_LOOP pass report=$ReportFullPath"

    if (-not $Continuous -and $iteration -ge $MaxIterations) {
        break
    }

    Start-Sleep -Seconds $DelaySeconds
}
