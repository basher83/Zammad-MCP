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
        # Parse fingerprint using --with-colons for machine-readable output
        # The 'fpr' record contains the fingerprint in field 10
        # Use grep and cut for more predictable parsing
        key_fingerprint=$(GNUPGHOME="$tmp_keyring" gpg --with-colons --fingerprint 2>/dev/null \
          | grep "^fpr:" | head -1 | cut -d: -f10)
        
        # Validate fingerprint format (should be 40 hex characters for GPG keys)
        # Modern GPG keys use SHA1 (40 chars) or SHA256 (64 chars) for fingerprints
        # We check for 40 as that's most common, but could extend to support 64
        if [[ ! "$key_fingerprint" =~ ^[A-F0-9]{40}$ ]]; then
            # Try uppercase conversion in case of lowercase hex
            key_fingerprint_upper=$(echo "$key_fingerprint" | tr '[:lower:]' '[:upper:]')
            if [[ ! "$key_fingerprint_upper" =~ ^[A-F0-9]{40}$ ]]; then
                echo "Warning: Invalid or missing key fingerprint"
                echo "Expected 40 character hex string, got: '$key_fingerprint'"
                echo "GPG output format may have changed or locale settings may affect parsing"
                echo "Proceeding with key display for manual verification"
                key_fingerprint=""
            else
                key_fingerprint="$key_fingerprint_upper"
            fi
        fi
        
        echo "$key_info"
        if [ -n "$key_fingerprint" ]; then
            echo "Key fingerprint: $key_fingerprint"
        fi
        
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

# Function to check if ~/.local/bin is in PATH and provide instructions
check_local_bin_path() {
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        echo ""
        echo "NOTE: $HOME/.local/bin is not in your PATH."
        echo "Add the following to your shell configuration file (.bashrc, .zshrc, etc.):"
        echo '  export PATH="$HOME/.local/bin:$PATH"'
        echo ""
        echo "For the current session, run:"
        echo '  export PATH="$HOME/.local/bin:$PATH"'
    fi
}

# Function to create fd symlink safely
create_fd_symlink() {
    local target=$(which fdfind)
    local link="$HOME/.local/bin/fd"
    
    mkdir -p "$HOME/.local/bin"
    
    # Check if fd already exists and handle appropriately
    if [ -e "$link" ] || [ -L "$link" ]; then
        # Check if it's already the correct symlink
        if [ -L "$link" ] && [ "$(readlink "$link")" = "$target" ]; then
            echo "Symlink already correctly configured"
        else
            echo "Removing existing fd file/symlink"
            rm -f "$link"
            ln -nsf "$target" "$link"
            echo "Created symlink: fd -> $target"
        fi
    else
        ln -nsf "$target" "$link"
        echo "Created symlink: fd -> $target"
    fi
}

# Install fd-find - a modern replacement for find
echo "Checking fd..."

# Check if fd is already available (either as fd or fdfind)
if ! command -v fd &> /dev/null && ! command -v fdfind &> /dev/null; then
    echo "Installing fd-find..."
    
    # Install fd-find package
    sudo apt-get update
    sudo apt-get install -y fd-find
    echo "fd-find installed successfully!"
    
    # Create symlink for fd command
    echo "Setting up fd symlink..."
    create_fd_symlink
    
    # Check if ~/.local/bin is in PATH
    check_local_bin_path
else
    # Check if we have fd command specifically
    if command -v fdfind &> /dev/null && ! command -v fd &> /dev/null; then
        echo "fd-find is installed but 'fd' command not available"
        echo "Creating fd symlink..."
        create_fd_symlink
        
        # Check PATH again
        check_local_bin_path
    else
        echo "fd is already installed and available"
    fi
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