param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Args
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$bundledPython = Join-Path $repoRoot "..\.tools\python313\python.exe"

if (Test-Path -LiteralPath $bundledPython) {
  $python = (Resolve-Path -LiteralPath $bundledPython).Path
} else {
  $python = (Get-Command python -ErrorAction Stop).Source
}

Write-Host "Using Python: $python"
& $python (Join-Path $PSScriptRoot "check_camunda_all.py") @Args
exit $LASTEXITCODE
