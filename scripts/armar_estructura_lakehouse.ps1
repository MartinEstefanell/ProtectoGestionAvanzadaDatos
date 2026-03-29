param(
    [string]$DatasetDir = "",
    [string]$LakehouseDir = "",
    [string]$DimDateFile = ""
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

function Ensure-Directory {
    param([string]$PathValue)

    if (-not (Test-Path -LiteralPath $PathValue)) {
        New-Item -ItemType Directory -Path $PathValue -Force | Out-Null
    }
}

$projectRoot = Get-ProjectRoot
$resolvedLakehouseDir = if ([string]::IsNullOrWhiteSpace($LakehouseDir)) {
    Join-Path $projectRoot "artifacts\lakehouse"
}
else {
    $LakehouseDir
}

$resolvedDatasetDir = if ([string]::IsNullOrWhiteSpace($DatasetDir)) {
    Join-Path $projectRoot "dataset"
}
else {
    $DatasetDir
}

$resolvedDimDateFile = if ([string]::IsNullOrWhiteSpace($DimDateFile)) {
    Join-Path $resolvedLakehouseDir "dimensions\dim_date.csv"
}
else {
    $DimDateFile
}

$sp500Source = Get-RequiredPath -PathValue (Join-Path $resolvedDatasetDir "sp500_2022.csv")
$eventSource = Get-RequiredPath -PathValue (Join-Path $resolvedDatasetDir "events_2022.csv")
$eventAuditSource = Get-RequiredPath -PathValue (Join-Path $resolvedDatasetDir "events_audit_2022.csv")
$resolvedDimDateFile = Get-RequiredPath -PathValue $resolvedDimDateFile

$rawSp500Dir = Join-Path $resolvedLakehouseDir "raw\sp500"
$rawEventDir = Join-Path $resolvedLakehouseDir "raw\event"
$rawEventAuditDir = Join-Path $resolvedLakehouseDir "raw\event_audit"
$dimensionsDir = Join-Path $resolvedLakehouseDir "dimensions"
$curatedSp500Dir = Join-Path $resolvedLakehouseDir "curated\sp500_clean"
$curatedEventDir = Join-Path $resolvedLakehouseDir "curated\event_clean"
$curatedEventAuditDir = Join-Path $resolvedLakehouseDir "curated\event_audit_clean"

Ensure-Directory -PathValue $rawSp500Dir
Ensure-Directory -PathValue $rawEventDir
Ensure-Directory -PathValue $rawEventAuditDir
Ensure-Directory -PathValue $dimensionsDir
Ensure-Directory -PathValue $curatedSp500Dir
Ensure-Directory -PathValue $curatedEventDir
Ensure-Directory -PathValue $curatedEventAuditDir

Copy-Item -LiteralPath $sp500Source -Destination (Join-Path $rawSp500Dir "sp500_2022.csv") -Force
Copy-Item -LiteralPath $eventSource -Destination (Join-Path $rawEventDir "events_2022.csv") -Force
Copy-Item -LiteralPath $eventAuditSource -Destination (Join-Path $rawEventAuditDir "events_audit_2022.csv") -Force

$targetDimDate = Join-Path $dimensionsDir "dim_date.csv"
$resolvedDimDatePath = (Resolve-Path $resolvedDimDateFile).Path
if ($resolvedDimDatePath -ne $targetDimDate) {
    Copy-Item -LiteralPath $resolvedDimDateFile -Destination $targetDimDate -Force
}

Write-Host "Estructura local lista en: $resolvedLakehouseDir"
Write-Host "Incluye:"
Write-Host "  raw/sp500/sp500_2022.csv"
Write-Host "  raw/event/events_2022.csv"
Write-Host "  raw/event_audit/events_audit_2022.csv"
Write-Host "  dimensions/dim_date.csv"
Write-Host "  curated/sp500_clean/"
Write-Host "  curated/event_clean/"
Write-Host "  curated/event_audit_clean/"
