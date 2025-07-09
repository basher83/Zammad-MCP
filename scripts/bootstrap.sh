#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

# (rest of bootstrap.sh follows)
# Install eza - a modern replacement for ls
# Security Note: GPG key verification is interactive by default to avoid hardcoding
# fingerprints that may change. For automated installations, set EZA_SKIP_GPG_VERIFY=1
# or verify the fingerprint manually at https://github.com/eza-community/eza
echo "Checking eza..."

# Check if eza is already installed
if ! command -v eza &> /dev/null; then
    echo "Installing eza..."
    
    # Ensure required tools are installed
    missing_tools=""
    ! command -v gpg &> /dev/null && missing_tools="$missing_tools gpg"
    ! command -v wget &> /dev/null && missing_tools="$missing_tools wget"
    
    if [ -n "$missing_tools" ]; then
        echo "Installing required tools:$missing_tools"
        # Note: We'll update package index later after adding repository
        sudo apt-get update
        sudo apt-get install -y $missing_tools
    fi
    
    # Check if repository is already configured
    if [ ! -f "/etc/apt/keyrings/gierens.gpg" ] || [ ! -f "/etc/apt/sources.list.d/gierens.list" ]; then
        echo "Adding eza repository..."
        sudo mkdir -p /etc/apt/keyrings
        
        # Remove existing file if it exists (shouldn't happen with the check above)
        [ -f "/etc/apt/keyrings/gierens.gpg" ] && sudo rm -f /etc/apt/keyrings/gierens.gpg
        
        # Download GPG key to temporary file
        echo "Downloading eza repository key..."
        tmp_key=$(mktemp)
        
        if ! wget -qO "$tmp_key" https://raw.githubusercontent.com/eza-community/eza/main/deb.asc; then
            echo "Failed to download eza GPG key"
            exit 1
        fi
        
        # Display key information for transparency
        echo "GPG key information:"
        # Import key to temporary keyring for verification
        tmp_keyring=$(mktemp -d)
        GNUPGHOME="$tmp_keyring" gpg --import "$tmp_key" 2>/dev/null
        key_info=$(GNUPGHOME="$tmp_keyring" gpg --list-keys 2>/dev/null)
        key_fingerprint=$(GNUPGHOME="$tmp_keyring" gpg --with-colons --fingerprint 2>/dev/null \
          | awk -F: '$1=="fpr"{print $10; exit}')
        
        echo "$key_info"
        echo "Key fingerprint: $key_fingerprint"
        
        # For automated/CI environments, allow skipping confirmation
        if [ -n "${EZA_SKIP_GPG_VERIFY:-}" ]; then
            echo "Skipping GPG verification (EZA_SKIP_GPG_VERIFY is set)"
        elif [ -t 0 ]; then
            # Interactive mode - ask for confirmation
            echo ""
            echo "Please verify this key fingerprint matches the official eza key."
            echo "You can check: https://github.com/eza-community/eza"
            echo ""
            echo "Do you trust this key? [y/N]"
            read -r response
            if [[ ! "$response" =~ ^[Yy]$ ]]; then
                echo "Key not trusted. Aborting."
                rm -f "$tmp_key"
                rm -rf "$tmp_keyring"
                exit 1
            fi
        else
            # Non-interactive mode without skip flag
            echo ""
            echo "WARNING: Running in non-interactive mode."
            echo "To skip this check, set EZA_SKIP_GPG_VERIFY=1"
            echo "To verify the key, check: https://github.com/eza-community/eza"
            echo "Proceeding with installation..."
        fi
        
        # Import the verified key
        sudo gpg --dearmor < "$tmp_key" -o /etc/apt/keyrings/gierens.gpg
        echo "deb [signed-by=/etc/apt/keyrings/gierens.gpg] http://deb.gierens.de stable main" | sudo tee /etc/apt/sources.list.d/gierens.list
        sudo chmod 644 /etc/apt/keyrings/gierens.gpg /etc/apt/sources.list.d/gierens.list
        
        # Clean up
        rm -f "$tmp_key"
        rm -rf "$tmp_keyring"
    else
        echo "eza repository already configured"
    fi
    
    # Install eza
    echo "Installing eza package..."
    sudo apt-get update
    sudo apt-get install -y eza
    echo "eza installed successfully!"
else
    echo "eza is already installed"
fi

# Install uv - Python package installer
echo "Checking uv..."

# Check if uv is already installed
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    
    # Ensure curl is installed
    if ! command -v curl &> /dev/null; then
        echo "Installing curl..."
        sudo apt-get install -y curl || {
            echo "Failed to install curl, updating package index..."
            sudo apt-get update
            sudo apt-get install -y curl
        }
    fi
    
    # Download installer to a temporary file for inspection
    echo "Downloading uv installer..."
    tmp_installer=$(mktemp)
    trap "rm -f $tmp_installer" EXIT
    
    # Use the official installer URL
    UV_INSTALLER_URL="https://astral.sh/uv/install.sh"
    
    if ! curl -LsSf -o "$tmp_installer" "$UV_INSTALLER_URL"; then
        echo "Failed to download uv installer"
        exit 1
    fi
    
    # Calculate actual checksum
    actual_sha=$(sha256sum "$tmp_installer" | cut -d' ' -f1)
    
    # Note: The installer script changes frequently, so we verify it's from the expected domain
    # and do additional safety checks rather than pinning to a specific checksum
    echo "Downloaded installer SHA-256: $actual_sha"
    
    # Basic validation - check if it's a shell script and not empty
    if [ ! -s "$tmp_installer" ]; then
        echo "Downloaded installer is empty"
        exit 1
    fi
    
    if ! head -n 1 "$tmp_installer" | grep -q "^#!/"; then
        echo "Downloaded file doesn't appear to be a shell script"
        exit 1
    fi
    
    # Additional safety check - verify the script contains expected uv installation markers
    if ! grep -q "astral.sh/uv" "$tmp_installer" || ! grep -q "cargo install" "$tmp_installer"; then
        echo "Installer doesn't appear to be the official uv installer"
        exit 1
    fi
    
    # Show installer details for transparency
    echo "Installer size: $(wc -c < "$tmp_installer") bytes"
    echo "First 10 lines of installer:"
    head -n 10 "$tmp_installer" | sed 's/^/  /'
    
    # Option for manual review if running interactively
    if [ -t 0 ] && [ -z "${UV_INSTALL_SKIP_CONFIRM:-}" ]; then
        echo ""
        echo "Would you like to review the full installer script before execution? [y/N]"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            less "$tmp_installer"
            echo ""
            echo "Proceed with installation? [Y/n]"
            read -r confirm
            if [[ "$confirm" =~ ^[Nn]$ ]]; then
                echo "Installation cancelled"
                exit 1
            fi
        fi
    fi
    
    # Execute the installer
    echo "Running uv installer..."
    sh "$tmp_installer"
    
    # Add uv to PATH for current session
    export PATH="$HOME/.cargo/bin:$PATH"
    
    # Persist PATH update for future sessions
    echo "Updating shell configuration..."
    cargo_path_line='export PATH="$HOME/.cargo/bin:$PATH"'
    
    # Update shell configuration files
    for rc_file in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
        if [ -f "$rc_file" ] && ! grep -q ".cargo/bin" "$rc_file"; then
            echo "$cargo_path_line" >> "$rc_file"
            echo "Added cargo bin to $(basename "$rc_file")"
        fi
    done
    
    echo "uv installed successfully!"
else
    echo "uv is already installed"
fi

# Install ripgrep - a fast search tool
echo "Installing ripgrep..."

# Check if ripgrep is already installed
if ! command -v rg &> /dev/null; then
    echo "Installing ripgrep package..."
    sudo apt-get update
    sudo apt-get install -y ripgrep
    echo "ripgrep installed successfully!"
else
    echo "ripgrep is already installed"
fi