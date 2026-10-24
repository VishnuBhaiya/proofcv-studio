$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$readerPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $readerPython)) { throw 'Run setup-proofcv.ps1 first.' }
Write-Host 'Read-only portfolio reader on http://127.0.0.1:8001. Press Ctrl+C to stop.'
Write-Host 'Enable an approved snapshot in Portfolio Studio, then use its connected website link.'
& $readerPython -m server.portfolio_reader
