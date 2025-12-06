#!/bin/bash
set -euo pipefail

# ============================================================================
# PAL MCP Server Setup Script
#
# A platform-agnostic setup script that works on macOS, Linux, and WSL.
# Handles environment setup, dependency installation, and configuration.
# ============================================================================

# Initialize pyenv if available (do this early)
if [[ -d "$HOME/.pyenv" ]]; then
    export PYENV_ROOT="$HOME/.pyenv"
    export PATH="$PYENV_ROOT/bin:$PATH"
    if command -v pyenv &> /dev/null; then
        eval "$(pyenv init --path)" 2>/dev/null || true
        eval "$(pyenv init -)" 2>/dev/null || true
    fi
fi

# ----------------------------------------------------------------------------
# Constants and Configuration
# ----------------------------------------------------------------------------

# Colors for output (ANSI codes work on all platforms)
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly RED='\033[0;31m'
readonly NC='\033[0m' # No Color

# Configuration
readonly VENV_PATH=".pal_venv"
readonly DOCKER_CLEANED_FLAG=".docker_cleaned"
readonly DESKTOP_CONFIG_FLAG=".desktop_configured"
readonly LOG_DIR="logs"
readonly LOG_FILE="mcp_server.log"
readonly LEGACY_MCP_NAMES=("zen" "zen-mcp" "zen-mcp-server" "zen_mcp" "zen_mcp_server")

# Determine portable arguments for sed -i (GNU vs BSD)
declare -a SED_INPLACE_ARGS
if sed --version >/dev/null 2>&1; then
    SED_INPLACE_ARGS=(-i)
else
    SED_INPLACE_ARGS=(-i "")
fi

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

# Get cross-platform Python executable path from venv
get_venv_python_path() {
    local venv_path="$1"
    
    # Convert to absolute path for consistent behavior across shell environments
    local abs_venv_path
    abs_venv_path=$(cd "$(dirname "$venv_path")" && pwd)/$(basename "$venv_path")

    # Check for both Unix and Windows Python executable paths
    if [[ -f "$abs_venv_path/bin/python" ]]; then
        echo "$abs_venv_path/bin/python"
    elif [[ -f "$abs_venv_path/Scripts/python.exe" ]]; then
        echo "$abs_venv_path/Scripts/python.exe"
    else
        return 1  # No Python executable found
    fi
}

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
            local win_appdata
            if command -v wslvar &> /dev/null; then
                win_appdata=$(wslvar APPDATA 2>/dev/null)
            fi

            if [[ -n "${win_appdata:-}" ]]; then
                echo "$(wslpath "$win_appdata")/Claude/claude_desktop_config.json"
            else
                print_warning "Could not determine Windows user path automatically. Please ensure APPDATA is set correctly or provide the full path manually."
                echo "/mnt/c/Users/$USER/AppData/Roaming/Claude/claude_desktop_config.json"
            fi
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
    # Pyenv should already be initialized at script start, but check if .python-version exists
    if [[ -f ".python-version" ]] && command -v pyenv &> /dev/null; then
        # Ensure pyenv respects the local .python-version
        pyenv local &>/dev/null || true
    fi

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
                    # Verify the command actually exists (important for pyenv)
                    if command -v "$cmd" &> /dev/null; then
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
        fi
    done

    # No suitable Python found - check if we can use pyenv
    local os_type=$(detect_os)

    # Check for pyenv on Unix-like systems (macOS/Linux)
    if [[ "$os_type" == "macos" || "$os_type" == "linux" || "$os_type" == "wsl" ]]; then
        if command -v pyenv &> /dev/null; then
            # pyenv exists, check if Python 3.12 is installed
            if ! pyenv versions 2>/dev/null | grep -E "3\.(1[2-9]|[2-9][0-9])" >/dev/null; then
                echo ""
                echo "Python 3.10+ is required. Pyenv can install Python 3.12 locally for this project."
                read -p "Install Python 3.12 using pyenv? (Y/n): " -n 1 -r
                echo ""
                if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                    if install_python_with_pyenv; then
                        # Try finding Python again
                        if python_cmd=$(find_python); then
                            echo "$python_cmd"
                            return 0
                        fi
                    fi
                fi
            else
                # Python 3.12+ is installed in pyenv but may not be active
                # Check if .python-version exists
                if [[ ! -f ".python-version" ]] || ! grep -qE "3\.(1[2-9]|[2-9][0-9])" .python-version 2>/dev/null; then
                    echo ""
                    print_info "Python 3.12 is installed via pyenv but not set for this project."
                    read -p "Set Python 3.12.0 for this project? (Y/n): " -n 1 -r
                    echo ""
                    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                        # Find the first suitable Python version
                        local py_version=$(pyenv versions --bare | grep -E "^3\.(1[2-9]|[2-9][0-9])" | head -1)
                        if [[ -n "$py_version" ]]; then
                            pyenv local "$py_version"
                            print_success "Set Python $py_version for this project"
                            # Re-initialize pyenv to pick up the change
                            eval "$(pyenv init --path)" 2>/dev/null || true
                            eval "$(pyenv init -)" 2>/dev/null || true
                            # Try finding Python again
                            if python_cmd=$(find_python); then
                                echo "$python_cmd"
                                return 0
                            fi
                        fi
                    fi
                fi
            fi
        else
            # No pyenv installed - show instructions
            echo "" >&2
            print_error "Python 3.10+ not found. The 'mcp' package requires Python 3.10+."
            echo "" >&2

            if [[ "$os_type" == "macos" ]]; then
                echo "To install Python locally for this project:" >&2
                echo "" >&2
                echo "1. Install pyenv (manages Python versions per project):" >&2
                echo "   brew install pyenv" >&2
                echo "" >&2
                echo "2. Add to ~/.zshrc:" >&2
                echo '   export PYENV_ROOT="$HOME/.pyenv"' >&2
                echo '   export PATH="$PYENV_ROOT/bin:$PATH"' >&2
                echo '   eval "$(pyenv init -)"' >&2
                echo "" >&2
                echo "3. Restart terminal, then run:" >&2
                echo "   pyenv install 3.12.0" >&2
                echo "   cd $(pwd)" >&2
                echo "   pyenv local 3.12.0" >&2
                echo "   ./run-server.sh" >&2
            else
                # Linux/WSL
                echo "To install Python locally for this project:" >&2
                echo "" >&2
                echo "1. Install pyenv:" >&2
                echo "   curl https://pyenv.run | bash" >&2
                echo "" >&2
                echo "2. Add to ~/.bashrc:" >&2
                echo '   export PYENV_ROOT="$HOME/.pyenv"' >&2
                echo '   export PATH="$PYENV_ROOT/bin:$PATH"' >&2
                echo '   eval "$(pyenv init -)"' >&2
                echo "" >&2
                echo "3. Restart terminal, then run:" >&2
                echo "   pyenv install 3.12.0" >&2
                echo "   cd $(pwd)" >&2
                echo "   pyenv local 3.12.0" >&2
                echo "   ./run-server.sh" >&2
            fi
        fi
    else
        # Other systems (shouldn't happen with bash script)
        print_error "Python 3.10+ not found. Please install Python 3.10 or newer."
    fi

    return 1
}

# Install Python with pyenv (when pyenv is already installed)
install_python_with_pyenv() {
    # Ensure pyenv is initialized
    export PYENV_ROOT="${PYENV_ROOT:-$HOME/.pyenv}"
    export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init -)" 2>/dev/null || true

    print_info "Installing Python 3.12 (this may take a few minutes)..."
    if pyenv install -s 3.12.0; then
        print_success "Python 3.12 installed"

        # Set local Python version for this project
        pyenv local 3.12.0
        print_success "Python 3.12 set for this project"

        # Show shell configuration instructions
        echo ""
        print_info "To make pyenv work in new terminals, add to your shell config:"
        local shell_config="~/.zshrc"
        if [[ "$SHELL" == *"bash"* ]]; then
            shell_config="~/.bashrc"
        fi
        echo '  export PYENV_ROOT="$HOME/.pyenv"'
        echo '  command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"'
        echo '  eval "$(pyenv init -)"'
        echo ""

        # Re-initialize pyenv to use the newly installed Python
        eval "$(pyenv init --path)" 2>/dev/null || true
        eval "$(pyenv init -)" 2>/dev/null || true

        return 0
    else
        print_error "Failed to install Python 3.12"
        return 1
    fi
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
        if bash -c "$install_cmd" >/dev/null 2>&1; then  # Replaced eval to prevent command injection
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
    if $venv_python -m ensurepip --default-pip >/dev/null 2>&1; then
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

# Setup environment using uv-first approach
setup_environment() {
    local venv_python=""

    # Try uv-first approach
    if command -v uv &> /dev/null; then
        print_info "Setting up environment with uv..."

        # Only remove existing venv if it wasn't created by uv (to ensure clean uv setup)
        if [[ -d "$VENV_PATH" ]] && [[ ! -f "$VENV_PATH/uv_created" ]]; then
            print_info "Removing existing environment for clean uv setup..."
            rm -rf "$VENV_PATH"
        fi

        # Try Python 3.12 first (preferred)
        local uv_output
        if uv_output=$(uv venv --python 3.12 "$VENV_PATH" 2>&1); then
            # Use helper function for cross-platform path detection
            if venv_python=$(get_venv_python_path "$VENV_PATH"); then
                touch "$VENV_PATH/uv_created"  # Mark as uv-created
                print_success "Created environment with uv using Python 3.12"

                # Ensure pip is installed in uv environment
                if ! $venv_python -m pip --version &>/dev/null 2>&1; then
                    print_info "Installing pip in uv environment..."
                    # uv doesn't install pip by default, use bootstrap method
                    if bootstrap_pip "$venv_python" "python3"; then
                        print_success "pip installed in uv environment"
                    else
                        print_warning "Failed to install pip in uv environment"
                    fi
                fi
            else
                print_warning "uv succeeded but Python executable not found in venv"
            fi
        # Fall back to any available Python through uv
        elif uv_output=$(uv venv "$VENV_PATH" 2>&1); then
            # Use helper function for cross-platform path detection
            if venv_python=$(get_venv_python_path "$VENV_PATH"); then
                touch "$VENV_PATH/uv_created"  # Mark as uv-created
                local python_version=$($venv_python --version 2>&1)
                print_success "Created environment with uv using $python_version"

                # Ensure pip is installed in uv environment
                if ! $venv_python -m pip --version &>/dev/null 2>&1; then
                    print_info "Installing pip in uv environment..."
                    # uv doesn't install pip by default, use bootstrap method
                    if bootstrap_pip "$venv_python" "python3"; then
                        print_success "pip installed in uv environment"
                    else
                        print_warning "Failed to install pip in uv environment"
                    fi
                fi
            else
                print_warning "uv succeeded but Python executable not found in venv"
            fi
        else
            print_warning "uv environment creation failed, falling back to system Python detection"
            print_warning "uv output: $uv_output"
        fi
    else
        print_info "uv not found, using system Python detection"
    fi

    # If uv failed or not available, fallback to system Python detection
    if [[ -z "$venv_python" ]]; then
        print_info "Setting up environment with system Python..."
        local python_cmd
        python_cmd=$(find_python) || return 1

        # Use existing venv creation logic
        venv_python=$(setup_venv "$python_cmd")
        if [[ $? -ne 0 ]]; then
            return 1
        fi
    else
        # venv_python was already set by uv creation above, just convert to absolute path
        if [[ -n "$venv_python" ]]; then
            # Convert to absolute path for MCP registration
            local abs_venv_python
            if cd "$(dirname "$venv_python")" 2>/dev/null; then
                abs_venv_python=$(pwd)/$(basename "$venv_python")
                venv_python="$abs_venv_python"
            else
                print_error "Failed to resolve absolute path for venv_python"
                return 1
            fi
        fi
    fi

    echo "$venv_python"
    return 0
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
                    echo "  cd ~ && git clone <repository-url> && cd pal-mcp-server && ./run-server.sh"
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

    # Always check if pip exists in the virtual environment (regardless of how it was created)
    if [[ ! -f "$venv_pip" ]] && ! $venv_python -m pip --version &>/dev/null 2>&1; then
        print_warning "pip not found in virtual environment, installing..."

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
    local module_name="$2"
    "$python_cmd" -c "import importlib, sys; importlib.import_module(sys.argv[1])" "$module_name" &>/dev/null
}

# Install dependencies
install_dependencies() {
    local python_cmd="$1"
    local deps_needed=false

    # First verify pip is available with retry logic and bootstrap fallback
    local pip_available=false
    local max_attempts=3

    for ((attempt=1; attempt<=max_attempts; attempt++)); do
        if "$python_cmd" -m pip --version &>/dev/null; then
            pip_available=true
            break
        else
            if (( attempt < max_attempts )); then
                print_warning "Attempt $attempt/$max_attempts: pip not available, retrying in 1 second..."
                sleep 1
            fi
        fi
    done

    # If pip is still not available after retries, try to bootstrap it
    if [[ "$pip_available" == false ]]; then
        print_warning "pip is not available in the Python environment after $max_attempts attempts"
        
        # Enhanced diagnostic information for debugging
        print_info "Diagnostic information:"
        print_info "  Python executable: $python_cmd"
        print_info "  Python executable exists: $(if [[ -f "$python_cmd" ]]; then echo "Yes"; else echo "No"; fi)"
        print_info "  Python executable permissions: $(ls -la "$python_cmd" 2>/dev/null || echo "Cannot check")"
        print_info "  Virtual environment path: $VENV_PATH"
        print_info "  Virtual environment exists: $(if [[ -d "$VENV_PATH" ]]; then echo "Yes"; else echo "No"; fi)"
        
        print_info "Attempting to bootstrap pip..."

        # Extract the base python command for bootstrap (fallback to python3)
        local base_python_cmd="python3"
        if command -v python &> /dev/null; then
            base_python_cmd="python"
        fi

        # Try to bootstrap pip
        if bootstrap_pip "$python_cmd" "$base_python_cmd"; then
            print_success "Successfully bootstrapped pip"

            # Verify pip is now available
            if $python_cmd -m pip --version &>/dev/null 2>&1; then
                pip_available=true
            else
                print_error "pip still not available after bootstrap attempt"
            fi
        else
            print_error "Failed to bootstrap pip"
        fi
    fi

    # Final check - if pip is still not available, exit with error
    if [[ "$pip_available" == false ]]; then
        print_error "pip is not available in the Python environment"
        echo ""
        echo "This indicates an incomplete Python installation or a problem with the virtual environment."
        echo ""
        echo "Final diagnostic information:"
        echo "  Python executable: $python_cmd"
        echo "  Python version: $($python_cmd --version 2>&1 || echo "Cannot determine")"
        echo "  pip module check: $($python_cmd -c "import pip; print('Available')" 2>&1 || echo "Not available")"
        echo ""
        echo "Troubleshooting steps:"
        echo "1. Delete the virtual environment: rm -rf $VENV_PATH"
        echo "2. Run this script again: ./run-server.sh"
        echo "3. If the problem persists, check your Python installation"
        echo "4. For Git Bash on Windows, try running from a regular Command Prompt or PowerShell"
        echo ""
        return 1
    fi

    # Check required packages
    local packages=("mcp" "google.genai" "openai" "pydantic" "dotenv")
    for package in "${packages[@]}"; do
        if ! check_package "$python_cmd" "$package"; then
            deps_needed=true
            break
        fi
    done

    if [[ "$deps_needed" == false ]]; then
        print_success "Dependencies already installed"
        return 0
    fi

    echo ""
    print_info "Setting up PAL MCP Server..."
    echo "Installing required components:"
    echo "  • MCP protocol library"
    echo "  • AI model connectors"
    echo "  • Data validation tools"
    echo "  • Environment configuration"
    echo ""

    # Determine installation method and execute directly to handle paths with spaces
    local install_output
    local exit_code=0

    echo -n "Downloading packages..."

    if command -v uv &> /dev/null && [[ -f "$VENV_PATH/uv_created" ]]; then
        print_info "Using uv for faster package installation..."
        install_output=$(uv pip install -q -r requirements.txt --python "$python_cmd" 2>&1) || exit_code=$?
    elif [[ -n "${VIRTUAL_ENV:-}" ]] || [[ "$python_cmd" == *"$VENV_PATH"* ]]; then
        install_output=$("$python_cmd" -m pip install -q -r requirements.txt 2>&1) || exit_code=$?
    else
        install_output=$("$python_cmd" -m pip install -q --user -r requirements.txt 2>&1) || exit_code=$?
    fi

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
            if [[ "$use_uv" == true ]]; then
                echo "  uv pip install -r requirements.txt --python $python_cmd"
                echo "Or fallback to pip:"
            fi
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

    # Update API keys from environment if present
    local api_keys=(
        "GEMINI_API_KEY:your_gemini_api_key_here"
        "OPENAI_API_KEY:your_openai_api_key_here"
        "XAI_API_KEY:your_xai_api_key_here"
        "DIAL_API_KEY:your_dial_api_key_here"
        "OPENROUTER_API_KEY:your_openrouter_api_key_here"
    )

    for key_pair in "${api_keys[@]}"; do
        local key_name="${key_pair%%:*}"
        local placeholder="${key_pair##*:}"
        local key_value="${!key_name:-}"

        if [[ -n "$key_value" ]]; then
            sed "${SED_INPLACE_ARGS[@]}" "s/$placeholder/$key_value/" .env
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

    # Replace host.docker.internal with localhost
    sed "${SED_INPLACE_ARGS[@]}" 's/host\.docker\.internal/localhost/g' .env

    print_success "Migrated Docker URLs to localhost in .env"
    echo "  (Backup saved as .env.backup_*)"
}

# Check API keys and warn if missing (non-blocking)
check_api_keys() {
    local has_key=false
    local api_keys=(
        "GEMINI_API_KEY:your_gemini_api_key_here"
        "OPENAI_API_KEY:your_openai_api_key_here"
        "XAI_API_KEY:your_xai_api_key_here"
        "DIAL_API_KEY:your_dial_api_key_here"
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
        print_warning "No API keys found in .env!"
        echo ""
        echo "The Python development environment will be set up, but you won't be able to use the MCP server until you add API keys."
        echo ""
        echo "To add API keys, edit .env and add at least one:"
        echo "  GEMINI_API_KEY=your-actual-key"
        echo "  OPENAI_API_KEY=your-actual-key"
        echo "  XAI_API_KEY=your-actual-key"
        echo "  DIAL_API_KEY=your-actual-key"
        echo "  OPENROUTER_API_KEY=your-actual-key"
        echo ""
        print_info "You can continue with development setup and add API keys later."
        echo ""
    fi

    return 0  # Always return success to continue setup
}


# ----------------------------------------------------------------------------
# Environment Variable Parsing Function
# ----------------------------------------------------------------------------

# Parse .env file and extract all valid environment variables
parse_env_variables() {
    local env_vars=""
    
    if [[ -f .env ]]; then
        # Read .env file and extract non-empty, non-comment variables
        while IFS= read -r line; do
            # Skip comments, empty lines, and lines starting with #
            if [[ -n "$line" && ! "$line" =~ ^[[:space:]]*# && "$line" =~ ^[[:space:]]*([^=]+)=(.*)$ ]]; then
                local key="${BASH_REMATCH[1]}"
                local value="${BASH_REMATCH[2]}"
                
                # Clean up key (remove leading/trailing whitespace)
                key=$(echo "$key" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
                
                # Skip if value is empty or just whitespace
                if [[ -n "$value" && ! "$value" =~ ^[[:space:]]*$ ]]; then
                    # Clean up value (remove leading/trailing whitespace and quotes)
                    value=$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | sed 's/^"//;s/"$//')
                    
                    # Remove inline comments (everything after # that's not in quotes)
                    value=$(echo "$value" | sed 's/[[:space:]]*#.*$//')
                    
                    # Skip if value is a placeholder or empty after comment removal
                    if [[ ! "$value" =~ ^your_.*_here$ && "$value" != "your_" && -n "$value" && ! "$value" =~ ^[[:space:]]*$ ]]; then
                        env_vars+="$key=$value"$'\n'
                    fi
                fi
            fi
        done < .env
    fi

    # If no .env file or no valid vars, fall back to environment variables
    if [[ -z "$env_vars" ]]; then
        local api_keys=(
            "GEMINI_API_KEY"
            "OPENAI_API_KEY" 
            "XAI_API_KEY"
            "DIAL_API_KEY"
            "OPENROUTER_API_KEY"
            "CUSTOM_API_URL"
            "CUSTOM_API_KEY"
            "CUSTOM_MODEL_NAME"
            "DISABLED_TOOLS"
            "DEFAULT_MODEL"
            "LOG_LEVEL"
            "DEFAULT_THINKING_MODE_THINKDEEP"
            "CONVERSATION_TIMEOUT_HOURS"
            "MAX_CONVERSATION_TURNS"
        )

        for key_name in "${api_keys[@]}"; do
            local key_value="${!key_name:-}"
            if [[ -n "$key_value" && ! "$key_value" =~ ^your_.*_here$ ]]; then
                env_vars+="$key_name=$key_value"$'\n'
            fi
        done
    fi
    
    echo "$env_vars"
}

# ----------------------------------------------------------------------------
# Claude Integration Functions
# ----------------------------------------------------------------------------

# Check if MCP is added to Claude CLI and verify it's correct
check_claude_cli_integration() {
    local python_cmd="$1"
    local server_path="$2"

    # Check for native installed Claude CLI (not in PATH by default)
    # Native installs:
    #   - curl https://claude.ai/install.sh | bash -> ~/.local/bin/claude
    #   - brew install --cask claude-code -> /opt/homebrew/bin/claude (Apple Silicon) or /usr/local/bin/claude (Intel)
    if ! command -v claude &> /dev/null; then
        local claude_paths=(
            "$HOME/.local/bin"
            "/opt/homebrew/bin"
            "/usr/local/bin"
        )
        for dir in "${claude_paths[@]}"; do
            if [[ -x "$dir/claude" ]]; then
                print_info "Found native installed Claude CLI at $dir/claude"
                export PATH="$dir:$PATH"
                print_success "Added $dir to PATH"
                break
            fi
        done
    fi

    if ! command -v claude &> /dev/null; then
        echo ""
        print_warning "Claude CLI not found"
        echo ""
        read -p "Would you like to add PAL to Claude Code? (Y/n): " -n 1 -r
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

    # Remove legacy zen registrations to avoid duplicate errors after rename
    for legacy_name in "${LEGACY_MCP_NAMES[@]}"; do
        claude mcp remove "$legacy_name" -s user >/dev/null 2>&1 || true
    done

    # Check if pal is registered
    local mcp_list=$(claude mcp list 2>/dev/null)
    if echo "$mcp_list" | grep -q "pal"; then
        # Check if it's using the old Docker command
        if echo "$mcp_list" | grep -E "zen.*docker|zen.*compose" &>/dev/null; then
            print_warning "Found old Docker-based Zen registration, updating..."
            claude mcp remove zen -s user 2>/dev/null || true

            # Re-add with correct Python command and environment variables
            local env_vars=$(parse_env_variables)
            local env_args=""
            
            # Convert environment variables to -e arguments
            if [[ -n "$env_vars" ]]; then
                while IFS= read -r line; do
                    if [[ -n "$line" && "$line" =~ ^([^=]+)=(.*)$ ]]; then
                        env_args+=" -e ${BASH_REMATCH[1]}=\"${BASH_REMATCH[2]}\""
                    fi
                done <<< "$env_vars"
            fi
            
            local claude_cmd="claude mcp add pal -s user$env_args -- \"$python_cmd\" \"$server_path\""
            if eval "$claude_cmd" 2>/dev/null; then
                print_success "Updated PAL to become a standalone script with environment variables"
                return 0
            else
                echo ""
                echo "Failed to update MCP registration. Please run manually:"
                echo "  claude mcp remove pal -s user"
                echo "  $claude_cmd"
                return 1
            fi
        else
            # Verify the registered path matches current setup
            local expected_cmd="$python_cmd $server_path"
            if echo "$mcp_list" | grep -F "$server_path" &>/dev/null; then
                return 0
            else
                print_warning "PAL registered with different path, updating..."
                claude mcp remove pal -s user 2>/dev/null || true

                # Re-add with current path and environment variables
                local env_vars=$(parse_env_variables)
                local env_args=""
                
                # Convert environment variables to -e arguments
                if [[ -n "$env_vars" ]]; then
                    while IFS= read -r line; do
                        if [[ -n "$line" && "$line" =~ ^([^=]+)=(.*)$ ]]; then
                            env_args+=" -e ${BASH_REMATCH[1]}=\"${BASH_REMATCH[2]}\""
                        fi
                    done <<< "$env_vars"
                fi
                
                local claude_cmd="claude mcp add pal -s user$env_args -- \"$python_cmd\" \"$server_path\""
                if eval "$claude_cmd" 2>/dev/null; then
                    print_success "Updated PAL with current path and environment variables"
                    return 0
                else
                    echo ""
                    echo "Failed to update MCP registration. Please run manually:"
                    echo "  claude mcp remove pal -s user"
                    echo "  $claude_cmd"
                    return 1
                fi
            fi
        fi
    else
        # Not registered at all, ask user if they want to add it
        echo ""
        read -p "Add PAL to Claude Code? (Y/n): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Nn]$ ]]; then
            local env_vars=$(parse_env_variables)
            local env_args=""
            
            # Convert environment variables to -e arguments for manual command
            if [[ -n "$env_vars" ]]; then
                while IFS= read -r line; do
                    if [[ -n "$line" && "$line" =~ ^([^=]+)=(.*)$ ]]; then
                        env_args+=" -e ${BASH_REMATCH[1]}=\"${BASH_REMATCH[2]}\""
                    fi
                done <<< "$env_vars"
            fi
            
            print_info "To add manually later, run:"
            echo "  claude mcp add pal -s user$env_args -- $python_cmd $server_path"
            return 0
        fi

        print_info "Registering PAL with Claude Code..."
        
        # Add with environment variables
        local env_vars=$(parse_env_variables)
        local env_args=""
        
        # Convert environment variables to -e arguments
        if [[ -n "$env_vars" ]]; then
            while IFS= read -r line; do
                if [[ -n "$line" && "$line" =~ ^([^=]+)=(.*)$ ]]; then
                    env_args+=" -e ${BASH_REMATCH[1]}=\"${BASH_REMATCH[2]}\""
                fi
            done <<< "$env_vars"
        fi
        
        local claude_cmd="claude mcp add pal -s user$env_args -- \"$python_cmd\" \"$server_path\""
        if eval "$claude_cmd" 2>/dev/null; then
            print_success "Successfully added PAL to Claude Code with environment variables"
            return 0
        else
            echo ""
            echo "Failed to add automatically. To add manually, run:"
            echo "  $claude_cmd"
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

    # Legacy MCP server names to clean out from previous releases
    local legacy_names_csv
    legacy_names_csv=$(IFS=,; echo "${LEGACY_MCP_NAMES[*]}")

    echo ""
    read -p "Configure PAL for Claude Desktop? (Y/n): " -n 1 -r
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
        if grep -q "docker.*compose.*pal\|pal.*docker" "$config_path" 2>/dev/null; then
            print_warning "Removing old Docker-based MCP configuration..."
            # Create backup
            cp "$config_path" "${config_path}.backup_$(date +%Y%m%d_%H%M%S)"

            # Remove old pal config using a more robust approach
            local temp_file=$(mktemp)
            python3 -c "
import json
import sys

try:
    with open('$config_path', 'r') as f:
        config = json.load(f)

    # Remove pal from mcpServers if it exists
    if 'mcpServers' in config and 'pal' in config['mcpServers']:
        del config['mcpServers']['pal']
        print('Removed old pal MCP configuration')

    with open('$temp_file', 'w') as f:
        json.dump(config, f, indent=2)

except Exception as e:
    print(f'Error processing config: {e}', file=sys.stderr)
    sys.exit(1)
" && mv "$temp_file" "$config_path"
        fi

        # Add new config with environment variables
        local env_vars=$(parse_env_variables)
        local temp_file=$(mktemp)
        local env_file=$(mktemp)
        
        # Write environment variables to a temporary file for Python to read
        if [[ -n "$env_vars" ]]; then
            echo "$env_vars" > "$env_file"
        fi
        
        PAL_LEGACY_NAMES="$legacy_names_csv" python3 -c "
import json
import os
import sys

legacy_keys = [k for k in os.environ.get('PAL_LEGACY_NAMES', '').split(',') if k]

try:
    with open('$config_path', 'r') as f:
        config = json.load(f)
except Exception:
    config = {}

if not isinstance(config, dict):
    config = {}

# Ensure mcpServers exists
if 'mcpServers' not in config or not isinstance(config.get('mcpServers'), dict):
    config['mcpServers'] = {}

# Remove legacy entries from any known server blocks
for container in ('mcpServers', 'servers'):
    servers = config.get(container)
    if isinstance(servers, dict):
        for key in legacy_keys:
            servers.pop(key, None)

# Add pal server
pal_config = {
    'command': '$python_cmd',
    'args': ['$server_path']
}

# Add environment variables if they exist
env_dict = {}
try:
    with open('$env_file', 'r') as f:
        for line in f:
            line = line.strip()
            if '=' in line and line:
                key, value = line.split('=', 1)
                env_dict[key] = value
except Exception:
    pass

if env_dict:
    pal_config['env'] = env_dict

config['mcpServers']['pal'] = pal_config

with open('$temp_file', 'w') as f:
    json.dump(config, f, indent=2)
" && mv "$temp_file" "$config_path"
        
        # Clean up temporary env file
        rm -f "$env_file" 2>/dev/null || true

    else
        print_info "Creating new Claude Desktop config..."
        
        # Create new config with environment variables
        local env_vars=$(parse_env_variables)
        local temp_file=$(mktemp)
        local env_file=$(mktemp)
        
        # Write environment variables to a temporary file for Python to read
        if [[ -n "$env_vars" ]]; then
            echo "$env_vars" > "$env_file"
        fi
        
        python3 -c "
import json
import sys

config = {'mcpServers': {}}

# Add pal server
pal_config = {
    'command': '$python_cmd',
    'args': ['$server_path']
}

# Add environment variables if they exist
env_dict = {}
try:
    with open('$env_file', 'r') as f:
        for line in f:
            line = line.strip()
            if '=' in line and line:
                key, value = line.split('=', 1)
                env_dict[key] = value
except:
    pass

if env_dict:
    pal_config['env'] = env_dict

config['mcpServers']['pal'] = pal_config

with open('$temp_file', 'w') as f:
    json.dump(config, f, indent=2)
" && mv "$temp_file" "$config_path"
        
        # Clean up temporary env file
        rm -f "$env_file" 2>/dev/null || true
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
        
        # Generate example with actual environment variables for error case
        example_env=""
        env_vars=$(parse_env_variables)
        if [[ -n "$env_vars" ]]; then
            local first_entry=true
            while IFS= read -r line; do
                if [[ -n "$line" && "$line" =~ ^([^=]+)=(.*)$ ]]; then
                    local key="${BASH_REMATCH[1]}"
                    local value="your_$(echo "${key}" | tr '[:upper:]' '[:lower:]')"
                    
                    if [[ "$first_entry" == true ]]; then
                        first_entry=false
                        example_env="      \"$key\": \"$value\""
                    else
                        example_env+=",\n      \"$key\": \"$value\""
                    fi
                fi
            done <<< "$env_vars"
        fi
        
        cat << EOF
{
  "mcpServers": {
    "pal": {
      "command": "$python_cmd",
      "args": ["$server_path"]$(if [[ -n "$example_env" ]]; then echo ","; fi)$(if [[ -n "$example_env" ]]; then echo "
      \"env\": {
$(echo -e "$example_env")
      }"; fi)
    }
  }
}
EOF
    fi
}

# Check and update Gemini CLI configuration
check_gemini_cli_integration() {
    local script_dir="$1"
    local pal_wrapper="$script_dir/pal-mcp-server"

    # Check if Gemini settings file exists
    local gemini_config="$HOME/.gemini/settings.json"
    if [[ ! -f "$gemini_config" ]]; then
        # Gemini CLI not installed or not configured
        return 0
    fi

    # Clean up legacy zen entries and detect existing pal configuration
    local legacy_names_csv
    legacy_names_csv=$(IFS=,; echo "${LEGACY_MCP_NAMES[*]}")

    local gemini_status
    gemini_status=$(
        PAL_LEGACY_NAMES="$legacy_names_csv" PAL_WRAPPER="$pal_wrapper" PAL_GEMINI_CONFIG="$gemini_config" python3 - <<'PY' 2>/dev/null
import json
import os
import pathlib
import sys

config_path = pathlib.Path(os.environ["PAL_GEMINI_CONFIG"])
legacy = [n for n in os.environ.get("PAL_LEGACY_NAMES", "").split(",") if n]
wrapper = os.environ["PAL_WRAPPER"]

changed = False
has_pal = False

try:
    data = json.loads(config_path.read_text())
except Exception:
    data = {}

if not isinstance(data, dict):
    data = {}

servers = data.get("mcpServers")
if not isinstance(servers, dict):
    servers = {}
    data["mcpServers"] = servers

for key in legacy:
    if servers.pop(key, None) is not None:
        changed = True

pal_cfg = servers.get("pal")
if isinstance(pal_cfg, dict):
    has_pal = True
    if pal_cfg.get("command") != wrapper:
        pal_cfg["command"] = wrapper
        servers["pal"] = pal_cfg
        changed = True

if changed:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(data, indent=2))

status = ("CHANGED" if changed else "UNCHANGED") + ":" + ("HAS_PAL" if has_pal else "NO_PAL")
sys.stdout.write(status)
sys.exit(0)
PY
    ) || true

    local gemini_changed=false
    local gemini_has_pal=false
    [[ "$gemini_status" == CHANGED:* ]] && gemini_changed=true
    [[ "$gemini_status" == *:HAS_PAL ]] && gemini_has_pal=true

    if [[ "$gemini_has_pal" == true ]]; then
        if [[ "$gemini_changed" == true ]]; then
            print_success "Removed legacy Gemini MCP entries"
        fi
        return 0
    fi

    # Ask user if they want to add PAL to Gemini CLI
    echo ""
    read -p "Configure PAL for Gemini CLI? (Y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        print_info "Skipping Gemini CLI integration"
        return 0
    fi

    # Ensure wrapper script exists
    if [[ ! -f "$pal_wrapper" ]]; then
        print_info "Creating wrapper script for Gemini CLI..."
        cat > "$pal_wrapper" << 'EOF'
#!/bin/bash
# Wrapper script for Gemini CLI compatibility
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
exec .pal_venv/bin/python server.py "$@"
EOF
        chmod +x "$pal_wrapper"
        print_success "Created pal-mcp-server wrapper script"
    fi

    # Update Gemini settings
    print_info "Updating Gemini CLI configuration..."

    # Create backup
    cp "$gemini_config" "${gemini_config}.backup_$(date +%Y%m%d_%H%M%S)"

    # Add pal configuration using Python for proper JSON handling
    local temp_file=$(mktemp)
    python3 -c "
import json
import sys

try:
    with open('$gemini_config', 'r') as f:
        config = json.load(f)

    # Ensure mcpServers exists
    if 'mcpServers' not in config:
        config['mcpServers'] = {}

    # Add pal server
    config['mcpServers']['pal'] = {
        'command': '$pal_wrapper'
    }

    with open('$temp_file', 'w') as f:
        json.dump(config, f, indent=2)

except Exception as e:
    print(f'Error processing config: {e}', file=sys.stderr)
    sys.exit(1)
" && mv "$temp_file" "$gemini_config"

    if [[ $? -eq 0 ]]; then
        print_success "Successfully configured Gemini CLI"
        echo "  Config: $gemini_config"
        echo "  Restart Gemini CLI to use PAL MCP Server"
    else
        print_error "Failed to update Gemini CLI config"
        echo "Manual config location: $gemini_config"
        echo "Add this configuration:"
        cat << EOF
{
  "mcpServers": {
    "pal": {
      "command": "$pal_wrapper"
    }
  }
}
EOF
    fi
}

# Check and update Codex CLI configuration
check_codex_cli_integration() {
    if ! command -v codex &> /dev/null; then
        return 0
    fi

    local codex_config="$HOME/.codex/config.toml"
    local legacy_names_csv
    legacy_names_csv=$(IFS=,; echo "${LEGACY_MCP_NAMES[*]}")

    if [[ -f "$codex_config" ]]; then
        local codex_cleanup_status
        codex_cleanup_status=$(
            PAL_LEGACY_NAMES="$legacy_names_csv" PAL_CODEX_CONFIG="$codex_config" python3 - <<'PY' 2>/dev/null
import os
import pathlib
import re
import sys

config_path = pathlib.Path(os.environ["PAL_CODEX_CONFIG"])
legacy = [n for n in os.environ.get("PAL_LEGACY_NAMES", "").split(",") if n]

if not config_path.exists():
    sys.exit(0)

lines = config_path.read_text().splitlines()
output = []
skip = False
removed = False
section_re = re.compile(r"\s*\[([^\]]+)\]")

for line in lines:
    match = section_re.match(line)
    if match:
        header = match.group(1).strip()
        parts = header.split(".")
        is_legacy = False
        if len(parts) >= 2 and parts[0] == "mcp_servers":
            section_key = ".".join(parts[1:])
            for name in legacy:
                if section_key == name or section_key.startswith(name + "."):
                    is_legacy = True
                    break
        skip = is_legacy
        if is_legacy:
            removed = True
            continue
    if not skip:
        output.append(line)

if removed:
    config_path.write_text("\n".join(output).rstrip() + ("\n" if output else ""))
    sys.stdout.write("REMOVED")
else:
    sys.stdout.write("UNCHANGED")
sys.exit(0)
PY
        ) || true

        if [[ "$codex_cleanup_status" == "REMOVED" ]]; then
            print_success "Removed legacy Codex MCP entries"
        fi
    fi

    local codex_has_pal=false
    if [[ -f "$codex_config" ]] && grep -q '\[mcp_servers\.pal\]' "$codex_config" 2>/dev/null; then
        codex_has_pal=true
    fi

    if [[ "$codex_has_pal" == false ]]; then
        echo ""
        read -p "Configure PAL for Codex CLI? (Y/n): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Nn]$ ]]; then
            print_info "Skipping Codex CLI integration"
            return 0
        fi

        print_info "Updating Codex CLI configuration..."

        mkdir -p "$(dirname "$codex_config")" 2>/dev/null || true

        if [[ -f "$codex_config" ]]; then
            cp "$codex_config" "${codex_config}.backup_$(date +%Y%m%d_%H%M%S)"
        fi

        local env_vars=$(parse_env_variables)

        {
            echo ""
            echo "[mcp_servers.pal]"
            echo "command = \"bash\""
            echo "args = [\"-c\", \"for p in \$(which uvx 2>/dev/null) \$HOME/.local/bin/uvx /opt/homebrew/bin/uvx /usr/local/bin/uvx uvx; do [ -x \\\"\$p\\\" ] && exec \\\"\$p\\\" --from git+https://github.com/BeehiveInnovations/pal-mcp-server.git pal-mcp-server; done; echo 'uvx not found' >&2; exit 1\"]"
            echo "tool_timeout_sec = 1200"
            echo ""
            echo "[mcp_servers.pal.env]"
            echo "PATH = \"/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:\$HOME/.local/bin:\$HOME/.cargo/bin:\$HOME/bin\""
            if [[ -n "$env_vars" ]]; then
                while IFS= read -r line; do
                    if [[ -n "$line" && "$line" =~ ^([^=]+)=(.*)$ ]]; then
                        local key="${BASH_REMATCH[1]}"
                        local value="${BASH_REMATCH[2]}"
                        local escaped_value
                        escaped_value=$(echo "$value" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')
                        echo "$key = \"$escaped_value\""
                    fi
                done <<< "$env_vars"
            fi
        } >> "$codex_config"

        if [[ $? -ne 0 ]]; then
            print_error "Failed to update Codex CLI config"
            echo "Manual config location: $codex_config"
            echo "Add this configuration:"
cat <<'CODExEOF'
[mcp_servers.pal]
command = "sh"
args = ["-c", "exec \$(which uvx 2>/dev/null || echo uvx) --from git+https://github.com/BeehiveInnovations/pal-mcp-server.git pal-mcp-server"]
tool_timeout_sec = 1200

[mcp_servers.pal.env]
PATH = "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:\$HOME/.local/bin:\$HOME/.cargo/bin:\$HOME/bin"

[features]
web_search_request = true
CODExEOF

            if [[ -n "$env_vars" ]]; then
                while IFS= read -r line; do
                    if [[ -n "$line" && "$line" =~ ^([^=]+)=(.*)$ ]]; then
                        local key="${BASH_REMATCH[1]}"
                        echo "${key} = \"your_$(echo "${key}" | tr '[:upper:]' '[:lower:]')\""
                    fi
                done <<< "$env_vars"
            else
                echo "GEMINI_API_KEY = \"your_gemini_api_key_here\""
            fi
            return 0
        fi

        print_success "Successfully configured Codex CLI"
        echo "  Config: $codex_config"
        echo "  Restart Codex CLI to use PAL MCP Server"
        codex_has_pal=true
    else
        print_info "Codex CLI already configured; refreshing Codex settings..."
    fi

    if [[ "$codex_has_pal" == true ]]; then
        if ! grep -Eq '^\s*web_search_request\s*=' "$codex_config" 2>/dev/null; then
            echo ""
            print_info "Web search requests let Codex pull fresh documentation for PAL's API lookup tooling."
            read -p "Enable Codex CLI web search requests? (Y/n): " -n 1 -r
            echo ""
            if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                if grep -Eq '^\s*\[features\]' "$codex_config" 2>/dev/null; then
                    if ! python3 - "$codex_config" <<'PY'
import sys
from pathlib import Path

cfg_path = Path(sys.argv[1])
content = cfg_path.read_text().splitlines()
output = []
in_features = False
added = False

for line in content:
    stripped = line.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        if in_features and not added:
            output.append("web_search_request = true")
            added = True
        in_features = stripped == "[features]"
        output.append(line)
        continue
    if in_features and stripped.startswith("web_search_request"):
        added = True
    output.append(line)

if in_features and not added:
    output.append("web_search_request = true")

cfg_path.write_text("\n".join(output) + "\n")
PY
                    then
                        print_error "Failed to enable Codex web search request feature. Add 'web_search_request = true' under [features] in $codex_config manually."
                    else
                        print_success "Enabled Codex web search request feature"
                    fi
                else
                    {
                        echo ""
                        echo "[features]"
                        echo "web_search_request = true"
                    } >> "$codex_config" && print_success "Enabled Codex web search request feature" || \
                        print_error "Failed to enable Codex web search request feature. Add 'web_search_request = true' under [features] in $codex_config manually."
                fi
            else
                print_info "Skipping Codex web search request feature"
            fi
        fi

        if grep -Eq '^\s*\[tools\]' "$codex_config" 2>/dev/null && \
           grep -Eq '^\s*web_search\s*=' "$codex_config" 2>/dev/null; then
            local removal_status
            if removal_status=$(python3 - "$codex_config" <<'PY' | tr -d '\n'
import sys
from pathlib import Path

cfg_path = Path(sys.argv[1])
lines = cfg_path.read_text().splitlines()
output = []
in_tools = False
removed = False

for line in lines:
    stripped = line.strip()
    if stripped.startswith('[') and stripped.endswith(']'):
        in_tools = stripped == '[tools]'
        output.append(line)
        continue
    if in_tools and stripped.startswith('web_search'):
        removed = True
        continue
    output.append(line)

if removed:
    cfg_path.write_text("\n".join(output) + "\n")
    print('REMOVED', end='')
else:
    print('UNCHANGED', end='')
PY
); then
                if [[ "$removal_status" == "REMOVED" ]]; then
                    print_success "Removed deprecated Codex [tools].web_search entry"
                fi
            else
                print_warning "Failed to clean up deprecated Codex [tools].web_search entry; remove manually from $codex_config"
            fi
        fi
    fi
}

# Print manual Qwen CLI configuration guidance
print_qwen_manual_instructions() {
    local python_cmd="$1"
    local server_path="$2"
    local script_dir="$3"
    local config_path="$4"
    local env_lines="$5"

    local env_array=()
    if [[ -n "$env_lines" ]]; then
        while IFS= read -r line; do
            [[ -z "$line" ]] && continue
            env_array+=("$line")
        done <<< "$env_lines"
    fi

    echo "Manual config location: $config_path"
    echo "Add or update this entry:"

    local env_block=""
    if [[ ${#env_array[@]} -gt 0 ]]; then
        env_block=$'      "env": {\n'
        local first=true
        for env_entry in "${env_array[@]}"; do
            local key="${env_entry%%=*}"
            local value="${env_entry#*=}"
            value=${value//\\/\\\\}
            value=${value//"/\\"}
            if [[ "$first" == true ]]; then
                first=false
                env_block+="        \"$key\": \"$value\""
            else
                env_block+=$',\n        '
                env_block+="\"$key\": \"$value\""
            fi
        done
        env_block+=$'\n      }'
    fi

    if [[ -n "$env_block" ]]; then
        cat << EOF
{
  "mcpServers": {
    "pal": {
      "command": "$python_cmd",
      "args": ["$server_path"],
      "cwd": "$script_dir",
$env_block
    }
  }
}
EOF
    else
        cat << EOF
{
  "mcpServers": {
    "pal": {
      "command": "$python_cmd",
      "args": ["$server_path"],
      "cwd": "$script_dir"
    }
  }
}
EOF
    fi
}

# Check and update Qwen Code CLI configuration
check_qwen_cli_integration() {
    local python_cmd="$1"
    local server_path="$2"

    if ! command -v qwen &> /dev/null; then
        return 0
    fi

    local qwen_config="$HOME/.qwen/settings.json"
    local script_dir
    script_dir=$(dirname "$server_path")

    local env_vars
    env_vars=$(parse_env_variables)
    local env_array=()
    if [[ -n "$env_vars" ]]; then
        while IFS= read -r line; do
            if [[ -n "$line" && "$line" =~ ^([^=]+)=(.*)$ ]]; then
                env_array+=("${BASH_REMATCH[1]}=${BASH_REMATCH[2]}")
            fi
        done <<< "$env_vars"
    fi

    local env_lines=""
    if [[ ${#env_array[@]} -gt 0 ]]; then
        env_lines=$(printf '%s\n' "${env_array[@]}")
    fi

    local legacy_names_csv
    legacy_names_csv=$(IFS=,; echo "${LEGACY_MCP_NAMES[*]}")

    if [[ -f "$qwen_config" ]]; then
        PAL_QWEN_LEGACY="$legacy_names_csv" PAL_QWEN_CONFIG="$qwen_config" python3 - <<'PYCLEANCONF' 2>/dev/null || true
import json
import os
import pathlib
import sys

config_path = pathlib.Path(os.environ.get("PAL_QWEN_CONFIG", ""))
legacy = [n for n in os.environ.get("PAL_QWEN_LEGACY", "").split(",") if n]

if not config_path.exists():
    sys.exit(0)

try:
    data = json.loads(config_path.read_text(encoding="utf-8"))
except Exception:
    sys.exit(0)

if not isinstance(data, dict):
    sys.exit(0)

servers = data.get("mcpServers")
if isinstance(servers, dict):
    removed = False
    for key in legacy:
        if servers.pop(key, None) is not None:
            removed = True
    if removed:
        config_path.write_text(json.dumps(data, indent=2))

sys.exit(0)
PYCLEANCONF
    fi

    local config_status=3
    if [[ -f "$qwen_config" ]]; then
        if python3 - "$qwen_config" "$python_cmd" "$server_path" "$script_dir" <<'PYCONF'
import json
import sys

config_path, expected_cmd, expected_arg, expected_cwd = sys.argv[1:5]
try:
    with open(config_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
except FileNotFoundError:
    sys.exit(1)
except Exception:
    sys.exit(5)

servers = data.get('mcpServers')
if not isinstance(servers, dict):
    sys.exit(3)

config = servers.get('pal')
if not isinstance(config, dict):
    sys.exit(3)

cmd = config.get('command')
args = config.get('args') or []
cwd = config.get('cwd')

cwd_matches = cwd in (None, "", expected_cwd)
if cmd == expected_cmd and len(args) == 1 and args[0] == expected_arg and cwd_matches:
    sys.exit(0)

sys.exit(4)
PYCONF
        then
            config_status=0
        else
            config_status=$?
            if [[ $config_status -eq 1 ]]; then
                config_status=3
            fi
        fi
    fi

    if [[ $config_status -eq 0 ]]; then
        return 0
    fi

    echo ""

    if [[ $config_status -eq 4 ]]; then
        print_warning "Found existing Qwen CLI pal configuration with different settings."
    elif [[ $config_status -eq 5 ]]; then
        print_warning "Unable to parse Qwen CLI settings; replacing with a fresh entry may help."
    fi

    local prompt="Configure PAL for Qwen CLI? (Y/n): "
    if [[ $config_status -eq 4 || $config_status -eq 5 ]]; then
        prompt="Update Qwen CLI pal configuration? (Y/n): "
    fi

    read -p "$prompt" -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        print_info "Skipping Qwen CLI integration"
        print_qwen_manual_instructions "$python_cmd" "$server_path" "$script_dir" "$qwen_config" "$env_lines"
        return 0
    fi

    mkdir -p "$(dirname "$qwen_config")" 2>/dev/null || true
    if [[ -f "$qwen_config" && $config_status -ne 3 ]]; then
        cp "$qwen_config" "${qwen_config}.backup_$(date +%Y%m%d_%H%M%S)" 2>/dev/null || true
    fi

    local update_output
    local update_status=0
    update_output=$(PAL_QWEN_ENV="$env_lines" PAL_QWEN_CMD="$python_cmd" PAL_QWEN_ARG="$server_path" PAL_QWEN_CWD="$script_dir" python3 - "$qwen_config" <<'PYUPDATE'
import json
import os
import pathlib
import sys

config_path = pathlib.Path(sys.argv[1])
cmd = os.environ['PAL_QWEN_CMD']
arg = os.environ['PAL_QWEN_ARG']
cwd = os.environ['PAL_QWEN_CWD']
env_lines = os.environ.get('PAL_QWEN_ENV', '').splitlines()

env_map = {}
for line in env_lines:
    if not line.strip():
        continue
    if '=' in line:
        key, value = line.split('=', 1)
        env_map[key] = value

if config_path.exists():
    try:
        with config_path.open('r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        data = {}
else:
    data = {}

if not isinstance(data, dict):
    data = {}

servers = data.get('mcpServers')
if not isinstance(servers, dict):
    servers = {}
    data['mcpServers'] = servers

pal_config = {
    'command': cmd,
    'args': [arg],
    'cwd': cwd,
}

if env_map:
    pal_config['env'] = env_map

servers['pal'] = pal_config

config_path.parent.mkdir(parents=True, exist_ok=True)
tmp_path = config_path.with_suffix(config_path.suffix + '.tmp')
with tmp_path.open('w', encoding='utf-8') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
tmp_path.replace(config_path)
PYUPDATE
    ) || update_status=$?

    if [[ $update_status -eq 0 ]]; then
        print_success "Successfully configured Qwen CLI"
        echo "  Config: $qwen_config"
        echo "  Restart Qwen CLI to use PAL MCP Server"
    else
        print_error "Failed to update Qwen CLI config"
        if [[ -n "$update_output" ]]; then
            echo "$update_output"
        fi
        print_qwen_manual_instructions "$python_cmd" "$server_path" "$script_dir" "$qwen_config" "$env_lines"
    fi
}

# Display configuration instructions
display_config_instructions() {
    local python_cmd="$1"
    local server_path="$2"

    # Get script directory for Gemini CLI config
    local script_dir=$(dirname "$server_path")

    echo ""
    local config_header="PAL MCP SERVER CONFIGURATION"
    echo "===== $config_header ====="
    printf '%*s\n' "$((${#config_header} + 12))" | tr ' ' '='
    echo ""
    echo "To use PAL MCP Server with your CLI clients:"
    echo ""

    print_info "1. For Claude Code (CLI):"
    # Show command with environment variables
    local env_vars=$(parse_env_variables)
    local env_args=""
    if [[ -n "$env_vars" ]]; then
        while IFS= read -r line; do
            if [[ -n "$line" && "$line" =~ ^([^=]+)=(.*)$ ]]; then
                env_args+=" -e ${BASH_REMATCH[1]}=\"${BASH_REMATCH[2]}\""
            fi
        done <<< "$env_vars"
    fi
    echo -e "   ${GREEN}claude mcp add pal -s user$env_args -- $python_cmd $server_path${NC}"
    echo ""

    print_info "2. For Claude Desktop:"
    echo "   Add this configuration to your Claude Desktop config file:"
    echo ""
    
    # Generate example with actual environment variables that exist
    example_env=""
    env_vars=$(parse_env_variables)
    if [[ -n "$env_vars" ]]; then
        local first_entry=true
        while IFS= read -r line; do
            if [[ -n "$line" && "$line" =~ ^([^=]+)=(.*)$ ]]; then
                local key="${BASH_REMATCH[1]}"
                local value="your_$(echo "${key}" | tr '[:upper:]' '[:lower:]')"
                
                if [[ "$first_entry" == true ]]; then
                    first_entry=false
                    example_env="           \"$key\": \"$value\""
                else
                    example_env+=",\n           \"$key\": \"$value\""
                fi
            fi
        done <<< "$env_vars"
    fi
    
    if [[ -n "$example_env" ]]; then
        cat << EOF
   {
     "mcpServers": {
       "pal": {
         "command": "$python_cmd",
         "args": ["$server_path"],
         "cwd": "$script_dir",
         "env": {
$(echo -e "$example_env")
         }
       }
     }
   }
EOF
    else
        cat << EOF
   {
     "mcpServers": {
       "pal": {
         "command": "$python_cmd",
         "args": ["$server_path"],
         "cwd": "$script_dir"
       }
     }
   }
EOF
    fi

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

    print_info "For Gemini CLI:"
    echo "   Add this configuration to ~/.gemini/settings.json:"
    echo ""
    cat << EOF
   {
     "mcpServers": {
       "pal": {
         "command": "$script_dir/pal-mcp-server"
       }
     }
   }
EOF
    echo ""

    print_info "For Qwen Code CLI:"
    echo "   Add this configuration to ~/.qwen/settings.json:"
    echo ""
    if [[ -n "$example_env" ]]; then
        cat << EOF
   {
     "mcpServers": {
       "pal": {
         "command": "$python_cmd",
         "args": ["$server_path"],
         "cwd": "$script_dir",
         "env": {
$(echo -e "$example_env")
         }
       }
     }
   }
EOF
    else
        cat << EOF
   {
     "mcpServers": {
       "pal": {
         "command": "$python_cmd",
         "args": ["$server_path"],
         "cwd": "$script_dir"
       }
     }
   }
EOF
    fi
    echo ""

    print_info "For Codex CLI:"
    echo "   Add this configuration to ~/.codex/config.toml:"
    echo ""
    cat << EOF
   [mcp_servers.pal]
   command = "bash"
   args = ["-c", "for p in \$(which uvx 2>/dev/null) \$HOME/.local/bin/uvx /opt/homebrew/bin/uvx /usr/local/bin/uvx uvx; do [ -x \\\"\$p\\\" ] && exec \\\"\$p\\\" --from git+https://github.com/BeehiveInnovations/pal-mcp-server.git pal-mcp-server; done; echo 'uvx not found' >&2; exit 1"]

   [mcp_servers.pal.env]
   PATH = "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:\$HOME/.local/bin:\$HOME/.cargo/bin:\$HOME/bin"
   GEMINI_API_KEY = "your_gemini_api_key_here"
EOF
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
    print_success "PAL is ready to use!"
    
    # Display enabled/disabled tools if DISABLED_TOOLS is configured
    if [[ -n "${DISABLED_TOOLS:-}" ]]; then
        echo ""
        print_info "Tool Configuration:"
        
        # Dynamically discover all available tools from the tools directory
        # Excludes: __pycache__, shared modules, models.py, listmodels.py, version.py
        local all_tools=()
        for tool_file in tools/*.py; do
            if [[ -f "$tool_file" ]]; then
                local tool_name=$(basename "$tool_file" .py)
                # Skip non-tool files
                if [[ "$tool_name" != "models" && "$tool_name" != "listmodels" && "$tool_name" != "version" && "$tool_name" != "__init__" ]]; then
                    all_tools+=("$tool_name")
                fi
            fi
        done
        
        # Convert DISABLED_TOOLS to array
        IFS=',' read -ra disabled_array <<< "$DISABLED_TOOLS"
        
        # Trim whitespace from disabled tools
        local disabled_tools=()
        for tool in "${disabled_array[@]}"; do
            disabled_tools+=("$(echo "$tool" | xargs)")
        done
        
        # Determine enabled tools
        local enabled_tools=()
        for tool in "${all_tools[@]}"; do
            local is_disabled=false
            for disabled in "${disabled_tools[@]}"; do
                if [[ "$tool" == "$disabled" ]]; then
                    is_disabled=true
                    break
                fi
            done
            if [[ "$is_disabled" == false ]]; then
                enabled_tools+=("$tool")
            fi
        done
        
        # Display enabled tools
        echo ""
        echo -e "  ${GREEN}Enabled Tools (${#enabled_tools[@]}):${NC}"
        local enabled_list=""
        for tool in "${enabled_tools[@]}"; do
            if [[ -n "$enabled_list" ]]; then
                enabled_list+=", "
            fi
            enabled_list+="$tool"
        done
        echo "    $enabled_list"
        
        # Display disabled tools
        echo ""
        echo -e "  ${YELLOW}Disabled Tools (${#disabled_tools[@]}):${NC}"
        local disabled_list=""
        for tool in "${disabled_tools[@]}"; do
            if [[ -n "$disabled_list" ]]; then
                disabled_list+=", "
            fi
            disabled_list+="$tool"
        done
        echo "    $disabled_list"
        
        echo ""
        echo "  To enable more tools, edit the DISABLED_TOOLS variable in .env"
    fi
}

# ----------------------------------------------------------------------------
# Log Management Functions
# ----------------------------------------------------------------------------

# Show help message
show_help() {
    local version=$(get_version)
    local header="🤖 PAL MCP Server v$version"
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
    echo "  https://github.com/BeehiveInnovations/pal-mcp-server"
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
            echo "Setting up environment for configuration display..."
            echo ""
            local python_cmd
            python_cmd=$(setup_environment) || exit 1
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
    local main_header="🤖 PAL MCP Server"
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

    # Step 2: Setup environment file
    setup_env_file || exit 1

    # Step 3: Source .env file
    if [[ -f .env ]]; then
        set -a
        source .env
        set +a
    fi

    # Step 4: Check API keys (non-blocking - just warn if missing)
    check_api_keys

    # Step 5: Setup Python environment (uv-first approach)
    local python_cmd
    python_cmd=$(setup_environment) || exit 1

    # Step 6: Install dependencies
    install_dependencies "$python_cmd" || exit 1

    # Step 7: Get absolute server path
    local script_dir=$(get_script_dir)
    local server_path="$script_dir/server.py"

    # Step 8: Display setup instructions
    display_setup_instructions "$python_cmd" "$server_path"

    # Step 9: Check Claude integrations
    check_claude_cli_integration "$python_cmd" "$server_path"
    check_claude_desktop_integration "$python_cmd" "$server_path"

    # Step 10: Check Gemini CLI integration
    check_gemini_cli_integration "$script_dir"

    # Step 11: Check Codex CLI integration
    check_codex_cli_integration

    # Step 12: Check Qwen CLI integration
    check_qwen_cli_integration "$python_cmd" "$server_path"

    # Step 13: Display log information
    echo ""
    echo "Logs will be written to: $script_dir/$LOG_DIR/$LOG_FILE"
    echo ""

    # Step 14: Handle command line arguments
    if [[ "$arg" == "-f" ]] || [[ "$arg" == "--follow" ]]; then
        follow_logs
    else
        echo "To follow logs: ./run-server.sh -f"
        echo "To show config: ./run-server.sh -c"
        echo "To update: git pull, then run ./run-server.sh again"
        echo ""
        echo "Happy coding! 🎉"
    fi
}

# ----------------------------------------------------------------------------
# Script Entry Point
# ----------------------------------------------------------------------------

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
