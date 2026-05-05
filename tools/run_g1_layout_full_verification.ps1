param(
    [string]$Sets = "51-62",
    [string]$Source = "",
    [int]$ExpectedPages = 4
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
$OutputEncoding = [Console]::OutputEncoding

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$python = "C:\Users\newgo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$script = Join-Path $root "tools\run_g1_layout_full_verification.py"

if ([string]::IsNullOrWhiteSpace($Source)) {
    & $python $script --sets $Sets --expected-pages $ExpectedPages
} else {
    & $python $script --sets $Sets --source $Source --expected-pages $ExpectedPages
}

exit $LASTEXITCODE
