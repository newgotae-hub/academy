$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Failures = New-Object System.Collections.Generic.List[string]
$Warnings = New-Object System.Collections.Generic.List[string]

function Read-FileText($path) {
    return Get-Content -Raw -Encoding UTF8 -LiteralPath $path
}

function Resolve-Pair($fragment) {
    $files = @(Get-ChildItem -File -LiteralPath $Root -Filter "*$fragment*.md")
    $student = $null
    $teacher = $null

    foreach ($file in $files) {
        $text = Read-FileText $file.FullName
        $headingCount = [regex]::Matches($text, '(?m)^###\s+').Count
        $answerRowCount = 0
        foreach ($line in ($text -split "`r?`n")) {
            if ($line -match '^\|\s*(?:5[1-9]|6[0-2]|63A)\s*\|') {
                $pipeCount = ($line.ToCharArray() | Where-Object { $_ -eq '|' }).Count
                if ($pipeCount -ge 9) { $answerRowCount += 1 }
            }
        }

        if ($headingCount -gt 20) { $student = $file.FullName }
        elseif ($answerRowCount -gt 0) { $teacher = $file.FullName }
    }

    if ($null -eq $student) { $Failures.Add("student_file_not_found fragment=$fragment") }
    if ($null -eq $teacher) { $Failures.Add("teacher_file_not_found fragment=$fragment") }
    return @{ Student = $student; Teacher = $teacher }
}

function Split-Row($line) {
    return @($line -split '\|' | ForEach-Object { $_.Trim() })
}

function Pipe-Count($line) {
    return ($line.ToCharArray() | Where-Object { $_ -eq '|' }).Count
}

function Data-Cell($line) {
    $cells = Split-Row $line
    if ($cells.Count -lt 3) { return "" }
    return $cells[2]
}

function Comma-Count($text) {
    return ($text.ToCharArray() | Where-Object { $_ -eq ',' }).Count
}

function Parse-QuickRows($teacherText) {
    $rows = @{}
    foreach ($line in ($teacherText -split "`r?`n")) {
        if ($line -match '^\|\s*(5[1-9]|6[0-2]|63A)\s*\|') {
            if ((Pipe-Count $line) -ge 9) {
                $cells = Split-Row $line
                $set = $cells[1]
                $rows[$set] = @{
                    Q6 = $cells[2]
                    Q7 = $cells[3]
                    Q8 = $cells[4]
                    SA1 = $cells[5]
                    Q9 = $cells[6]
                    Q10 = $cells[7]
                    Q11 = $cells[8]
                    SA2 = $cells[9]
                }
            }
        }
    }
    return $rows
}

function Parse-TraceRows($teacherText, $expectedCommaCount) {
    $rows = @{}
    foreach ($line in ($teacherText -split "`r?`n")) {
        if ($line -match '^\|\s*(5[1-9]|6[0-2]|63A)\s*\|') {
            if ((Pipe-Count $line) -eq 4) {
                $positions = Data-Cell $line
                if ((Comma-Count $positions) -eq $expectedCommaCount) {
                    $cells = Split-Row $line
                    $rows[$cells[1]] = $positions
                }
            }
        }
    }
    return $rows
}

function Get-SetBlock($studentText, $set) {
    $pattern = "(?ms)^##\s+[^\r\n]*\s+$([regex]::Escape($set))\s*$.*?(?=^##\s+|\z)"
    $match = [regex]::Match($studentText, $pattern)
    if (-not $match.Success) { return "" }
    return $match.Value
}

function Get-QBlock($setBlock, $qNo) {
    $pattern = "(?ms)^###\s+$qNo\.[^\r\n]*$.*?(?=^###\s+|\z)"
    $match = [regex]::Match($setBlock, $pattern)
    if (-not $match.Success) { return "" }
    return $match.Value
}

function Find-OptionNumber($qBlock, $positions) {
    $target = ($positions -replace '\s+', ' ').Trim()
    foreach ($line in ($qBlock -split "`r?`n")) {
        if ($line -match '^\s*([1-5])\.\s+(.+?)\s*$') {
            $optionNo = $Matches[1]
            $optionText = ($Matches[2] -replace '\s+', ' ').Trim()
            if ($optionText -eq $target) { return $optionNo }
        }
    }
    return $null
}

function Add-DistributionWarnings($quickRows, $label) {
    foreach ($q in @("Q6", "Q7", "Q8", "Q9", "Q10")) {
        $counts = @{}
        foreach ($set in $quickRows.Keys) {
            if ($set -eq "63A" -and ($q -eq "Q9" -or $q -eq "Q10")) { continue }
            $value = $quickRows[$set][$q]
            if ($value -eq "-") { continue }
            if (-not $counts.ContainsKey($value)) { $counts[$value] = 0 }
            $counts[$value] += 1
        }
        foreach ($key in $counts.Keys) {
            if ($counts[$key] -ge 8) {
                $Warnings.Add("$label distribution_skew $q=$key count=$($counts[$key])")
            }
        }
    }
}

$pair = Resolve-Pair "401-500"
if ($null -ne $pair.Student -and $null -ne $pair.Teacher) {
    $studentText = Read-FileText $pair.Student
    $teacherText = Read-FileText $pair.Teacher

    $quickRows = Parse-QuickRows $teacherText
    $q8Trace = Parse-TraceRows $teacherText 3
    $q11Trace = Parse-TraceRows $teacherText 1

    if ($quickRows.Count -ne 13) { $Failures.Add("401-500 quick_row_count expected=13 actual=$($quickRows.Count)") }
    if ($q8Trace.Count -ne 13) { $Failures.Add("401-500 q8_trace_count expected=13 actual=$($q8Trace.Count)") }
    if ($q11Trace.Count -ne 12) { $Failures.Add("401-500 q11_trace_count expected=12 actual=$($q11Trace.Count)") }

    foreach ($set in $quickRows.Keys) {
        if ($quickRows[$set].SA1 -notmatch '^A what\b') {
            $Failures.Add("401-500 set=$set sa1_A_not_what")
        }
        if ($set -ne "63A" -and $quickRows[$set].SA2 -notmatch '^A change\b') {
            $Failures.Add("401-500 set=$set sa2_A_not_change")
        }
    }

    foreach ($set in $q8Trace.Keys) {
        if (-not $quickRows.ContainsKey($set)) {
            $Failures.Add("401-500 q8_trace_without_quick_row set=$set")
            continue
        }

        if ($set -eq "63A") {
            $qBlockMatch = [regex]::Match($studentText, '(?ms)^###\s+63A-3\..*?(?=^###\s+63A-4\.|\z)')
            $qBlock = $qBlockMatch.Value
        }
        else {
            $setBlock = Get-SetBlock $studentText $set
            $qBlock = Get-QBlock $setBlock 8
        }

        $optionNumber = Find-OptionNumber $qBlock $q8Trace[$set]
        if ($null -eq $optionNumber) {
            $Failures.Add("401-500 set=$set q8_trace_not_found_in_student_options")
        }
        elseif ($quickRows[$set].Q8 -ne $optionNumber) {
            $Failures.Add("401-500 set=$set q8_quick_answer_mismatch quick=$($quickRows[$set].Q8) trace_option=$optionNumber")
        }
    }

    foreach ($set in $q11Trace.Keys) {
        if ($quickRows[$set].Q11 -ne $q11Trace[$set]) {
            $Failures.Add("401-500 set=$set q11_quick_trace_mismatch quick=$($quickRows[$set].Q11) trace=$($q11Trace[$set])")
        }
    }

    foreach ($token in @("only*", "FIXME", "TODO", "PENDING", "??", "A camouflage", "A why")) {
        if ($teacherText -match [regex]::Escape($token)) {
            $Failures.Add("401-500 teacher_forbidden_token token=$token")
        }
    }

    foreach ($token in @("canonical", "forbidden", "answer_key", "teacher_only")) {
        if ($studentText -match [regex]::Escape($token)) {
            $Failures.Add("401-500 student_forbidden_token token=$token")
        }
    }

    Add-DistributionWarnings $quickRows "401-500"
}

if ($Warnings.Count -gt 0) {
    foreach ($warning in $Warnings) {
        Write-Host "WARN  $warning"
    }
}

if ($Failures.Count -gt 0) {
    foreach ($failure in $Failures) {
        Write-Host "FAIL  $failure"
    }
    throw "G1 midterm premium gate failed"
}

Write-Host "PASS: G1 midterm premium gate passed"
