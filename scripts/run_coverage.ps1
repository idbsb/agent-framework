$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

function Assert-LastExitCode([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python virtual environment not found. Create .venv and install requirements-dev.txt first."
}

Push-Location $projectRoot
try {
    New-Item -ItemType Directory -Force -Path "reports\coverage" | Out-Null
    & $python -m coverage erase
    Assert-LastExitCode "coverage erase"
    & $python -m coverage run -m unittest discover -s tests -p "test_*.py" -v
    Assert-LastExitCode "Python tests"
    & $python -m coverage report
    Assert-LastExitCode "coverage threshold"
    & $python -m coverage html
    Assert-LastExitCode "coverage HTML"
    & $python -m coverage xml
    Assert-LastExitCode "coverage XML"
    & $python -m coverage json
    Assert-LastExitCode "coverage JSON"

    Push-Location "frontend"
    try {
        npm run test:coverage
        Assert-LastExitCode "frontend coverage"
    }
    finally {
        Pop-Location
    }
}
finally {
    Pop-Location
}
