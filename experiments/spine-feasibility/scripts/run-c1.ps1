$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..'))
node --version
npm.cmd ci
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
npm.cmd run c1:test
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
npm.cmd run c1:preflight
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
npm.cmd run c1:render
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
npm.cmd run c1:verify
exit $LASTEXITCODE
