param(
    [string]$Set = "51",
    [string]$Source = "",
    [string]$OutDir = "output\pdf",
    [int]$ExpectedPages = 4
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
$OutputEncoding = [Console]::OutputEncoding

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$python = "C:\Users\newgo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$out = Join-Path $root (Join-Path $OutDir "g1_mid_set${Set}_layout.pdf")
$report = Join-Path $root (Join-Path "output\layout_audit" "g1_mid_set${Set}_layout_audit.md")

if ([string]::IsNullOrWhiteSpace($Source)) {
    $sourcePath = Join-Path $root "광영여고_고1_1학기중간_본문전용_추가문항_401-500_학생용.md"
    & $python (Join-Path $root "tools\render_g1_exam_layout.py") --set $Set --out $out
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    if ([System.IO.Path]::IsPathRooted($Source)) {
        $sourcePath = $Source
    } else {
        $sourcePath = Join-Path $root $Source
    }
    & $python (Join-Path $root "tools\render_g1_exam_layout.py") --set $Set --source $sourcePath --out $out
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

& $python (Join-Path $root "tools\audit_g1_exam_layout.py") --generated $out --source $sourcePath --mode body --expected-pages $ExpectedPages --report $report
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Output $out
