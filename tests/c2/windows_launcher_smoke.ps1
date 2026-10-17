param([string]$Repository = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path)
$ErrorActionPreference = 'Stop'
$temporary = Join-Path $env:TEMP ('C2 Animation Path With Spaces ' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temporary -Force | Out-Null
$includedDirectories = @('app','alembic','contracts','scripts','src')
$includedFiles = @('requirements.txt','alembic.ini','package.json','package-lock.json','vite.config.ts','tsconfig.json','postcss.config.js','tailwind.config.js','index.html','start.bat')
try {
  foreach($dir in $includedDirectories) {
    Copy-Item -LiteralPath (Join-Path $Repository $dir) -Destination (Join-Path $temporary $dir) -Recurse -Force
  }
  foreach($file in $includedFiles) {
    Copy-Item -LiteralPath (Join-Path $Repository $file) -Destination (Join-Path $temporary $file) -Force
  }
  Push-Location $temporary
  try {
    $env:DATABASE_URL = 'sqlite:///./disposable_c2.sqlite'
    $env:ARTIFACT_ROOT = './disposable_artifacts'
    & "$temporary\start.bat" -SmokeTestSeconds 6
    if ($LASTEXITCODE -ne 0) { throw "Studio launcher failed with exit $LASTEXITCODE" }
    if (-not (Test-Path (Join-Path $temporary 'disposable_c2.sqlite'))) { throw 'Launcher did not migrate SQLite' }
    if (Test-Path (Join-Path $temporary 'youtube_ai_studio_v3.db')) { throw 'Legacy database created' }
    if (Test-Path (Join-Path $temporary '.venv\.yas3_requirements.sha256')) { throw 'Old process stamp created' }
    if (Test-Path (Join-Path $temporary 'node_modules\.yas3_package_lock.sha256')) { throw 'Old npm stamp created' }
    Write-Host 'C2 real Windows launcher spaces/first-run/stop PASS'
  } finally {Pop-Location}
} finally {
  Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
  Remove-Item Env:ARTIFACT_ROOT -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $temporary -Recurse -Force -ErrorAction SilentlyContinue
}
