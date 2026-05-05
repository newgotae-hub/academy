param(
  [string]$Root = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"
$script = Join-Path $PSScriptRoot "check_g1_midterm_package.py"
$bundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if (Test-Path -LiteralPath $bundledPython) {
  & $bundledPython $script --root $Root
} else {
  & python $script --root $Root
}
exit $LASTEXITCODE
