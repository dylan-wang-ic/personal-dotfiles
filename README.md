# dotfiles

Cross-platform personal configuration repository organized into three top-level directories:

- `common/` — OS-agnostic configs shared across Windows, macOS, and Linux (`bash`, `readline`, `starship`, `gh`, merged `vscode` + `cursor`, `omp` keybindings).
- `windows/` — Windows-specific configs and snapshots (`powershell`, `windows-terminal`, `omp` config, `raycast` `.rayconfig` export).
- `unix/` — macOS and Linux specific configs.

## Usage

Run from Bash (Git Bash on Windows, standard Bash on macOS/Linux):

```bash
# Check sync status between live machine and repo
./sync.sh status

# Deploy repo configs to the machine (backs up any overwritten files to ~/.dotfiles-backup/)
./sync.sh apply

# Pull live machine edits back into the repo (also refreshes VS Code extensions.txt)
./sync.sh collect

# Install VS Code extensions from common/vscode/extensions.txt
./sync.sh install-extensions
```

> **Note on symlinks vs copies**: On macOS/Linux (and on Windows with Developer Mode enabled), `./sync.sh apply` creates native symlinks automatically (except Windows Terminal `settings.json`, which is copied so atomic UI saves do not break links). On Windows without Developer Mode, it uses safe file copies in both directions (`apply` / `collect`).

## Manual Snapshots

- **Raycast (`windows/raycast/`)**: Export/import `.rayconfig` via Raycast `Export / Import Settings & Data`.
