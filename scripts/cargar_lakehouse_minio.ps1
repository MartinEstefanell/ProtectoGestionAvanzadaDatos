param(
    [string]$BucketName = "lakehouse",
    [string]$LakehouseDir = "",
    [string]$MinioContainer = "minio",
    [string]$MinioAlias = "myminio",
    [string]$MinioEndpoint = "http://localhost:9000",
    [string]$AccessKey = "admin",
    [string]$SecretKey = "password",
    [switch]$ResetBucket
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-ProjectRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Ensure-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker no esta disponible en la terminal actual."
    }

    & docker version --format "{{.Server.Version}}" *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker esta instalado, pero la terminal actual no puede acceder al daemon. Ejecuta el script en una PowerShell con permisos para Docker."
    }
}

function Get-RequiredPath {
    param([string]$PathValue)

    if (-not (Test-Path -LiteralPath $PathValue)) {
        throw "No se encontro la ruta requerida: $PathValue"
    }

    return (Resolve-Path $PathValue).Path
}

function Invoke-Docker {
    param([string[]]$Arguments)

    & docker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Fallo el comando docker: docker $($Arguments -join ' ')"
    }
}

function Publish-ToMinio {
    param(
        [string]$LocalRoot,
        [string]$ContainerName,
        [string]$AliasName,
        [string]$Endpoint,
        [string]$Bucket,
        [string]$Key,
        [string]$Secret,
        [bool]$ShouldResetBucket
    )

    $containerSeedRoot = "/tmp/lakehouse_seed"
    $resetCommand = if ($ShouldResetBucket) {
        "mc rb --force $AliasName/$Bucket >/dev/null 2>&1 || true; "
    }
    else {
        ""
    }

    Invoke-Docker -Arguments @(
        "exec",
        $ContainerName,
        "sh",
        "-c",
        "mc alias set $AliasName $Endpoint $Key $Secret >/dev/null 2>&1 && ${resetCommand}mc mb --ignore-existing $AliasName/$Bucket >/dev/null 2>&1 && rm -rf $containerSeedRoot && mkdir -p $containerSeedRoot"
    )

    Invoke-Docker -Arguments @(
        "cp",
        (Join-Path $LocalRoot "."),
        "${ContainerName}:$containerSeedRoot"
    )

    Invoke-Docker -Arguments @(
        "exec",
        $ContainerName,
        "sh",
        "-c",
        @"
mc alias set $AliasName $Endpoint $Key $Secret >/dev/null 2>&1 &&
mc mirror --overwrite $containerSeedRoot $AliasName/$Bucket >/dev/null &&
mc pipe $AliasName/$Bucket/curated/sp500_clean/ < /dev/null >/dev/null &&
mc pipe $AliasName/$Bucket/curated/event_clean/ < /dev/null >/dev/null &&
mc pipe $AliasName/$Bucket/curated/event_audit_clean/ < /dev/null >/dev/null &&
rm -rf $containerSeedRoot
"@
    )
}

$projectRoot = Get-ProjectRoot
$resolvedLakehouseDir = if ([string]::IsNullOrWhiteSpace($LakehouseDir)) {
    Join-Path $projectRoot "artifacts\lakehouse"
}
else {
    $LakehouseDir
}

Ensure-Docker
$resolvedLakehouseDir = Get-RequiredPath -PathValue $resolvedLakehouseDir
Get-RequiredPath -PathValue (Join-Path $resolvedLakehouseDir "raw\sp500\sp500_2022.csv") | Out-Null
Get-RequiredPath -PathValue (Join-Path $resolvedLakehouseDir "raw\event\events_2022.csv") | Out-Null
Get-RequiredPath -PathValue (Join-Path $resolvedLakehouseDir "raw\event_audit\events_audit_2022.csv") | Out-Null
Get-RequiredPath -PathValue (Join-Path $resolvedLakehouseDir "dimensions\dim_date.csv") | Out-Null

Publish-ToMinio `
    -LocalRoot $resolvedLakehouseDir `
    -ContainerName $MinioContainer `
    -AliasName $MinioAlias `
    -Endpoint $MinioEndpoint `
    -Bucket $BucketName `
    -Key $AccessKey `
    -Secret $SecretKey `
    -ShouldResetBucket $ResetBucket.IsPresent

Write-Host "Bucket creado o actualizado: $BucketName"
Write-Host "Objetos sincronizados desde: $resolvedLakehouseDir"
Write-Host "Si quieres borrar objetos viejos del bucket, ejecuta este script con -ResetBucket."
