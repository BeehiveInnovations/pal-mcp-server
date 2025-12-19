#!/bin/bash
set -euo pipefail

# ============================================================================
# Zen Skills Installation Script
#
# Install Zen Skills to ~/.claude/skills/ for Claude Code integration.
# This script is independent of the MCP server setup.
#
# Usage:
#   ./install-skills.sh              Install core skills only
#   ./install-skills.sh --all        Install core + optional skills
#   ./install-skills.sh --force      Force overwrite without prompting
#   ./install-skills.sh --help       Show help
#
# Environment variables:
#   FORCE=1                 Skip overwrite confirmation
#   CLAUDE_SKILLS_HOME      Custom skills installation directory
# ============================================================================

# ----------------------------------------------------------------------------
# Colors and Output Functions
# ----------------------------------------------------------------------------

readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly RED='\033[0;31m'
readonly NC='\033[0m'

print_success() {
    echo -e "${GREEN}✓${NC} $1" >&2
}

print_error() {
    echo -e "${RED}✗${NC} $1" >&2
}

print_warning() {
    echo -e "${YELLOW}!${NC} $1"
}

print_info() {
    echo -e "${YELLOW}$1${NC}"
}

# ----------------------------------------------------------------------------
# Helper Functions
# ----------------------------------------------------------------------------

get_script_dir() {
    cd "$(dirname "$0")" && pwd
}

# Safe removal function with path validation
# Ensures we only delete directories under ~/.claude/skills/
safe_rm() {
    local target="$1"

    # Reject empty or unset paths
    if [[ -z "$target" ]]; then
        print_error "safe_rm: target path is empty"
        return 1
    fi

    # Get absolute canonical path
    local real_target
    if [[ -e "$target" ]]; then
        real_target=$(realpath "$target")
    else
        # If target doesn't exist, get realpath of parent and append basename
        local parent=$(dirname "$target")
        local basename=$(basename "$target")
        if [[ -e "$parent" ]]; then
            real_target=$(realpath "$parent")/"$basename"
        else
            # Parent doesn't exist either, skip (nothing to delete)
            return 0
        fi
    fi

    # Define safe base directory (where skills should be installed)
    local skills_base=$(realpath "${CLAUDE_SKILLS_HOME:-$HOME/.claude/skills}")

    # Dangerous paths that should never be deleted
    local dangerous_paths=(
        "/"
        "/home"
        "/root"
        "/usr"
        "/bin"
        "/sbin"
        "/etc"
        "/var"
        "/opt"
        "$HOME"
        "$(realpath ~)"
    )

    # Check if target is a dangerous path
    for dangerous in "${dangerous_paths[@]}"; do
        if [[ "$real_target" == "$dangerous" ]]; then
            print_error "safe_rm: refusing to delete dangerous path: $real_target"
            return 1
        fi
    done

    # Ensure target is under the skills base directory
    if [[ "$real_target" != "$skills_base"/* ]]; then
        print_error "safe_rm: target must be under $skills_base, got: $real_target"
        return 1
    fi

    # All safety checks passed, perform deletion
    if [[ -e "$target" ]]; then
        rm -rf "$target"
    fi

    return 0
}

# Get available CLI clients from conf/cli_clients/*.json
get_available_cli_clients() {
    local script_dir="$1"
    local cli_dir="$script_dir/conf/cli_clients"
    local clients=""

    if [[ -d "$cli_dir" ]]; then
        for json_file in "$cli_dir"/*.json; do
            if [[ -f "$json_file" ]]; then
                # Extract name field from JSON (simple grep-based extraction)
                local name=$(grep -o '"name"[[:space:]]*:[[:space:]]*"[^"]*"' "$json_file" | head -1 | sed 's/.*"\([^"]*\)"$/\1/')
                if [[ -n "$name" ]]; then
                    if [[ -n "$clients" ]]; then
                        clients="$clients, $name"
                    else
                        clients="$name"
                    fi
                fi
            fi
        done
    fi

    echo "$clients"
}

# Update pal-clink SKILL.md with dynamic description of available CLI clients
update_clink_description() {
    local target_dir="$1"
    local script_dir="$2"
    local skill_md="$target_dir/SKILL.md"

    if [[ ! -f "$skill_md" ]]; then
        return 0
    fi

    # Get available CLI clients
    local clients=$(get_available_cli_clients "$script_dir")

    if [[ -z "$clients" ]]; then
        return 0
    fi

    # Create new description with available clients
    local new_desc="description: Bridges to external AI CLIs ($clients) for cross-model collaboration and specialized capabilities."

    # Replace the description line in SKILL.md
    if [[ "$(uname)" == "Darwin" ]]; then
        # macOS sed requires different syntax
        sed -i '' "s/^description:.*/$new_desc/" "$skill_md"
    else
        sed -i "s/^description:.*/$new_desc/" "$skill_md"
    fi
}

show_help() {
    echo "Zen Skills Installation Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --all       Install all skills (core + optional)"
    echo "  --force     Force overwrite existing skills without prompting"
    echo "  --help      Show this help message"
    echo ""
    echo "Environment variables:"
    echo "  FORCE=1              Same as --force"
    echo "  CLAUDE_SKILLS_HOME   Custom installation directory (default: ~/.claude/skills)"
    echo ""
    echo "Examples:"
    echo "  $0                   Install core skills only"
    echo "  $0 --all             Install all skills"
    echo "  $0 --all --force     Install all skills, overwrite existing"
    echo "  FORCE=1 $0 --all     Same as above"
}

# ----------------------------------------------------------------------------
# Skills Installation Functions
# ----------------------------------------------------------------------------

create_skill_symlinks() {
    local skills_target="$1"
    local bin_dir="${HOME}/.local/bin"

    # Create bin directory if it doesn't exist
    mkdir -p "$bin_dir"

    # Create symlinks for each skill
    local symlinks_created=0
    for skill_dir in "$skills_target"/pal-*/; do
        if [[ -d "$skill_dir" ]] && [[ -f "$skill_dir/run.sh" ]]; then
            local skill_name=$(basename "$skill_dir")
            local symlink_path="$bin_dir/$skill_name"

            # Remove existing symlink if present
            if [[ -L "$symlink_path" ]]; then
                rm "$symlink_path"
            fi

            # Create symlink
            ln -s "$skill_dir/run.sh" "$symlink_path"
            symlinks_created=$((symlinks_created + 1))
        fi
    done

    if [[ $symlinks_created -gt 0 ]]; then
        echo ""
        print_success "Created $symlinks_created command symlinks in $bin_dir"

        # Check if ~/.local/bin is in PATH
        if [[ ":$PATH:" != *":$bin_dir:"* ]]; then
            print_warning "$bin_dir is not in your PATH"
            echo "Add this to your ~/.bashrc or ~/.zshrc:"
            echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
        fi
    fi
}

install_skills_from_dir() {
    local skills_source="$1"
    local skills_target="$2"
    local runner_source="$3"
    local script_dir="$4"
    local skill_type="$5"  # "core" or "optional"
    local installed=0
    local skill_names=""

    for skill_dir in "$skills_source"/pal-*/; do
        if [[ -d "$skill_dir" ]] && [[ -f "$skill_dir/SKILL.md" ]]; then
            local skill_name=$(basename "$skill_dir")
            local target_dir="$skills_target/$skill_name"

            # Remove existing skill directory with safety checks
            if [[ -d "$target_dir" ]]; then
                safe_rm "$target_dir" || {
                    print_error "Failed to safely remove existing skill: $target_dir"
                    return 1
                }
            fi

            # Copy skill directory
            cp -r "$skill_dir" "$target_dir"

            # Create scripts directory and copy runner
            mkdir -p "$target_dir/scripts"
            cp "$runner_source" "$target_dir/scripts/"

            # Set PAL_MCP_ROOT in a config file for the skill
            echo "PAL_MCP_ROOT=\"$script_dir\"" > "$target_dir/scripts/.pal_config"

            # Make run.sh executable
            if [[ -f "$target_dir/run.sh" ]]; then
                chmod +x "$target_dir/run.sh"
            fi

            # Update pal-clink description with available CLI clients
            if [[ "$skill_name" == "pal-clink" ]]; then
                update_clink_description "$target_dir" "$script_dir"
            fi

            if [[ "$skill_type" == "optional" ]]; then
                print_success "Installed (optional): $skill_name"
            else
                print_success "Installed: $skill_name"
            fi
            skill_names="$skill_names  - $skill_name\n"
            installed=$((installed + 1))
        fi
    done

    echo "$installed|$skill_names"
}

install_skills() {
    local script_dir=$(get_script_dir)
    local skills_source="$script_dir/skills"
    local skills_optional="$script_dir/skills-optional"
    local skills_target="${CLAUDE_SKILLS_HOME:-$HOME/.claude/skills}"
    local runner_source="$script_dir/scripts/pal_skill_runner.py"
    local force_overwrite="${FORCE:-0}"
    local install_all="${INSTALL_ALL:-0}"

    echo ""
    if [[ "$install_all" == "1" ]]; then
        print_info "Installing Zen Skills (core + optional)..."
    else
        print_info "Installing Zen Skills (core only)..."
        echo "Tip: Use --all to also install optional skills (analyze, refactor, testgen, etc.)"
    fi
    echo ""

    # Check source directory
    if [[ ! -d "$skills_source" ]]; then
        print_error "Skills source directory not found: $skills_source"
        return 1
    fi

    # Check runner script
    if [[ ! -f "$runner_source" ]]; then
        print_error "Skill runner not found: $runner_source"
        return 1
    fi

    # Check if any skills already exist
    local existing_skills=""
    for skill_dir in "$skills_source"/pal-*/; do
        if [[ -d "$skill_dir" ]] && [[ -f "$skill_dir/SKILL.md" ]]; then
            local skill_name=$(basename "$skill_dir")
            local target_dir="$skills_target/$skill_name"
            if [[ -d "$target_dir" ]]; then
                existing_skills="$existing_skills $skill_name"
            fi
        fi
    done
    if [[ "$install_all" == "1" ]] && [[ -d "$skills_optional" ]]; then
        for skill_dir in "$skills_optional"/pal-*/; do
            if [[ -d "$skill_dir" ]] && [[ -f "$skill_dir/SKILL.md" ]]; then
                local skill_name=$(basename "$skill_dir")
                local target_dir="$skills_target/$skill_name"
                if [[ -d "$target_dir" ]]; then
                    existing_skills="$existing_skills $skill_name"
                fi
            fi
        done
    fi

    # Prompt user if skills already exist
    if [[ -n "$existing_skills" ]] && [[ "$force_overwrite" != "1" ]]; then
        echo ""
        print_warning "The following skills already exist:"
        for skill in $existing_skills; do
            echo "  - $skill"
        done
        echo ""
        read -p "Overwrite existing skills? [y/N] " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Installation cancelled."
            echo "Tip: Use --force or FORCE=1 to skip this prompt."
            return 0
        fi
    fi

    # Clean up old unified "zen" skill if exists (migration from old structure)
    if [[ -d "$skills_target/zen" ]] && [[ ! -d "$skills_target/pal-chat" ]]; then
        print_info "Removing old unified skill structure..."
        safe_rm "$skills_target/zen" || {
            print_error "Failed to safely remove old skill structure: $skills_target/zen"
            return 1
        }
    fi

    # Create target directory
    mkdir -p "$skills_target"

    # Install core skills
    local result=$(install_skills_from_dir "$skills_source" "$skills_target" "$runner_source" "$script_dir" "core")
    local core_installed=$(echo "$result" | cut -d'|' -f1)
    local core_names=$(echo "$result" | cut -d'|' -f2-)

    # Install optional skills if requested
    local optional_installed=0
    local optional_names=""
    if [[ "$install_all" == "1" ]] && [[ -d "$skills_optional" ]]; then
        result=$(install_skills_from_dir "$skills_optional" "$skills_target" "$runner_source" "$script_dir" "optional")
        optional_installed=$(echo "$result" | cut -d'|' -f1)
        optional_names=$(echo "$result" | cut -d'|' -f2-)
    fi

    local total_installed=$((core_installed + optional_installed))

    if [[ $total_installed -gt 0 ]]; then
        echo ""
        print_success "Installed $total_installed skills to $skills_target"
        echo ""
        if [[ $core_installed -gt 0 ]]; then
            echo "Core skills ($core_installed):"
            echo -e "$core_names"
        fi
        if [[ $optional_installed -gt 0 ]]; then
            echo "Optional skills ($optional_installed):"
            echo -e "$optional_names"
        fi

        # Create symlinks in ~/.local/bin for direct command access
        create_skill_symlinks "$skills_target"

        echo ""
        echo "Skills are now available in Claude Code."
        echo "You can call skills directly: pal-chat --prompt \"...\""
        echo "Or via full path: ~/.claude/skills/pal-chat/run.sh --prompt \"...\""
        echo ""
        echo "Claude will automatically discover and use them based on context."
    else
        print_warning "No skills found to install in $skills_source"
        echo "Expected structure: skills/pal-*/SKILL.md"
    fi

    return 0
}

# ----------------------------------------------------------------------------
# Main Entry Point
# ----------------------------------------------------------------------------

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --all)
                INSTALL_ALL=1
                shift
                ;;
            --force)
                FORCE=1
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                echo ""
                show_help
                exit 1
                ;;
        esac
    done

    # Run installation
    install_skills
}

main "$@"
