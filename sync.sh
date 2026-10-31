#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

to_posix() {
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -u "$1"
  else
    printf '%s\n' "${1//\\//}"
  fi
}

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) PLATFORM="windows" ;;
  Darwin*)              PLATFORM="macos" ;;
  Linux*)               PLATFORM="linux" ;;
  *)
    if [[ "${OS-}" == "Windows_NT" ]]; then
      PLATFORM="windows"
    else
      echo "Unsupported OS: $(uname -s)" >&2
      exit 1
    fi
    ;;
esac

HOME="$(to_posix "$HOME")"
XDG_CONFIG_DIR="$(to_posix "${XDG_CONFIG_HOME:-$HOME/.config}")"

if [[ "$PLATFORM" == "windows" ]]; then
  APPDATA_DIR="$(to_posix "${APPDATA:-$HOME/AppData/Roaming}")"
  LOCALAPPDATA_DIR="$(to_posix "${LOCALAPPDATA:-$HOME/AppData/Local}")"
  GH_CONFIG_DIR="$APPDATA_DIR/GitHub CLI"
  VSCODE_APP_DIR="$APPDATA_DIR/Code"
  CURSOR_APP_DIR="$APPDATA_DIR/Cursor"
  if [[ -d "$HOME/Documents/PowerShell" ]]; then
    PWSH_DIR="$HOME/Documents/PowerShell"
  elif command -v pwsh.exe >/dev/null 2>&1; then
    PWSH_DIR="$(dirname "$(to_posix "$(pwsh.exe -NoProfile -Command '$PROFILE' | tr -d '\r')")")"
  else
    PWSH_DIR="$HOME/Documents/PowerShell"
  fi
  WT_SETTINGS="$LOCALAPPDATA_DIR/Packages/Microsoft.WindowsTerminal_8wekyb3d8bbwe/LocalState/settings.json"
elif [[ "$PLATFORM" == "macos" ]]; then
  GH_CONFIG_DIR="$XDG_CONFIG_DIR/gh"
  VSCODE_APP_DIR="$HOME/Library/Application Support/Code"
  CURSOR_APP_DIR="$HOME/Library/Application Support/Cursor"
else
  GH_CONFIG_DIR="$XDG_CONFIG_DIR/gh"
  VSCODE_APP_DIR="$XDG_CONFIG_DIR/Code"
  CURSOR_APP_DIR="$XDG_CONFIG_DIR/Cursor"
fi

VSCODE_USER_DIR="$VSCODE_APP_DIR/User"
CURSOR_USER_DIR="$CURSOR_APP_DIR/User"

can_symlink() {
  if [[ "$PLATFORM" != "windows" ]]; then
    return 0
  fi
  local probe_src probe_dst
  probe_src="$(mktemp)"
  probe_dst="${probe_src}.symtest"
  if MSYS=winsymlinks:nativestrict ln -s "$probe_src" "$probe_dst" >/dev/null 2>&1; then
    rm -f "$probe_src" "$probe_dst"
    return 0
  fi
  rm -f "$probe_src" "$probe_dst"
  return 1
}

USE_SYMLINKS=0
if [[ "${DOTFILES_COPY_ONLY:-0}" != "1" ]] && can_symlink; then
  USE_SYMLINKS=1
fi

BACKUP_ROOT="$HOME/.dotfiles-backup/$(date +%Y%m%d-%H%M%S)"
BACKED_UP=0

backup_if_needed() {
  local dst="$1" src="$2"
  [[ -e "$dst" || -L "$dst" ]] || return 0
  if [[ -L "$dst" ]]; then
    local link_target
    link_target="$(readlink "$dst" || true)"
    [[ "$link_target" == "$src" ]] && return 0
  elif cmp -s "$src" "$dst"; then
    return 0
  fi

  local rel="${dst#"$HOME"/}"
  [[ "$rel" == "$dst" ]] && rel="$(basename "$dst")"
  local bpath="$BACKUP_ROOT/$rel"
  mkdir -p "$(dirname "$bpath")"
  cp -a "$dst" "$bpath"
  BACKED_UP=1
}

is_same_link() {
  local dst="$1" src="$2"
  [[ -L "$dst" ]] || return 1
  local target
  target="$(readlink "$dst" || true)"
  [[ "$target" == "$src" ]]
}

# Format: MODE|REPO_REL_PATH|SYSTEM_TARGET_PATH
# MODE: "auto" (symlink if supported, else copy) or "copy" (always copy)
MAPPINGS=(
  "auto|common/bash/.bashrc|$HOME/.bashrc"
  "auto|common/bash/.bash_profile|$HOME/.bash_profile"
  "auto|common/readline/.inputrc|$HOME/.inputrc"
  "auto|common/starship/starship.toml|$XDG_CONFIG_DIR/starship.toml"
  "auto|common/gh/config.yml|$GH_CONFIG_DIR/config.yml"
  "auto|common/vscode/settings.json|$VSCODE_USER_DIR/settings.json"
  "auto|common/vscode/keybindings.json|$VSCODE_USER_DIR/keybindings.json"
  "auto|common/vscode/mcp.json|$VSCODE_USER_DIR/mcp.json"
  "auto|common/omp/keybindings.yml|$HOME/.omp/agent/keybindings.yml"
)

# Share VS Code settings & keybindings with Cursor when Cursor is present
if [[ -d "$CURSOR_APP_DIR" || -d "$HOME/.cursor" ]]; then
  MAPPINGS+=(
    "auto|common/vscode/settings.json|$CURSOR_USER_DIR/settings.json"
    "auto|common/vscode/keybindings.json|$CURSOR_USER_DIR/keybindings.json"
    "auto|common/cursor/cli-config.json|$HOME/.cursor/cli-config.json"
  )
fi

if [[ "$PLATFORM" == "windows" ]]; then
  MAPPINGS+=(
    "auto|windows/powershell/Microsoft.PowerShell_profile.ps1|$PWSH_DIR/Microsoft.PowerShell_profile.ps1"
    "copy|windows/windows-terminal/settings.json|$WT_SETTINGS"
    "auto|windows/omp/config.yml|$HOME/.omp/agent/config.yml"
  )
else
  # Add unix/* mappings here as macOS/Linux-only configs are added, e.g.:
  # MAPPINGS+=("auto|unix/zsh/.zshrc|$HOME/.zshrc")
  :
fi

cmd_apply() {
  echo "Platform: $PLATFORM | Mode: $([[ $USE_SYMLINKS -eq 1 ]] && echo 'symlink' || echo 'copy')"
  for entry in "${MAPPINGS[@]}"; do
    IFS='|' read -r mode rel dst <<< "$entry"
    local src="$REPO_DIR/$rel"
    [[ -f "$src" ]] || continue
    mkdir -p "$(dirname "$dst")"
    backup_if_needed "$dst" "$src"

    if [[ "$mode" == "auto" && $USE_SYMLINKS -eq 1 ]]; then
      if [[ "$PLATFORM" == "windows" ]]; then
        MSYS=winsymlinks:nativestrict ln -sfn "$src" "$dst"
      else
        ln -sfn "$src" "$dst"
      fi
      printf '  [link] %s -> %s\n' "$dst" "$rel"
    else
      rm -f "$dst"
      cp "$src" "$dst"
      printf '  [copy] %s -> %s\n' "$rel" "$dst"
    fi
  done

  if [[ $BACKED_UP -eq 1 ]]; then
    echo "Backed up previous differing files to: $BACKUP_ROOT"
  fi
}

cmd_collect() {
  echo "Collecting live configs into repo ($PLATFORM)..."

  # Group targets by repo relative path so shared files (VS Code + Cursor) pick newest modified target
  declare -A seen_rels=()
  local ordered_rels=()
  for entry in "${MAPPINGS[@]}"; do
    IFS='|' read -r _ rel _ <<< "$entry"
    if [[ -z "${seen_rels[$rel]+set}" ]]; then
      seen_rels["$rel"]=1
      ordered_rels+=("$rel")
    fi
  done

  for rel in "${ordered_rels[@]}"; do
    local src="$REPO_DIR/$rel"
    local candidates=()
    for entry in "${MAPPINGS[@]}"; do
      IFS='|' read -r _ r dst <<< "$entry"
      [[ "$r" == "$rel" ]] || continue
      [[ -f "$dst" ]] || continue
      is_same_link "$dst" "$src" && continue
      if ! [[ -f "$src" ]] || ! cmp -s "$src" "$dst"; then
        candidates+=("$dst")
      fi
    done

    if [[ ${#candidates[@]} -eq 0 ]]; then
      continue
    fi

    local chosen="${candidates[0]}"
    if [[ ${#candidates[@]} -gt 1 ]]; then
      for c in "${candidates[@]:1}"; do
        if [[ "$c" -nt "$chosen" ]]; then
          chosen="$c"
        fi
      done
      echo "  [note] Multiple modified targets for $rel; pulling newest: $chosen"
    fi

    mkdir -p "$(dirname "$src")"
    cp "$chosen" "$src"
    printf '  [pull] %s <- %s\n' "$rel" "$chosen"
  done

  if command -v code >/dev/null 2>&1; then
    code --list-extensions | tr -d '\r' | sort > "$REPO_DIR/common/vscode/extensions.txt"
    echo "  [pull] common/vscode/extensions.txt <- code --list-extensions"
  fi
}

cmd_status() {
  echo "Platform: $PLATFORM | Default apply mode: $([[ $USE_SYMLINKS -eq 1 ]] && echo 'symlink' || echo 'copy')"
  for entry in "${MAPPINGS[@]}"; do
    IFS='|' read -r _ rel dst <<< "$entry"
    local src="$REPO_DIR/$rel"
    local state
    if [[ ! -e "$dst" && ! -L "$dst" ]]; then
      state="MISSING"
    elif is_same_link "$dst" "$src"; then
      state="LINKED"
    elif cmp -s "$src" "$dst"; then
      state="SYNCED"
    else
      state="MODIFIED"
    fi
    printf '  %-9s %-44s (%s)\n' "[$state]" "$rel" "$dst"
  done

  if [[ "$PLATFORM" == "windows" ]]; then
    local ray_latest
    ray_latest="$(ls -1t "$REPO_DIR/windows/raycast/"*.rayconfig 2>/dev/null | head -n 1 || true)"
    if [[ -n "$ray_latest" ]]; then
      printf '  %-9s %s\n' "[MANUAL]" "windows/raycast/$(basename "$ray_latest") (Import/Export via Raycast UI)"
    fi
  fi
}

cmd_extensions() {
  local ext_file="$REPO_DIR/common/vscode/extensions.txt"
  [[ -f "$ext_file" ]] || { echo "No $ext_file found." >&2; exit 1; }
  while IFS= read -r ext; do
    [[ -n "$ext" ]] || continue
    command -v code >/dev/null 2>&1 && code --install-extension "$ext" --force
  done < "$ext_file"
}

case "${1:-status}" in
  apply|install)      cmd_apply ;;
  collect|pull)       cmd_collect ;;
  status|diff)        cmd_status ;;
  install-extensions) cmd_extensions ;;
  *)
    echo "Usage: $0 {status|apply|collect|install-extensions}" >&2
    exit 1
    ;;
esac
