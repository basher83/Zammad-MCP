# Quick setup script for Zammad MCP server with uv on Windows

Write-Host "Setting up Zammad MCP Server..." -ForegroundColor Green

# Check if uv is installed
try {
    $null = Get-Command uv -ErrorAction Stop
} catch {
    Write-Host "Installing uv..." -ForegroundColor Yellow
    Write-Host "This will download and execute uv installer from https://astral.sh/uv/install.ps1" -ForegroundColor Yellow
    $confirmation = Read-Host "Continue? (y/N)"
    if ($confirmation -eq 'y' -or $confirmation -eq 'Y') {
        Invoke-WebRequest -Uri "https://astral.sh/uv/install.ps1" | Invoke-Expression
        Write-Host ""
        Write-Host "Note: PATH may need to be updated for uv to work in new terminals." -ForegroundColor Yellow
        Write-Host "The installer should have updated your PATH automatically." -ForegroundColor DarkGray
    } else {
        Write-Host "Installation cancelled. Please install uv manually." -ForegroundColor Red
        exit 1
    }
}

# Create virtual environment
Write-Host "Creating virtual environment..." -ForegroundColor Yellow
uv venv

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\.venv\Scripts\activate

# Install dependencies
Write-Host "Installing dependencies..." -ForegroundColor Yellow
uv pip install -e ".[dev]"

# Copy .env.example if .env doesn't exist
if (!(Test-Path .env)) {
    Write-Host "Creating .env file from template..." -ForegroundColor Yellow
    Copy-Item .env.example .env
    Write-Host "Please edit .env file with your Zammad credentials" -ForegroundColor Red
}

Write-Host ""
Write-Host "Setup complete! To start using the server:" -ForegroundColor Green
Write-Host "1. Edit .env file with your Zammad credentials"
Write-Host "2. Activate the virtual environment: .\.venv\Scripts\activate"
Write-Host "3. Run the server: python -m mcp_zammad"