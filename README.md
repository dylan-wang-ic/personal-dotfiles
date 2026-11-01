# dotfiles

Personal configuration shared across Windows, macOS, and Linux.

- `common/`: Starship, OMP, Bash/Readline, GitHub CLI, VS Code, and Cursor.
- `unix/`: tmux and zsh keys, plus cmux/Ghostty keys for macOS.
- `windows/`: Windows Terminal, PowerShell, OMP config, and manual Raycast snapshots.

## Apply only keys and prompt

Use this profile on a machine that already has its own shell and application setup:

```bash
bash ./sync.sh status workstation
bash ./sync.sh apply workstation
bash ./sync.sh collect workstation
```

The `workstation` profile owns:

| Platform | Configuration |
|---|---|
| All | Starship and OMP keybindings |
| macOS/Linux | tmux and `~/.zshrc.d/95-keybindings.zsh` |
| macOS | cmux, a Ghostty key include, and VS Code keybindings |
| Windows | Windows Terminal and VS Code keybindings |

It does **not** replace Bash profiles, Readline config, GitHub CLI config, VS Code settings/MCP, Cursor settings, or OMP provider/model configuration. The default `all` profile below retains those broader mappings.

Changed files are backed up under `~/.dotfiles-backup/` before replacement. Backups contain effective file content even when the old config was a symlink. Symlinks keep the personal repository as the source of truth; `DOTFILES_COPY_ONLY=1` uses copies instead.

On macOS the existing Ghostty `config` keeps its font, colors, and other appearance preferences. The installer removes separate `keybind` lines and adds `config-file = keybindings.conf`; that include points to this repository. Do not keep another set of keybinds in a work-specific repository.

The zsh file is installed late in `~/.zshrc.d/`. Shell setups that do not already source that directory must source the canonical file from their own `.zshrc`:

```zsh
source "$HOME/.zshrc.d/95-keybindings.zsh"
```

Open a new shell and a new OMP session after applying keys. Reload existing tmux servers without restarting sessions:

```bash
tmux source-file "$HOME/.tmux.conf"
```

Reload cmux configuration with its reload action after changing terminal keys. A tmux server and cmux do not automatically share a keybinding table; both files live here and implement the same input convention.

## Key convention

- `Alt+Left/Right`: move by word; adding Shift selects words in supporting editors.
- `Ctrl+Left/Right`: move to line start/end.
- `Alt+Backspace/Delete`: delete a word.
- `Ctrl+Backspace/Delete`: delete to line start/end.
- `Ctrl+Alt+arrows`: focus a pane/editor group.
- `Ctrl+Alt+Shift+arrows`: split a pane/group where the application supports that direction.
- `Ctrl+Alt+W`: close the active pane/group.
- `Ctrl+Shift+Left/Right`: previous/next tab.
- `Ctrl+Shift+W`: close the active tab.
- OMP keeps `Alt+P` and `Alt+O` for temporary model selection.

VS Code deliberately gives `Ctrl+Shift+Left/Right` to tab navigation instead of line selection. macOS retains `Cmd+Shift+Left/Right` for line selection; Windows/Linux keep their built-in `Shift+Home/End` alternatives.

### Application boundaries

VS Code editor groups use directional focus/split and separate group/editor close actions. Its integrated terminal has narrower APIs:

- Left/Up focus the previous terminal pane; Right/Down focus the next pane.
- All four split shortcuts use the configured terminal split orientation.
- With terminal content focused, **both close shortcuts terminate only the active terminal instance**, not every pane in the terminal tab. `Ctrl+Shift+W` closes a whole terminal tab only when the terminal-tabs list itself has focus. This avoids accidentally killing a different selected terminal group.

These terminal close actions terminate processes; they do not detach.

cmux uses native surface tabs, while tmux calls its tabs windows. `Ctrl+Alt+W` closes the focused cmux surface, not all tabs in a split-pane group. cmux's native remote-tmux mirror currently supports right/down splits, but not left/up placement. Use right/down there; local cmux and raw tmux support all four directions.

For remote work, prefer cmux's native tmux mirroring instead of nesting a raw tmux client. In a **raw local/SSH tmux client**, press `Ctrl+Alt+T` to enable the Ghostty `tmux-forward` key table; press it again to return to native pane controls. This forwards pane focus/split/close keys to tmux while it uses the alternate screen. Do not enable it in the native mirror.

There is an intentional boundary: cmux keeps `Ctrl+Shift+Left/Right/W` native even inside alternate-screen programs such as OMP. Those three keys therefore **cannot control raw nested tmux windows inside cmux**, even with forwarding enabled. Use tmux's prefix bindings for inner windows, or use the native mirror. Standalone Ghostty has no cmux interception and forwards all configured keys in this table.

macOS system shortcuts must also release these combinations. Changing OS shortcuts is a separate, explicit setup step, not part of this sync script.

## Full sync

The original broad sync remains available. Review its mappings before using it on a configured work machine:

```bash
bash ./sync.sh status
bash ./sync.sh apply
bash ./sync.sh collect
bash ./sync.sh install-extensions
```

On Windows, symlinks require Developer Mode or suitable privileges; otherwise files are copied. Windows Terminal settings always use copies because atomic UI saves replace symlinks. The `collect` command works with macOS's system Bash 3.2; only the full profile refreshes VS Code's extensions list.

## Tests

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
bash -n sync.sh
```

The sync tests use isolated homes and platform fixtures. They do not overwrite the running user's settings or require access to work credentials.

## Manual snapshots

The files in `windows/raycast/` are Windows snapshots. Installing or opening Raycast on a Mac does not import those snapshots or change its hotkey. Use Raycast's own Import/Export Settings & Data only after reviewing cross-platform compatibility.
