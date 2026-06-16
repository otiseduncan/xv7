param(
    [string]$Root = (Get-Location).Path,
    [string]$OutDir = "reports",
    [switch]$IncludeGenerated
)

$ErrorActionPreference = "Stop"

$WatchLines = 500
$LargeLines = 1000
$SplitRecommendedLines = 2000
$CriticalLines = 5000
$ExtremeLines = 20000

$Root = (Resolve-Path $Root).Path
$ReportRoot = Join-Path $Root $OutDir
New-Item -ItemType Directory -Force -Path $ReportRoot | Out-Null

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$MarkdownReport = Join-Path $ReportRoot "ARCHITECTURE_SIZE_AUDIT_$Timestamp.md"
$CsvReport = Join-Path $ReportRoot "architecture-size-audit-files_$Timestamp.csv"

$SourceExtensions = @(
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".py", ".ps1", ".json", ".md", ".yml", ".yaml",
    ".css", ".scss", ".html",
    ".sql", ".sh", ".bat", ".cmd"
)

$GeneratedOrVendorDirs = @(
    ".git",
    "node_modules",
    "dist",
    "build",
    "coverage",
    ".next",
    ".nuxt",
    ".vite",
    ".cache",
    ".turbo",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "playwright-report",
    "test-results",
    "generated-sites",
    "runtime",
    "logs",
    "tmp",
    "temp"
)

$GeneratedOrVendorFiles = @(
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Pipfile.lock"
)

function Get-RelativePath {
    param([string]$FullPath)
    return ($FullPath.Substring($Root.Length).TrimStart("\", "/") -replace "\\", "/")
}

function Test-IsGeneratedPath {
    param([string]$FullPath)

    $relative = Get-RelativePath $FullPath
    $parts = $relative -split "/"

    foreach ($part in $parts) {
        if ($GeneratedOrVendorDirs -contains $part) {
            return $true
        }
    }

    $name = [System.IO.Path]::GetFileName($FullPath)
    return ($GeneratedOrVendorFiles -contains $name)
}

function Get-Severity {
    param(
        [int]$Lines,
        [long]$Bytes
    )

    if ($Lines -ge $ExtremeLines) { return "EXTREME_SPLIT_NOW" }
    if ($Lines -ge $CriticalLines) { return "CRITICAL_SPLIT_NOW" }
    if ($Lines -ge $SplitRecommendedLines) { return "SPLIT_RECOMMENDED" }
    if ($Lines -ge $LargeLines) { return "LARGE_REVIEW" }
    if ($Lines -ge $WatchLines) { return "WATCH" }

    if (($Bytes / 1KB) -ge 1024) { return "LARGE_BY_SIZE_REVIEW" }
    if (($Bytes / 1KB) -ge 512) { return "WATCH_BY_SIZE" }

    return "OK"
}

function Get-TopModule {
    param([string]$RelativePath)

    $parts = $RelativePath -split "/"

    if ($parts.Count -ge 2 -and $parts[0] -in @("src", "server", "core", "tests", "e2e", "scripts", "docs", "public")) {
        return "$($parts[0])/$($parts[1])"
    }

    if ($parts.Count -ge 1) {
        return $parts[0]
    }

    return "(root)"
}

Write-Host ""
Write-Host "XV7 Architecture Size Audit" -ForegroundColor Cyan
Write-Host "Root: $Root"
Write-Host "Include generated/vendor: $IncludeGenerated"
Write-Host ""

$results = @()
$skipped = @()

$allFiles = Get-ChildItem -Path $Root -Recurse -File -Force -ErrorAction SilentlyContinue |
    Where-Object { $SourceExtensions -contains $_.Extension.ToLowerInvariant() }

foreach ($file in $allFiles) {
    $relative = Get-RelativePath $file.FullName
    $isGenerated = Test-IsGeneratedPath $file.FullName

    if ($isGenerated -and -not $IncludeGenerated) {
        $skipped += [pscustomobject]@{
            Path = $relative
            BytesKB = [math]::Round($file.Length / 1KB, 2)
            Reason = "generated_or_vendor_excluded"
        }
        continue
    }

    try {
        $lineCount = 0
        $reader = [System.IO.File]::OpenText($file.FullName)

        try {
            while ($null -ne $reader.ReadLine()) {
                $lineCount++
            }
        }
        finally {
            $reader.Close()
        }

        $results += [pscustomobject]@{
            Severity = Get-Severity -Lines $lineCount -Bytes $file.Length
            Lines = $lineCount
            BytesKB = [math]::Round($file.Length / 1KB, 2)
            Module = Get-TopModule $relative
            IsGeneratedOrVendor = $isGenerated
            Extension = $file.Extension.ToLowerInvariant()
            Path = $relative
        }
    }
    catch {
        $results += [pscustomobject]@{
            Severity = "READ_ERROR"
            Lines = -1
            BytesKB = [math]::Round($file.Length / 1KB, 2)
            Module = Get-TopModule $relative
            IsGeneratedOrVendor = $isGenerated
            Extension = $file.Extension.ToLowerInvariant()
            Path = $relative
        }
    }
}

$sortedFiles = @($results | Sort-Object Lines -Descending)
$problemFiles = @($sortedFiles | Where-Object { $_.Severity -ne "OK" -and $_.Severity -ne "WATCH_BY_SIZE" })
$criticalFiles = @($sortedFiles | Where-Object { $_.Severity -in @("EXTREME_SPLIT_NOW", "CRITICAL_SPLIT_NOW", "SPLIT_RECOMMENDED") })

$moduleSummary = @(
    $results |
        Group-Object Module |
        ForEach-Object {
            $group = @($_.Group)
            $largest = $group | Sort-Object Lines -Descending | Select-Object -First 1

            [pscustomobject]@{
                Module = $_.Name
                Files = $group.Count
                TotalLines = ($group | Measure-Object Lines -Sum).Sum
                LargestFileLines = $largest.Lines
                LargestFile = $largest.Path
                CriticalFiles = @($group | Where-Object { $_.Severity -in @("EXTREME_SPLIT_NOW", "CRITICAL_SPLIT_NOW", "SPLIT_RECOMMENDED") }).Count
                ReviewFiles = @($group | Where-Object { $_.Severity -ne "OK" }).Count
            }
        } |
        Sort-Object TotalLines -Descending
)

$sortedFiles | Export-Csv -NoTypeInformation -Path $CsvReport

$md = @()
$md += "# XV7 Architecture Size Audit"
$md += ""
$md += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$md += ""
$md += "Root: ``$Root``"
$md += ""
$md += "Include generated/vendor: ``$IncludeGenerated``"
$md += ""
$md += "## Verdict"
$md += ""

if ($criticalFiles.Count -eq 0) {
    $md += "No source files crossed the split-now thresholds in the scanned set."
}
else {
    $md += "Found $($criticalFiles.Count) file(s) at SPLIT_RECOMMENDED or worse."
}

$md += ""
$md += "## Thresholds"
$md += ""
$md += "| Severity | Meaning |"
$md += "|---|---|"
$md += "| OK | Under 500 lines and not oversized by file size |"
$md += "| WATCH | 500+ lines; monitor for complexity |"
$md += "| LARGE_REVIEW | 1000+ lines; review for splitting |"
$md += "| SPLIT_RECOMMENDED | 2000+ lines; likely too large |"
$md += "| CRITICAL_SPLIT_NOW | 5000+ lines; split unless generated/vendor |"
$md += "| EXTREME_SPLIT_NOW | 20000+ lines; architecture emergency unless generated/vendor |"
$md += ""
$md += "## Top 30 Largest Files"
$md += ""
$md += "| Severity | Lines | KB | Generated/Vendor | Path |"
$md += "|---|---:|---:|---|---|"

foreach ($item in ($sortedFiles | Select-Object -First 30)) {
    $md += "| $($item.Severity) | $($item.Lines) | $($item.BytesKB) | $($item.IsGeneratedOrVendor) | ``$($item.Path)`` |"
}

$md += ""
$md += "## Files Needing Review"
$md += ""
$md += "| Severity | Lines | KB | Module | Path |"
$md += "|---|---:|---:|---|---|"

foreach ($item in ($problemFiles | Select-Object -First 75)) {
    $md += "| $($item.Severity) | $($item.Lines) | $($item.BytesKB) | $($item.Module) | ``$($item.Path)`` |"
}

$md += ""
$md += "## Largest Modules/Folders"
$md += ""
$md += "| Module | Files | Total Lines | Largest File Lines | Critical Files | Largest File |"
$md += "|---|---:|---:|---:|---:|---|"

foreach ($module in ($moduleSummary | Select-Object -First 30)) {
    $md += "| ``$($module.Module)`` | $($module.Files) | $($module.TotalLines) | $($module.LargestFileLines) | $($module.CriticalFiles) | ``$($module.LargestFile)`` |"
}

$md += ""
$md += "## Architecture Rules"
$md += ""
$md += "- Normal source files should usually stay under 500 lines."
$md += "- 500-1000 lines is a watch zone."
$md += "- 1000-2000 lines should be reviewed."
$md += "- 2000+ lines should usually be split."
$md += "- 5000+ lines is a serious architecture warning unless generated."
$md += "- 20000+ lines is extreme and should not be hand-maintained source."
$md += "- A 150000-line file should almost never be active source code."
$md += ""
$md += "## Output Files"
$md += ""
$md += "- File CSV: ``$CsvReport``"

Set-Content -Path $MarkdownReport -Value $md -Encoding UTF8

Write-Host ""
Write-Host "Audit complete." -ForegroundColor Green
Write-Host "Markdown report: $MarkdownReport"
Write-Host "File CSV:        $CsvReport"
Write-Host ""

Write-Host "Top largest files:" -ForegroundColor Cyan
$sortedFiles |
    Select-Object -First 20 Severity, Lines, BytesKB, IsGeneratedOrVendor, Path |
    Format-Table -AutoSize

if ($criticalFiles.Count -gt 0) {
    Write-Host ""
    Write-Host "Files that need splitting/review now:" -ForegroundColor Yellow
    $criticalFiles |
        Select-Object Severity, Lines, BytesKB, IsGeneratedOrVendor, Path |
        Format-Table -AutoSize
}
