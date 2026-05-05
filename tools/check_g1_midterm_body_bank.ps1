$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Failures = New-Object System.Collections.Generic.List[string]
$Warnings = New-Object System.Collections.Generic.List[string]

function Read-Path($path) {
    if (-not (Test-Path -LiteralPath $path)) {
        $Failures.Add("missing_file: $path")
        return ""
    }
    return Get-Content -Raw -Encoding UTF8 -LiteralPath $path
}

function Resolve-BodyPair($label, $fragment) {
    $files = @(Get-ChildItem -File -LiteralPath $Root -Filter "*$fragment*.md")
    if ($files.Count -lt 2) {
        $Failures.Add("$label pair_files expected>=2 actual=$($files.Count)")
        return $null
    }

    $studentFile = $null
    $teacherFile = $null
    foreach ($file in $files) {
        $text = Read-Path $file.FullName
        if ((Count-Re $text '(?m)^###\s+') -gt 20) {
            $studentFile = $file.FullName
        }
        elseif ((Count-Re $text '(?m)^\|\s*(?:3[9]|4[0-9]|50|5[1-9]|6[0-2]|63A)\s*\|') -gt 0) {
            $teacherFile = $file.FullName
        }
    }

    if ($null -eq $studentFile) { $Failures.Add("$label student_file_not_resolved") }
    if ($null -eq $teacherFile) { $Failures.Add("$label teacher_file_not_resolved") }
    if ($null -eq $studentFile -or $null -eq $teacherFile) { return $null }

    return @{ Student = $studentFile; Teacher = $teacherFile }
}

function Count-Re($text, $pattern) {
    return [regex]::Matches($text, $pattern).Count
}

function Count-AnswerRows($text) {
    $count = 0
    foreach ($line in ($text -split "`r?`n")) {
        if ($line -match '^\|\s*(?:3[9]|4[0-9]|50|5[1-9]|6[0-2]|63A)\s*\|') {
            if (($line.ToCharArray() | Where-Object { $_ -eq '|' }).Count -ge 9) {
                $count += 1
            }
        }
    }
    return $count
}

function Add-Fail($label, $actual, $expected) {
    if ($actual -ne $expected) {
        $Failures.Add("$label expected=$expected actual=$actual")
    }
}

function Check-BodyFile($label, $fragment, $expectedQuestions, $expectedFullSets, $expectedTeacherRows) {
    $pair = Resolve-BodyPair $label $fragment
    if ($null -eq $pair) { return }

    $student = Read-Path $pair.Student
    $teacher = Read-Path $pair.Teacher
    if ($student.Length -eq 0 -or $teacher.Length -eq 0) { return }

    $objectiveCount = Count-Re $student '(?m)^###\s+(?:[6-9]|10|11)\.'
    $shortAnswerCount = Count-Re $student '(?m)^\(A\)\s+_+'
    $halfPackCount = Count-Re $student '(?m)^###\s+63A-[1-4]\.'
    $halfPackShortAnswerCount = Count-Re $student '(?m)^###\s+63A-4\.'
    $totalQuestions = $objectiveCount + $shortAnswerCount + $halfPackCount - $halfPackShortAnswerCount

    Add-Fail "$label total_body_questions" $totalQuestions $expectedQuestions
    Add-Fail "$label full_set_headers" (Count-Re $student '(?m)^##\s+.*\s+\d+\s*$') $expectedFullSets
    Add-Fail "$label teacher_answer_rows" (Count-AnswerRows $teacher) $expectedTeacherRows

    foreach ($token in @('canonical', 'forbidden', 'QA', 'teacher_only', 'answer_key')) {
        if ($student -match [regex]::Escape($token)) {
            $Failures.Add("$label student_leak_token: $token")
        }
    }

    foreach ($token in @('only*', 'FIXME', 'TODO', 'PENDING')) {
        if ($teacher -match [regex]::Escape($token)) {
            $Failures.Add("$label unresolved_teacher_note: $token")
        }
    }

    if ((Count-Re $student '(?m)^###\s+11\.') -ne $expectedFullSets) {
        $Failures.Add("$label q11_count does not match full set count")
    }
    $surfaceOrderClues = Count-Re $student '\b(?:First|Later|Therefore|Thus|At first)\b'
    if ($surfaceOrderClues -gt 8) {
        $Warnings.Add("$label many_surface_order_clues: $surfaceOrderClues")
    }
}

Check-BodyFile `
    "39-50" `
    "39-50" `
    96 `
    12 `
    12

Check-BodyFile `
    "401-500" `
    "401-500" `
    100 `
    12 `
    13

if ($Warnings.Count -gt 0) {
    foreach ($warning in $Warnings) {
        Write-Host "WARN  $warning"
    }
}

if ($Failures.Count -gt 0) {
    foreach ($failure in $Failures) {
        Write-Host "FAIL  $failure"
    }
    throw "G1 midterm body bank lint failed"
}

Write-Host "PASS: G1 midterm body bank lint passed"
