param(
  [Parameter(Mandatory=$true)][string]$Command,
  [Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments
)
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
python "$PSScriptRoot\..\stilometry.py" $Command @Arguments
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
