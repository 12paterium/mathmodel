param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Script,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ScriptArguments
)

$ErrorActionPreference = "Stop"
$CodeRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$VendorRoot = Join-Path $CodeRoot "_vendor"

if (-not (Test-Path -LiteralPath $VendorRoot)) {
    throw "Dependency directory is missing. Run code/bootstrap.ps1 first."
}

$env:MPLCONFIGDIR = $env:TEMP
$env:PYTHONPATH = if ($env:PYTHONPATH) {
    "$VendorRoot;$env:PYTHONPATH"
} else {
    $VendorRoot
}

$PythonOutput = uv --no-cache python find 3.10
if ($LASTEXITCODE -ne 0 -or -not $PythonOutput) {
    throw "Unable to locate UV-managed CPython 3.10."
}
$PythonPath = ([string]($PythonOutput | Select-Object -First 1)).Trim()

& $PythonPath $Script @ScriptArguments
exit $LASTEXITCODE
