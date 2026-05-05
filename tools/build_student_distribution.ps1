$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $ScriptDir "..")
$BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (Test-Path $BundledPython) {
  & $BundledPython (Join-Path $ScriptDir "build_student_distribution.py") --root $Root
} else {
  python (Join-Path $ScriptDir "build_student_distribution.py") --root $Root
}
