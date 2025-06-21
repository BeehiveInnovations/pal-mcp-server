#!/bin/bash
set -euo pipefail

# ============================================================================
# Zen MCP Server Setup Script
# 
# A platform-agnostic setup script that works on macOS, Linux, and WSL.
# Handles environment setup, dependency installation, and configuration.
# ============================================================================

# ----------------------------------------------------------------------------
# Constants and Configuration
# ----------------------------------------------------------------------------

# Colors for output (ANSI codes work on all platforms)
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly RED='\033[0;31m'
readonly NC='\033[0m' # No Color

# Configuration
readonly VENV_PATH=".zen_venv"
readonly DOCKER_CLEANED_FLAG=".docker_cleaned"
readonly DESKTOP_CONFIG_FLAG=".desktop_configured"
readonly LOG_DIR="logs"
readonly LOG_FILE="mcp_server.log"

# ----------------------------------------------------------------------------
# Utility Functions
# ----------------------------------------------------------------------------

# Print colored output
print_success() {
    echo -e "${GREEN}✓${NC} $1" >&2
}

print_error() {
    echo -e "${RED}✗${NC} $1" >&2
}

print_warning() {
    echo -e "${YELLOW}!${NC} $1" >&2
}

print_info() {
    echo -e "${YELLOW}$1${NC}" >&2
}

# Get the script's directory (works on all platforms)
get_script_dir() {
    cd "$(dirname "$0")" && pwd
}

# Extract version from config.py
get_version() {
    grep -E '^__version__ = ' config.py 2>/dev/null | sed 's/__version__ = "\(.*\)"/\1/' || echo "unknown"
}

# Clear Python cache files to prevent import issues
clear_python_cache() {
    print_info "Clearing Python cache files..."
    find . -name "*.pyc" -delete 2>/dev/null || true
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    print_success "Python cache cleared"
}

# ----------------------------------------------------------------------------
# Platform Detection Functions
# ----------------------------------------------------------------------------

# Detect the operating system
detect_os() {
    case "$OSTYPE" in
        darwin*)  echo "macos" ;;
        linux*)   
            if grep -qi microsoft /proc/version 2>/dev/null; then
                echo "wsl"
            else
                echo "linux"
            fi
            ;;
        msys*|cygwin*|win32) echo "windows" ;;
        *)        echo "unknown" ;;
    esac
}

# Get Claude config path based on platform
get_claude_config_path() {
    local os_type=$(detect_os)
    
    case "$os_type" in
        macos)
            echo "$HOME/Library/Application Support/Claude/claude_desktop_config.json"
            ;;
        linux)
            echo "$HOME/.config/Claude/claude_desktop_config.json"
            ;;
        wsl)
            echo "/mnt/c/Users/$USER/AppData/Roaming/Claude/claude_desktop_config.json"
            ;;
        windows)
            echo "$APPDATA/Claude/claude_desktop_config.json"
            ;;
        *)
            echo ""
            ;;
    esac
}

# ----------------------------------------------------------------------------
# Docker Cleanup Functions
# ----------------------------------------------------------------------------

# Clean up old Docker artifacts
cleanup_docker() {
    # Skip if already cleaned or Docker not available
    [[ -f "$DOCKER_CLEANED_FLAG" ]] && return 0
    
    if ! command -v docker &> /dev/null || ! docker info &> /dev/null 2>&1; then
        return 0
    fi
    
    local found_artifacts=false
    
    # Define containers to remove
    local containers=(
        "gemini-mcp-server"
        "gemini-mcp-redis"
        "zen-mcp-server"
        "zen-mcp-redis"
        "zen-mcp-log-monitor"
    )
    
    # Remove containers
    for container in "${containers[@]}"; do
        if docker ps -a --format "{{.Names}}" | grep -q "^${container}$" 2>/dev/null; then
            if [[ "$found_artifacts" == false ]]; then
                echo "One-time Docker cleanup..."
                found_artifacts=true
            fi
            echo "  Removing container: $container"
            docker stop "$container" >/dev/null 2>&1 || true
            docker rm "$container" >/dev/null 2>&1 || true
        fi
    done
    
    # Remove images
    local images=("gemini-mcp-server:latest" "zen-mcp-server:latest")
    for image in "${images[@]}"; do
        if docker images --format "{{.Repository}}:{{.Tag}}" | grep -q "^${image}$" 2>/dev/null; then
            if [[ "$found_artifacts" == false ]]; then
                echo "One-time Docker cleanup..."
                found_artifacts=true
            fi
            echo "  Removing image: $image"
            docker rmi "$image" >/dev/null 2>&1 || true
        fi
    done
    
    # Remove volumes
    local volumes=("redis_data" "mcp_logs")
    for volume in "${volumes[@]}"; do
        if docker volume ls --format "{{.Name}}" | grep -q "^${volume}$" 2>/dev/null; then
            if [[ "$found_artifacts" == false ]]; then
                echo "One-time Docker cleanup..."
                found_artifacts=true
            fi
            echo "  Removing volume: $volume"
            docker volume rm "$volume" >/dev/null 2>&1 || true
        fi
    done
    
    if [[ "$found_artifacts" == true ]]; then
        print_success "Docker cleanup complete"
    fi
    
    touch "$DOCKER_CLEANED_FLAG"
}

# ----------------------------------------------------------------------------
# Python Environment Functions
# ----------------------------------------------------------------------------

# Find suitable Python command
find_python() {
    # Prefer Python 3.12 for best compatibility
    local python_cmds=("python3.12" "python3.13" "python3.11" "python3.10" "python3" "python" "py")
    
    for cmd in "${python_cmds[@]}"; do
        if command -v "$cmd" &> /dev/null; then
            local version=$($cmd --version 2>&1)
            if [[ $version =~ Python\ 3\.([0-9]+)\.([0-9]+) ]]; then
                local major_version=${BASH_REMATCH[1]}
                local minor_version=${BASH_REMATCH[2]}
                
                # Check minimum version (3.10) for better library compatibility
                if [[ $major_version -ge 10 ]]; then
                    echo "$cmd"
                    print_success "Found Python: $version"
                    
                    # Recommend Python 3.12
                    if [[ $major_version -ne 12 ]]; then
                        print_info "Note: Python 3.12 is recommended for best compatibility."
                    fi
                    
                    return 0
                fi
            fi
        fi
    done
    
    print_error "Python 3.10+ not found. Please install Python 3.10 or newer (3.12 recommended)."
    return 1
}

# Detect Linux distribution
detect_linux_distro() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        echo "${ID:-unknown}"
    elif [[ -f /etc/debian_version ]]; then
        echo "debian"
    elif [[ -f /etc/redhat-release ]]; then
        echo "rhel"
    elif [[ -f /etc/arch-release ]]; then
        echo "arch"
    else
        echo "unknown"
    fi
}

# Get package manager and install command for the distro
get_install_command() {
    local distro="$1"
    local python_version="${2:-}"
    
    # Extract major.minor version if provided
    local version_suffix=""
    if [[ -n "$python_version" ]] && [[ "$python_version" =~ ([0-9]+\.[0-9]+) ]]; then
        version_suffix="${BASH_REMATCH[1]}"
    fi
    
    case "$distro" in
        ubuntu|debian|raspbian|pop|linuxmint|elementary)
            if [[ -n "$version_suffix" ]]; then
                # Try version-specific packages first, then fall back to generic
                echo "sudo apt update && (sudo apt install -y python${version_suffix}-venv python${version_suffix}-dev || sudo apt install -y python3-venv python3-pip)"
            else
                echo "sudo apt update && sudo apt install -y python3-venv python3-pip"
            fi
            ;;
        fedora)
            echo "sudo dnf install -y python3-venv python3-pip"
            ;;
        rhel|centos|rocky|almalinux|oracle)
            echo "sudo dnf install -y python3-venv python3-pip || sudo yum install -y python3-venv python3-pip"
            ;;
        arch|manjaro|endeavouros)
            echo "sudo pacman -Syu --noconfirm python-pip python-virtualenv"
            ;;
        opensuse|suse)
            echo "sudo zypper install -y python3-venv python3-pip"
            ;;
        alpine)
            echo "sudo apk add --no-cache python3-dev py3-pip py3-virtualenv"
            ;;
        *)
            echo ""
            ;;
    esac
}

# Check if we can use sudo
can_use_sudo() {
    # Check if sudo exists and user can use it
    if command -v sudo &> /dev/null; then
        # Test sudo with a harmless command
        if sudo -n true 2>/dev/null; then
            return 0
        elif [[ -t 0 ]]; then
            # Terminal is interactive, test if sudo works with password
            if sudo true 2>/dev/null; then
                return 0
            fi
        fi
    fi
    return 1
}

# Try to install system packages automatically
try_install_system_packages() {
    local python_cmd="${1:-python3}"
    local os_type=$(detect_os)
    
    # Skip on macOS as it works fine
    if [[ "$os_type" == "macos" ]]; then
        return 1
    fi
    
    # Only try on Linux systems
    if [[ "$os_type" != "linux" && "$os_type" != "wsl" ]]; then
        return 1
    fi
    
    # Get Python version
    local python_version=""
    if command -v "$python_cmd" &> /dev/null; then
        python_version=$($python_cmd --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "")
    fi
    
    local distro=$(detect_linux_distro)
    local install_cmd=$(get_install_command "$distro" "$python_version")
    
    if [[ -z "$install_cmd" ]]; then
        return 1
    fi
    
    print_info "Attempting to install required Python packages..."
    
    # Check if we can use sudo
    if can_use_sudo; then
        print_info "Installing system packages (this may ask for your password)..."
        if eval "$install_cmd" >/dev/null 2>&1; then
            print_success "System packages installed successfully"
            return 0
        else
            print_warning "Failed to install system packages automatically"
        fi
    fi
    
    return 1
}

# Bootstrap pip in virtual environment
bootstrap_pip() {
    local venv_python="$1"
    local python_cmd="$2"
    
    print_info "Bootstrapping pip in virtual environment..."
    
    # Try ensurepip first
    if $venv_python -m ensurepip --default-pip 2>/dev/null; then
        print_success "Successfully bootstrapped pip using ensurepip"
        return 0
    fi
    
    # Try to download get-pip.py
    print_info "Downloading pip installer..."
    local get_pip_url="https://bootstrap.pypa.io/get-pip.py"
    local temp_pip=$(mktemp)
    local download_success=false
    
    # Try curl first
    if command -v curl &> /dev/null; then
        if curl -sSL "$get_pip_url" -o "$temp_pip" 2>/dev/null; then
            download_success=true
        fi
    fi
    
    # Try wget if curl failed
    if [[ "$download_success" == false ]] && command -v wget &> /dev/null; then
        if wget -qO "$temp_pip" "$get_pip_url" 2>/dev/null; then
            download_success=true
        fi
    fi
    
    # Try python urllib as last resort
    if [[ "$download_success" == false ]]; then
        print_info "Using Python to download pip installer..."
        if $python_cmd -c "import urllib.request; urllib.request.urlretrieve('$get_pip_url', '$temp_pip')" 2>/dev/null; then
            download_success=true
        fi
    fi
    
    if [[ "$download_success" == true ]] && [[ -f "$temp_pip" ]] && [[ -s "$temp_pip" ]]; then
        print_info "Installing pip..."
        if $venv_python "$temp_pip" --no-warn-script-location >/dev/null 2>&1; then
            rm -f "$temp_pip"
            print_success "Successfully installed pip"
            return 0
        fi
    fi
    
    rm -f "$temp_pip" 2>/dev/null
    return 1
}

# Setup virtual environment
setup_venv() {
    local python_cmd="$1"
    local venv_python=""
    local venv_pip=""
    
    # Create venv if it doesn't exist
    if [[ ! -d "$VENV_PATH" ]]; then
        print_info "Creating isolated environment..."
        
        # Capture error output for better diagnostics
        local venv_error
        if venv_error=$($python_cmd -m venv "$VENV_PATH" 2>&1); then
            print_success "Created isolated environment"
        else
            # Check for common Linux issues and try fallbacks
            local os_type=$(detect_os)
            if [[ "$os_type" == "linux" || "$os_type" == "wsl" ]]; then
                if echo "$venv_error" | grep -E -q "No module named venv|venv.*not found|ensurepip is not|python3.*-venv"; then
                    # Try to install system packages automatically first
                    if try_install_system_packages "$python_cmd"; then
                        print_info "Retrying virtual environment creation..."
                        if venv_error=$($python_cmd -m venv "$VENV_PATH" 2>&1); then
                            print_success "Created isolated environment"
                        else
                            # Continue to fallback methods below
                            print_warning "Still unable to create venv, trying fallback methods..."
                        fi
                    fi
                    
                    # If venv still doesn't exist, try fallback methods
                    if [[ ! -d "$VENV_PATH" ]]; then
                        # Try virtualenv as fallback
                        if command -v virtualenv &> /dev/null; then
                            print_info "Attempting to create environment with virtualenv..."
                            if virtualenv -p "$python_cmd" "$VENV_PATH" &>/dev/null 2>&1; then
                                print_success "Created environment using virtualenv fallback"
                            fi
                        fi
                        
                        # Try python -m virtualenv if directory wasn't created
                        if [[ ! -d "$VENV_PATH" ]]; then
                            if $python_cmd -m virtualenv "$VENV_PATH" &>/dev/null 2>&1; then
                                print_success "Created environment using python -m virtualenv fallback"
                            fi
                        fi
                        
                        # Last resort: try to install virtualenv via pip and use it
                        if [[ ! -d "$VENV_PATH" ]] && command -v pip3 &> /dev/null; then
                            print_info "Installing virtualenv via pip..."
                            if pip3 install --user virtualenv &>/dev/null 2>&1; then
                                local user_bin="$HOME/.local/bin"
                                if [[ -f "$user_bin/virtualenv" ]]; then
                                    if "$user_bin/virtualenv" -p "$python_cmd" "$VENV_PATH" &>/dev/null 2>&1; then
                                        print_success "Created environment using pip-installed virtualenv"
                                    fi
                                fi
                            fi
                        fi
                    fi
                    
                    # Check if any method succeeded
                    if [[ ! -d "$VENV_PATH" ]]; then
                        print_error "Unable to create virtual environment"
                        echo ""
                        echo "Your system is missing Python development packages."
                        echo ""
                        
                        local distro=$(detect_linux_distro)
                        local python_version=$($python_cmd --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "")
                        local install_cmd=$(get_install_command "$distro" "$python_version")
                        
                        if [[ -n "$install_cmd" ]]; then
                            echo "Please run this command to install them:"
                            echo "  $install_cmd"
                        else
                            echo "Please install Python venv support for your system:"
                            echo "  Ubuntu/Debian: sudo apt install python3-venv python3-pip"
                            echo "  RHEL/CentOS:   sudo dnf install python3-venv python3-pip"
                            echo "  Arch:          sudo pacman -S python-pip python-virtualenv"
                        fi
                        echo ""
                        echo "Then run this script again."
                        exit 1
                    fi
                elif echo "$venv_error" | grep -q "Permission denied"; then
                    print_error "Permission denied creating virtual environment"
                    echo ""
                    echo "Try running in a different directory:"
                    echo "  cd ~ && git clone <repository-url> && cd zen-mcp-server && ./run-server.sh"
                    echo ""
                    exit 1
                else
                    print_error "Failed to create virtual environment"
                    echo "Error: $venv_error"
                    exit 1
                fi
            else
                # For non-Linux systems, show the error and exit
                print_error "Failed to create virtual environment"
                echo "Error: $venv_error"
                exit 1
            fi
        fi
    fi
    
    # Get venv Python path based on platform
    local os_type=$(detect_os)
    case "$os_type" in
        windows)
            venv_python="$VENV_PATH/Scripts/python.exe"
            venv_pip="$VENV_PATH/Scripts/pip.exe"
            ;;
        *)
            venv_python="$VENV_PATH/bin/python"
            venv_pip="$VENV_PATH/bin/pip"
            ;;
    esac
    
    # Check if venv Python exists
    if [[ ! -f "$venv_python" ]]; then
        print_error "Virtual environment Python not found"
        exit 1
    fi
    
    # Check if pip exists in the virtual environment
    if [[ ! -f "$venv_pip" ]] && ! $venv_python -m pip --version &>/dev/null 2>&1; then
        # On Linux, try to install system packages if pip is missing
        local os_type=$(detect_os)
        if [[ "$os_type" == "linux" || "$os_type" == "wsl" ]]; then
            if try_install_system_packages "$python_cmd"; then
                # Check if pip is now available after system package install
                if $venv_python -m pip --version &>/dev/null 2>&1; then
                    print_success "pip is now available"
                else
                    # Still need to bootstrap pip
                    bootstrap_pip "$venv_python" "$python_cmd" || true
                fi
            else
                # Try to bootstrap pip without system packages
                bootstrap_pip "$venv_python" "$python_cmd" || true
            fi
        else
            # For non-Linux systems, just try to bootstrap pip
            bootstrap_pip "$venv_python" "$python_cmd" || true
        fi
        
        # Final check after all attempts
        if ! $venv_python -m pip --version &>/dev/null 2>&1; then
            print_error "Failed to install pip in virtual environment"
            echo ""
            echo "Your Python installation appears to be incomplete."
            echo ""
            
            local distro=$(detect_linux_distro)
            local python_version=$($python_cmd --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "")
            local install_cmd=$(get_install_command "$distro" "$python_version")
            
            if [[ -n "$install_cmd" ]]; then
                echo "Please run this command to install Python packages:"
                echo "  $install_cmd"
            else
                echo "Please install Python pip support for your system."
            fi
            echo ""
            echo "Then delete the virtual environment and run this script again:"
            echo "  rm -rf $VENV_PATH"
            echo "  ./run-server.sh"
            echo ""
            exit 1
        fi
    fi
    
    # Verify pip is working
    if ! $venv_python -m pip --version &>/dev/null 2>&1; then
        print_error "pip is not working correctly in the virtual environment"
        echo ""
        echo "Try deleting the virtual environment and running again:"
        echo "  rm -rf $VENV_PATH"
        echo "  ./run-server.sh"
        echo ""
        exit 1
    fi
    
    if [[ -n "${VIRTUAL_ENV:-}" ]]; then
        print_success "Using activated virtual environment with pip"
    else
        print_success "Virtual environment ready with pip"
    fi
    
    # Convert to absolute path for MCP registration
    local abs_venv_python=$(cd "$(dirname "$venv_python")" && pwd)/$(basename "$venv_python")
    echo "$abs_venv_python"
    return 0
}

# Check if package is installed
check_package() {
    local python_cmd="$1"
    local package="$2"
    $python_cmd -c "import $package" 2>/dev/null
}

# Install dependencies
install_dependencies() {
    local python_cmd="$1"
    local deps_needed=false
    
    # First verify pip is available
    if ! $python_cmd -m pip --version &>/dev/null 2>&1; then
        print_error "pip is not available in the Python environment"
        echo ""
        echo "This indicates an incomplete Python installation."
        echo "Please see the instructions above for installing the required packages."
        return 1
    fi
    
    # Check required packages
    local packages=("mcp" "google.generativeai" "openai" "pydantic" "dotenv")
    for package in "${packages[@]}"; do
        local import_name=${package%%.*}  # Get first part before dot
        if ! check_package "$python_cmd" "$import_name"; then
            deps_needed=true
            break
        fi
    done
    
    if [[ "$deps_needed" == false ]]; then
        print_success "Dependencies already installed"
        return 0
    fi
    
    echo ""
    print_info "Setting up Zen MCP Server..."
    echo "Installing required components:"
    echo "  • MCP protocol library"
    echo "  • AI model connectors"
    echo "  • Data validation tools"
    echo "  • Environment configuration"
    echo ""
    
    # Determine if we're in a venv
    local install_cmd
    if [[ -n "${VIRTUAL_ENV:-}" ]] || [[ "$python_cmd" == *"$VENV_PATH"* ]]; then
        install_cmd="$python_cmd -m pip install -q -r requirements.txt"
    else
        install_cmd="$python_cmd -m pip install -q --user -r requirements.txt"
    fi
    
    # Install packages with better error handling
    echo -n "Downloading packages..."
    local install_output
    local install_error
    
    # Capture both stdout and stderr
    install_output=$($install_cmd 2>&1)
    local exit_code=$?
    
    if [[ $exit_code -ne 0 ]]; then
        echo -e "\r${RED}✗ Setup failed${NC}                      "
        echo ""
        echo "Installation error:"
        echo "$install_output" | head -20
        echo ""
        
        # Check for common issues
        if echo "$install_output" | grep -q "No module named pip"; then
            print_error "pip module not found"
            echo ""
            echo "Your Python installation is incomplete. Please install pip:"
            
            local distro=$(detect_linux_distro)
            local python_version=$($python_cmd --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "")
            local install_cmd=$(get_install_command "$distro" "$python_version")
            
            if [[ -n "$install_cmd" ]]; then
                echo ""
                echo "For your system ($distro), run:"
                echo "  $install_cmd"
            else
                echo ""
                echo "  Ubuntu/Debian: sudo apt install python3-pip"
                echo "  RHEL/CentOS:   sudo dnf install python3-pip"
                echo "  Arch:          sudo pacman -S python-pip"
            fi
        elif echo "$install_output" | grep -q "Permission denied"; then
            print_error "Permission denied during installation"
            echo ""
            echo "Try using a virtual environment or install with --user flag:"
            echo "  $python_cmd -m pip install --user -r requirements.txt"
        else
            echo "Try running manually:"
            echo "  $python_cmd -m pip install -r requirements.txt"
            echo ""
            echo "Or install individual packages:"
            echo "  $python_cmd -m pip install mcp google-genai openai pydantic python-dotenv"
        fi
        return 1
    else
        echo -e "\r${GREEN}✓ Setup complete!${NC}                    "
        
        # Verify critical imports work
        if ! check_package "$python_cmd" "dotenv"; then
            print_warning "python-dotenv not imported correctly, installing explicitly..."
            if $python_cmd -m pip install python-dotenv &>/dev/null 2>&1; then
                print_success "python-dotenv installed successfully"
            else
                print_error "Failed to install python-dotenv"
                return 1
            fi
        fi
        
        return 0
    fi
}

# ----------------------------------------------------------------------------
# Environment Configuration Functions
# ----------------------------------------------------------------------------

# Setup .env file
setup_env_file() {
    if [[ -f .env ]]; then
        print_success ".env file already exists"
        migrate_env_file
        return 0
    fi
    
    if [[ ! -f .env.example ]]; then
        print_error ".env.example not found!"
        return 1
    fi
    
    cp .env.example .env
    print_success "Created .env from .env.example"
    
    # Detect sed version for cross-platform compatibility
    local sed_cmd
    if sed --version >/dev/null 2>&1; then
        sed_cmd="sed -i"  # GNU sed (Linux)
    else
        sed_cmd="sed -i ''"  # BSD sed (macOS)
    fi
    
    # Update API keys from environment if present
    local api_keys=(
        "GEMINI_API_KEY:your_gemini_api_key_here"
        "OPENAI_API_KEY:your_openai_api_key_here"
        "XAI_API_KEY:your_xai_api_key_here"
        "OPENROUTER_API_KEY:your_openrouter_api_key_here"
    )
    
    for key_pair in "${api_keys[@]}"; do
        local key_name="${key_pair%%:*}"
        local placeholder="${key_pair##*:}"
        local key_value="${!key_name:-}"
        
        if [[ -n "$key_value" ]]; then
            $sed_cmd "s/$placeholder/$key_value/" .env
            print_success "Updated .env with $key_name from environment"
        fi
    done
    
    return 0
}

# Migrate .env file from Docker to standalone format
migrate_env_file() {
    # Check if migration is needed
    if ! grep -q "host\.docker\.internal" .env 2>/dev/null; then
        return 0
    fi
    
    print_warning "Migrating .env from Docker to standalone format..."
    
    # Create backup
    cp .env .env.backup_$(date +%Y%m%d_%H%M%S)
    
    # Detect sed version for cross-platform compatibility
    local sed_cmd
    if sed --version >/dev/null 2>&1; then
        sed_cmd="sed -i"  # GNU sed (Linux)
    else
        sed_cmd="sed -i ''"  # BSD sed (macOS)
    fi
    
    # Replace host.docker.internal with localhost
    $sed_cmd 's/host\.docker\.internal/localhost/g' .env
    
    print_success "Migrated Docker URLs to localhost in .env"
    echo "  (Backup saved as .env.backup_*)"
}

# Validate API keys
validate_api_keys() {
    local has_key=false
    local api_keys=(
        "GEMINI_API_KEY:your_gemini_api_key_here"
        "OPENAI_API_KEY:your_openai_api_key_here"
        "XAI_API_KEY:your_xai_api_key_here"
        "OPENROUTER_API_KEY:your_openrouter_api_key_here"
    )
    
    for key_pair in "${api_keys[@]}"; do
        local key_name="${key_pair%%:*}"
        local placeholder="${key_pair##*:}"
        local key_value="${!key_name:-}"
        
        if [[ -n "$key_value" ]] && [[ "$key_value" != "$placeholder" ]]; then
            print_success "$key_name configured"
            has_key=true
        fi
    done
    
    # Check custom API URL
    if [[ -n "${CUSTOM_API_URL:-}" ]]; then
        print_success "CUSTOM_API_URL configured: $CUSTOM_API_URL"
        has_key=true
    fi
    
    if [[ "$has_key" == false ]]; then
        print_error "No API keys found in .env!"
        echo "" >&2
        echo "Please edit .env and add at least one API key:" >&2
        echo "  GEMINI_API_KEY=your-actual-key" >&2
        echo "  OPENAI_API_KEY=your-actual-key" >&2
        echo "  XAI_API_KEY=your-actual-key" >&2
        echo "  OPENROUTER_API_KEY=your-actual-key" >&2
        echo "" >&2
        return 1
    fi
    
    return 0
}

# ----------------------------------------------------------------------------
# Claude Integration Functions
# ----------------------------------------------------------------------------

# Check if MCP is added to Claude CLI and verify it's correct
check_claude_cli_integration() {
    local python_cmd="$1"
    local server_path="$2"
    
    if ! command -v claude &> /dev/null; then
        echo ""
        print_warning "Claude CLI not found"
        echo ""
        read -p "Would you like to add Zen to Claude Code? (Y/n): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Nn]$ ]]; then
            print_info "Skipping Claude Code integration"
            return 0
        fi
        
        echo ""
        echo "Please install Claude Code first:"
        echo "  Visit: https://docs.anthropic.com/en/docs/claude-code/cli-usage"
        echo ""
        echo "Then run this script again to register MCP."
        return 1
    fi
    
    # Check if zen is registered
    local mcp_list=$(claude mcp list 2>/dev/null)
    if echo "$mcp_list" | grep -q "zen"; then
        # Check if it's using the old Docker command
        if echo "$mcp_list" | grep -E "zen.*docker|zen.*compose" &>/dev/null; then
            print_warning "Found old Docker-based Zen registration, updating..."
            claude mcp remove zen -s user 2>/dev/null || true
            
            # Re-add with correct Python command
            if claude mcp add zen -s user -- "$python_cmd" "$server_path" 2>/dev/null; then
                print_success "Updated Zen to become a standalone script"
                return 0
            else
                echo ""
                echo "Failed to update MCP registration. Please run manually:"
                echo "  claude mcp remove zen -s user"
                echo "  claude mcp add zen -s user -- $python_cmd $server_path"
                return 1
            fi
        else
            # Verify the registered path matches current setup
            local expected_cmd="$python_cmd $server_path"
            if echo "$mcp_list" | grep -F "$server_path" &>/dev/null; then
                return 0
            else
                print_warning "Zen registered with different path, updating..."
                claude mcp remove zen -s user 2>/dev/null || true
                
                if claude mcp add zen -s user -- "$python_cmd" "$server_path" 2>/dev/null; then
                    print_success "Updated Zen with current path"
                    return 0
                else
                    echo ""
                    echo "Failed to update MCP registration. Please run manually:"
                    echo "  claude mcp remove zen -s user"
                    echo "  claude mcp add zen -s user -- $python_cmd $server_path"
                    return 1
                fi
            fi
        fi
    else
        # Not registered at all, ask user if they want to add it
        echo ""
        read -p "Add Zen to Claude Code? (Y/n): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Nn]$ ]]; then
            print_info "To add manually later, run:"
            echo "  claude mcp add zen -s user -- $python_cmd $server_path"
            return 0
        fi
        
        print_info "Registering Zen with Claude Code..."
        if claude mcp add zen -s user -- "$python_cmd" "$server_path" 2>/dev/null; then
            print_success "Successfully added Zen to Claude Code"
            return 0
        else
            echo ""
            echo "Failed to add automatically. To add manually, run:"
            echo "  claude mcp add zen -s user -- $python_cmd $server_path"
            return 1
        fi
    fi
}

# Check and update Claude Desktop configuration
check_claude_desktop_integration() {
    local python_cmd="$1"
    local server_path="$2"
    
    # Skip if already configured (check flag)
    if [[ -f "$DESKTOP_CONFIG_FLAG" ]]; then
        return 0
    fi
    
    local config_path=$(get_claude_config_path)
    if [[ -z "$config_path" ]]; then
        print_warning "Unable to determine Claude Desktop config path for this platform"
        return 0
    fi
    
    echo ""
    read -p "Configure Zen for Claude Desktop? (Y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        print_info "Skipping Claude Desktop integration"
        touch "$DESKTOP_CONFIG_FLAG"  # Don't ask again
        return 0
    fi
    
    # Create config directory if it doesn't exist
    local config_dir=$(dirname "$config_path")
    mkdir -p "$config_dir" 2>/dev/null || true
    
    # Handle existing config
    if [[ -f "$config_path" ]]; then
        print_info "Updating existing Claude Desktop config..."
        
        # Check for old Docker config and remove it
        if grep -q "docker.*compose.*zen\|zen.*docker" "$config_path" 2>/dev/null; then
            print_warning "Removing old Docker-based MCP configuration..."
            # Create backup
            cp "$config_path" "${config_path}.backup_$(date +%Y%m%d_%H%M%S)"
            
            # Remove old zen config using a more robust approach
            local temp_file=$(mktemp)
            python3 -c "
import json
import sys

try:
    with open('$config_path', 'r') as f:
        config = json.load(f)
    
    # Remove zen from mcpServers if it exists
    if 'mcpServers' in config and 'zen' in config['mcpServers']:
        del config['mcpServers']['zen']
        print('Removed old zen MCP configuration')
    
    with open('$temp_file', 'w') as f:
        json.dump(config, f, indent=2)
        
except Exception as e:
    print(f'Error processing config: {e}', file=sys.stderr)
    sys.exit(1)
" && mv "$temp_file" "$config_path"
        fi
        
        # Add new config
        local temp_file=$(mktemp)
        python3 -c "
import json
import sys

try:
    with open('$config_path', 'r') as f:
        config = json.load(f)
except:
    config = {}

# Ensure mcpServers exists
if 'mcpServers' not in config:
    config['mcpServers'] = {}

# Add zen server
config['mcpServers']['zen'] = {
    'command': '$python_cmd',
    'args': ['$server_path']
}

with open('$temp_file', 'w') as f:
    json.dump(config, f, indent=2)
" && mv "$temp_file" "$config_path"
        
    else
        print_info "Creating new Claude Desktop config..."
        cat > "$config_path" << EOF
{
  "mcpServers": {
    "zen": {
      "command": "$python_cmd",
      "args": ["$server_path"]
    }
  }
}
EOF
    fi
    
    if [[ $? -eq 0 ]]; then
        print_success "Successfully configured Claude Desktop"
        echo "  Config: $config_path"
        echo "  Restart Claude Desktop to use the new MCP server"
        touch "$DESKTOP_CONFIG_FLAG"
    else
        print_error "Failed to update Claude Desktop config"
        echo "Manual config location: $config_path"
        echo "Add this configuration:"
        cat << EOF
{
  "mcpServers": {
    "zen": {
      "command": "$python_cmd",
      "args": ["$server_path"]
    }
  }
}
EOF
    fi
}

# Display configuration instructions
display_config_instructions() {
    local python_cmd="$1"
    local server_path="$2"
    
    echo ""
    local config_header="ZEN MCP SERVER CONFIGURATION"
    echo "===== $config_header ====="
    printf '%*s\n' "$((${#config_header} + 12))" | tr ' ' '='
    echo ""
    echo "To use Zen MCP Server with your Claude clients:"
    echo ""
    
    print_info "1. For Claude Code (CLI):"
    echo -e "   ${GREEN}claude mcp add zen -s user -- $python_cmd $server_path${NC}"
    echo ""
    
    print_info "2. For Claude Desktop:"
    echo "   Add this configuration to your Claude Desktop config file:"
    echo ""
    cat << EOF
   {
     "mcpServers": {
       "zen": {
         "command": "$python_cmd",
         "args": ["$server_path"]
       }
     }
   }
EOF
    
    # Show platform-specific config location
    local config_path=$(get_claude_config_path)
    if [[ -n "$config_path" ]]; then
        echo ""
        print_info "   Config file location:"
        echo -e "   ${YELLOW}$config_path${NC}"
    fi
    
    echo ""
    print_info "3. Restart Claude Desktop after updating the config file"
    echo ""
}

# Display setup instructions
display_setup_instructions() {
    local python_cmd="$1"
    local server_path="$2"
    
    echo ""
    local setup_header="SETUP COMPLETE"
    echo "===== $setup_header ====="
    printf '%*s\n' "$((${#setup_header} + 12))" | tr ' ' '='
    echo ""
    print_success "Zen is ready to use!"
}

# ----------------------------------------------------------------------------
# Log Management Functions
# ----------------------------------------------------------------------------

# Show help message
show_help() {
    local version=$(get_version)
    local header="🤖 Zen MCP Server v$version"
    echo "$header"
    printf '%*s\n' "${#header}" | tr ' ' '='
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help      Show this help message"
    echo "  -v, --version   Show version information"
    echo "  -f, --follow    Follow server logs in real-time"
    echo "  -c, --config    Show configuration instructions for Claude clients"
    echo "  --clear-cache   Clear Python cache and exit (helpful for import issues)"
    echo ""
    echo "Examples:"
    echo "  $0              Setup and start the MCP server"
    echo "  $0 -f           Setup and follow logs"
    echo "  $0 -c           Show configuration instructions"
    echo "  $0 --version    Show version only"
    echo "  $0 --clear-cache Clear Python cache (fixes import issues)"
    echo ""
    echo "For more information, visit:"
    echo "  https://github.com/BeehiveInnovations/zen-mcp-server"
}

# Show version only
show_version() {
    local version=$(get_version)
    echo "$version"
}

# Follow logs
follow_logs() {
    local log_path="$LOG_DIR/$LOG_FILE"
    
    echo "Following server logs (Ctrl+C to stop)..."
    echo ""
    
    # Create logs directory and file if they don't exist
    mkdir -p "$LOG_DIR"
    touch "$log_path"
    
    # Follow the log file
    tail -f "$log_path"
}

# ----------------------------------------------------------------------------
# Main Function
# ----------------------------------------------------------------------------

main() {
    # Parse command line arguments
    local arg="${1:-}"
    
    case "$arg" in
        -h|--help)
            show_help
            exit 0
            ;;
        -v|--version)
            show_version
            exit 0
            ;;
        -c|--config)
            # Setup minimal environment to get paths for config display
            local python_cmd
            python_cmd=$(find_python) || exit 1
            local new_python_cmd
            new_python_cmd=$(setup_venv "$python_cmd")
            python_cmd="$new_python_cmd"
            local script_dir=$(get_script_dir)
            local server_path="$script_dir/server.py"
            display_config_instructions "$python_cmd" "$server_path"
            exit 0
            ;;
        -f|--follow)
            # Continue with normal setup then follow logs
            ;;
        --clear-cache)
            # Clear cache and exit
            clear_python_cache
            print_success "Cache cleared successfully"
            echo ""
            echo "You can now run './run-server.sh' normally"
            exit 0
            ;;
        "")
            # Normal setup without following logs
            ;;
        *)
            print_error "Unknown option: $arg"
            echo "" >&2
            show_help
            exit 1
            ;;
    esac
    
    # Display header
    local main_header="🤖 Zen MCP Server"
    echo "$main_header"
    printf '%*s\n' "${#main_header}" | tr ' ' '='
    
    # Get and display version
    local version=$(get_version)
    echo "Version: $version"
    echo ""
    
    # Check if venv exists
    if [[ ! -d "$VENV_PATH" ]]; then
        echo "Setting up Python environment for first time..."
    fi
    
    # Step 1: Docker cleanup
    cleanup_docker
    
    # Step 1.5: Clear Python cache to prevent import issues
    clear_python_cache
    
    # Step 2: Find Python
    local python_cmd
    python_cmd=$(find_python) || exit 1
    
    # Step 3: Setup environment file
    setup_env_file || exit 1
    
    # Step 4: Source .env file
    if [[ -f .env ]]; then
        set -a
        source .env
        set +a
    fi
    
    # Step 5: Validate API keys
    validate_api_keys || exit 1
    
    # Step 6: Setup virtual environment
    local new_python_cmd
    new_python_cmd=$(setup_venv "$python_cmd")
    python_cmd="$new_python_cmd"
    
    # Step 7: Install dependencies
    install_dependencies "$python_cmd" || exit 1
    
    # Step 8: Get absolute server path
    local script_dir=$(get_script_dir)
    local server_path="$script_dir/server.py"
    
    # Step 9: Display setup instructions
    display_setup_instructions "$python_cmd" "$server_path"
    
    # Step 10: Check Claude integrations
    check_claude_cli_integration "$python_cmd" "$server_path"
    check_claude_desktop_integration "$python_cmd" "$server_path"
    
    # Step 11: Display log information
    echo ""
    echo "Logs will be written to: $script_dir/$LOG_DIR/$LOG_FILE"
    echo ""
    
    # Step 12: Handle command line arguments
    if [[ "$arg" == "-f" ]] || [[ "$arg" == "--follow" ]]; then
        follow_logs
    else
        echo "To follow logs: ./run-server.sh -f"
        echo "To show config: ./run-server.sh -c"
        echo "To update: git pull, then run ./run-server.sh again"
        echo ""
        echo "Happy Clauding! 🎉"
    fi
}

# ----------------------------------------------------------------------------
# Script Entry Point
# ----------------------------------------------------------------------------

# Run main function with all arguments
main "$@"