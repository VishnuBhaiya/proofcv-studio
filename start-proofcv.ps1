$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$proofPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $proofPython)) {
    throw 'This project needs its own .venv. Run: python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt'
}
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'dist\index.html'))) {
    throw 'The included dist build is missing. Re-extract the official submission ZIP, or install Node.js and pnpm, then run pnpm install --frozen-lockfile; pnpm run build.'
}
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'portfolio-runtime\portfolio.js'))) {
    throw 'The included portfolio runtime is missing. Restore portfolio-runtime from main, or run pnpm run build.'
}
Write-Host 'Open http://127.0.0.1:8000 in your browser. Press Ctrl+C to stop.'
& $proofPython -m server.http
