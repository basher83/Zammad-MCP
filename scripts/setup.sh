#!/bin/bash
# Quick setup script for Zammad MCP server with uv

set -euo pipefail

echo "Setting up Zammad MCP Server..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    
    # Add uv to PATH for this session
    export PATH="$HOME/.cargo/bin:$PATH"
    echo ""
    echo "Note: PATH updated for current session only."
    echo "Add ~/.cargo/bin to your shell's PATH permanently."
fi

# Create virtual environment
echo "Creating virtual environment..."
uv venv

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
uv pip install -e ".[dev]"

# Copy .env.example if .env doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "Please edit .env file with your Zammad credentials"
fi

echo ""
echo "Setup complete! To start using the server:"
echo "1. Edit .env file with your Zammad credentials"
echo "2. Activate the virtual environment: source .venv/bin/activate"
echo "3. Run the server: python -m mcp_zammad"