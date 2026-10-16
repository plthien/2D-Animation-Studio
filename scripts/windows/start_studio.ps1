param([ValidateRange(0,120)][int]$SmokeTestSeconds = 0)
# Windows-only animation application launcher. No legacy hosts and no paid calls.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Push-Location $root
$api = $null
$ui = $null
try {
  if (-not [Environment]::OSVersion.Platform.Equals([PlatformID]::Win32NT)) {
    throw '2D Animation Studio requires Windows.'
  }
  $venvPython = Join-Path $root '.venv\Scripts\python.exe'
  if (-not (Test-Path $venvPython)) {
    & py -3.12 -m venv (Join-Path $root '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 environment creation failed.' }
  }
  & $venvPython -c 'import sys; assert sys.version_info[:2] == (3, 12)'
  if ($LASTEXITCODE -ne 0) { throw 'The Python virtual environment must use Python 3.12.' }
  $requirementHash = (Get-FileHash (Join-Path $root 'requirements.txt') -Algorithm SHA256).Hash
  $requirementStamp = Join-Path $root '.venv\.animation-requirements.sha256'
  $previousRequirementHash = if (Test-Path $requirementStamp) { (Get-Content $requirementStamp -Raw).Trim() } else { '' }
  if ($requirementHash -ne $previousRequirementHash) {
    & $venvPython -m pip install -r (Join-Path $root 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
    Set-Content -Path $requirementStamp -Value $requirementHash -NoNewline -Encoding ASCII
  }
  $nodeVersion = (& node --version).Trim()
  if ($nodeVersion -notmatch '^v22\.') { throw "Node.js 22 required; found $nodeVersion" }
  $npmHash = (Get-FileHash (Join-Path $root 'package-lock.json') -Algorithm SHA256).Hash
  $npmStamp = Join-Path $root 'node_modules\.animation-lock.sha256'
  $previousNpmHash = if (Test-Path $npmStamp) { (Get-Content $npmStamp -Raw).Trim() } else { '' }
  if (-not (Test-Path (Join-Path $root 'node_modules')) -or $npmHash -ne $previousNpmHash) {
    & npm.cmd ci --ignore-scripts
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    Set-Content -Path $npmStamp -Value $npmHash -NoNewline -Encoding ASCII
  }
  $env:APP_NAME = '2D Animation Studio'
  if (-not $env:DATABASE_URL) { $env:DATABASE_URL = 'sqlite:///./2d_animation_studio.db' }
  if (-not $env:ARTIFACT_ROOT) { $env:ARTIFACT_ROOT = './local_artifacts' }
  $env:HOST = '127.0.0.1'
  $env:API_PORT = '8000'
  $env:FRONTEND_PORT = '5173'
  $env:AUTO_APPLY_MIGRATIONS = 'true'
  & $venvPython -m alembic upgrade head
  if ($LASTEXITCODE -ne 0) { throw 'Animation database migration refused or failed. Existing data was not deleted.' }
  Write-Host 'Starting 2D Animation Studio API and Cockpit (local-only).'
  $api = Start-Process -FilePath $venvPython -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $root -PassThru -NoNewWindow
  $ui = Start-Process -FilePath 'cmd.exe' -ArgumentList @('/d','/c','npm.cmd run dev -- --host 127.0.0.1') -WorkingDirectory $root -PassThru -NoNewWindow
  Write-Host 'Open http://127.0.0.1:5173. Press Ctrl+C to stop both owned process trees.'
  $started = Get-Date
  while ($true) {
    Start-Sleep -Seconds 2
    $api.Refresh()
    $ui.Refresh()
    if ($api.HasExited) { throw "Animation API stopped unexpectedly (exit $($api.ExitCode))." }
    if ($ui.HasExited) { throw "Cockpit frontend stopped unexpectedly (exit $($ui.ExitCode))." }
    if ($SmokeTestSeconds -gt 0 -and ((Get-Date) - $started).TotalSeconds -ge $SmokeTestSeconds) {
      Write-Host 'Smoke run completed; stopping both owned service trees.'
      break
    }
  }
}
catch {
  Write-Error "Studio startup/runtime failed: $($_.Exception.Message)"
  exit 1
}
finally {
  foreach ($p in @($ui,$api)) {
    if ($null -ne $p) {
      try { & taskkill.exe /PID $p.Id /T /F 2>$null | Out-Null } catch {}
    }
  }
  Pop-Location
}
