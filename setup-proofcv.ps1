$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

$systemPython = Get-Command python -ErrorAction SilentlyContinue
if (-not $systemPython) {
    throw 'Python 3.12 or 3.13 is required. Install Python, reopen PowerShell, then run this script again.'
}

$detectedPython = (& $systemPython.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
if ($LASTEXITCODE -ne 0 -or $detectedPython -notin @('3.12', '3.13')) {
    throw "Python 3.12 or 3.13 is required. Detected Python $detectedPython. Install a supported version and ensure 'python' resolves to it."
}
Write-Host "Using supported Python $detectedPython."

$proofPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $proofPython)) {
    Write-Host 'Creating the local Python environment...'
    & $systemPython.Source -m venv .venv
}

Write-Host 'Installing the pinned Python dependencies...'
& $proofPython -m pip install -r requirements.txt

$privateConfig = Join-Path $PSScriptRoot '.env'
if (-not (Test-Path -LiteralPath $privateConfig)) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot '.env.example') -Destination $privateConfig
    Write-Host 'Created .env with a blank GEMINI_API_KEY.'
} else {
    Write-Host 'Existing .env preserved.'
}

Write-Host ''
Write-Host 'Setup complete. Add your own API key after GEMINI_API_KEY= in .env.'
Write-Host 'Then run: .\start-proofcv.ps1'
