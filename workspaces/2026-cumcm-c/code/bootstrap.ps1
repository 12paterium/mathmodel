param()

$ErrorActionPreference = "Stop"
$CodeRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$VendorRoot = Join-Path $CodeRoot "_vendor"
$Requirements = Join-Path $CodeRoot "requirements.txt"

New-Item -ItemType Directory -Force -Path $VendorRoot | Out-Null

uv pip install `
    --python 3.10 `
    --target $VendorRoot `
    --no-cache `
    --requirements $Requirements

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "Environment ready in $VendorRoot"
