param(
    [string]$PythonVersion = '3.12',
    [switch]$SkipFrontend
)

$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$BackendDir = Join-Path $ProjectRoot 'backend'
$BackendVenv = Join-Path $BackendDir '.venv'
$BackendRequirements = Join-Path $BackendDir 'requirements.txt'
$FrontendDir = Join-Path $ProjectRoot 'hot_engine'

function Assert-CommandExists {
    param([string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found in PATH: $Name"
    }
}

Assert-CommandExists 'uv'
Assert-CommandExists 'npm'

if (Test-Path $BackendVenv) {
    Remove-Item -Recurse -Force $BackendVenv
}

Write-Host "Creating backend venv with Python $PythonVersion..."
& uv venv --python $PythonVersion $BackendVenv

$BackendPython = Join-Path $BackendVenv 'Scripts\python.exe'

Write-Host 'Installing backend requirements...'
& uv pip install --python $BackendPython -r $BackendRequirements

if (-not $SkipFrontend) {
    Write-Host 'Installing frontend dependencies...'
    Push-Location $FrontendDir
    try {
        & npm install
    }
    finally {
        Pop-Location
    }
}

$MissingMediaTools = @()
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    $MissingMediaTools += 'ffmpeg'
}
if (-not (Get-Command ffprobe -ErrorAction SilentlyContinue)) {
    $MissingMediaTools += 'ffprobe'
}

if ($MissingMediaTools.Count -gt 0) {
    Write-Warning ("Missing external tool(s) on PATH: {0}. Backend video upload/metadata flow will fail until they are installed." -f ($MissingMediaTools -join ', '))
}

Write-Host ''
Write-Host 'Rebuild finished.'
Write-Host "Backend Python: $BackendPython"
Write-Host 'Backend start:'
Write-Host '  backend\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload'
Write-Host 'Frontend start:'
Write-Host '  cd hot_engine; npm run dev'