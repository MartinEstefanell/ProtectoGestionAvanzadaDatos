param(
    [string]$Sp500Csv = "",
    [string]$OutputFile = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-ProjectRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Get-RequiredPath {
    param([string]$PathValue)

    if (-not (Test-Path -LiteralPath $PathValue)) {
        throw "No se encontro el archivo requerido: $PathValue"
    }

    return (Resolve-Path $PathValue).Path
}

function Get-Sp500Dates {
    param([string]$CsvPath)

    $lines = Get-Content -LiteralPath $CsvPath -Encoding UTF8
    if ($lines.Count -lt 4) {
        throw "El archivo no tiene el formato esperado: $CsvPath"
    }

    return $lines |
        Select-Object -Skip 3 |
        ForEach-Object { ($_ -split ",", 2)[0].Trim() } |
        Where-Object { $_ -match '^\d{4}-\d{2}-\d{2}$' } |
        Sort-Object -Unique
}

function Get-DateId {
    param([datetime]$DateValue)

    return $DateValue.ToString("yyyyMMdd")
}

function New-DateDimension {
    param([string[]]$Dates)

    foreach ($dateText in $Dates) {
        $dateValue = [datetime]::ParseExact(
            $dateText,
            "yyyy-MM-dd",
            [System.Globalization.CultureInfo]::InvariantCulture
        )

        $dayOfWeek = [int]$dateValue.DayOfWeek
        $mondayBasedDay = if ($dayOfWeek -eq 0) { 7 } else { $dayOfWeek }

        [PSCustomObject][ordered]@{
            date_id     = Get-DateId -DateValue $dateValue
            date        = $dateValue.ToString("yyyy-MM-dd")
            year        = $dateValue.Year
            quarter     = [int][Math]::Ceiling($dateValue.Month / 3.0)
            month       = $dateValue.Month
            day         = $dateValue.Day
            day_of_week = $mondayBasedDay
        }
    }
}

$projectRoot = Get-ProjectRoot
$resolvedSp500Csv = if ([string]::IsNullOrWhiteSpace($Sp500Csv)) {
    Join-Path $projectRoot "dataset\sp500_2022.csv"
}
else {
    $Sp500Csv
}

$resolvedOutputFile = if ([string]::IsNullOrWhiteSpace($OutputFile)) {
    Join-Path $projectRoot "artifacts\lakehouse\dimensions\dim_date.csv"
}
else {
    $OutputFile
}

$resolvedSp500Csv = Get-RequiredPath -PathValue $resolvedSp500Csv
$outputDirectory = Split-Path -Path $resolvedOutputFile -Parent

if (-not (Test-Path -LiteralPath $outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$sp500Dates = Get-Sp500Dates -CsvPath $resolvedSp500Csv
$dateDimension = New-DateDimension -Dates $sp500Dates

$dateDimension |
    Export-Csv -LiteralPath $resolvedOutputFile -NoTypeInformation -Encoding UTF8

Write-Host "dim_date generado en: $resolvedOutputFile"
