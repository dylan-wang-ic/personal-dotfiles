# dotfiles

Personal configuration shared across Windows, macOS, and Linux.

- `common/`: Starship, OMP, Bash/Readline, GitHub CLI, VS Code, and Cursor.
- `unix/`: tmux and zsh keys, the OMP model overlay, plus cmux/Ghostty keys for macOS.
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
| All | Starship, and OMP keybindings and the model overlay (`~/.omp/agent/personal.yml`) |
| macOS/Linux | tmux, `~/.zshrc.d/40-omp-env.zsh` and `~/.zshrc.d/95-keybindings.zsh` |
| macOS | cmux, a Ghostty key include, and VS Code keybindings |
| Windows | VS Code keybindings |

It does **not** replace Bash profiles, Readline config, GitHub CLI config, VS Code settings/MCP, Cursor settings, Windows Terminal settings, or OMP's managed `~/.omp/agent/config.yml` and `models.yml`. The overlay carries model roles only: `40-omp-env.zsh` adds it to `PI_CONFIG_FILES` when the file exists, so Gohan's managed providers, `enabledModels`, and appearance settings stay authoritative and a missing or dangling overlay falls back to them instead of aborting omp. The default `all` profile below retains those broader mappings, including the Windows Terminal `settings.json` copy, which replaces the whole file (profile list, default profile GUID, starting directory).

Changed files are backed up under `~/.dotfiles-backup/` before replacement. Backups contain effective file content even when the old config was a symlink. Symlinks keep the personal repository as the source of truth; `DOTFILES_COPY_ONLY=1` uses copies instead.

On macOS the existing Ghostty `config` keeps its font, colors, other appearance preferences, and any `keybind` line for a key this repository does not manage. The installer removes only the triggers this repository binds (comparing spellings such as `super`/`cmd` and `left`/`arrow_left`), then adds one `config-file = keybindings.conf` pointing at this repository. If that `config` was a symlink into another repository, the installer writes a regular file in its place so it never edits through the link; the link target is preserved in the backup as `.link-target`. Do not keep another set of these keybinds in a work-specific repository.

The zsh file is installed late in `~/.zshrc.d/`. Shell setups that do not already source that directory must source the canonical file from their own `.zshrc`:

```zsh
source "$HOME/.zshrc.d/95-keybindings.zsh"
```

Open a new shell and a new OMP session after applying keys. Reload existing tmux servers without restarting sessions:

```bash
tmux source-file "$HOME/.tmux.conf"
```

`status` prints the active profile and the state of the Ghostty key include (`MISSING`, `LEGACY-LINK`, `NO-INCLUDE`, `INCLUDED`).

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
- `Ctrl+Shift+T`: new tab.
- `Ctrl+Shift+W`: close the active tab.
- OMP keeps `Alt+P` and `Alt+O` for temporary model selection.

On macOS the Windows modifiers map to **Option as Alt** and **Command as Ctrl**. cmux applies that through `terminal.textEditingGestures`, so Option+Left moves by word and Command+Left moves to the line start. cmux sends the emacs line-editor encodings of those keys (`Esc b`, `Ctrl+A`, `Ctrl+U`, `Ctrl+K`, `Esc d`), which zsh, Readline and OMP already understand; the OMP file therefore lists both the modifier and the emacs form for each action.

VS Code deliberately gives `Ctrl+Shift+Left/Right` to tab navigation instead of line selection. macOS retains `Cmd+Shift+Left/Right` for line selection; Windows/Linux keep their built-in `Shift+Home/End` alternatives. `Ctrl+Left/Right` needs Mission Control's "Move left/right a space" shortcuts to be off; on macOS those are symbolic hotkeys 79 and 81.

`Ctrl+Shift+W` in tmux runs `kill-window` with no confirmation, so it ends every pane in that window.

### Terminology

cmux has one more level than iTerm2 or Windows Terminal, and it uses "tab" at two of those levels.

| cmux | iTerm2 / Windows Terminal | tmux | VS Code |
|---|---|---|---|
| Window | Window | — | Window |
| Workspace (sidebar entry) | Tab | Session | Window |
| Pane (split region) | Pane | Pane | Editor group |
| Surface (tab inside a pane) | — (their tab holds the panes) | Window | Editor tab |
| Panel (the terminal itself) | — | — | — |

Consequences:

- In iTerm2 and Windows Terminal a tab *contains* panes, so closing a tab closes all its panes. In cmux a **pane contains tabs**: every pane has its own tab bar, and closing a tab closes one surface.
- The sidebar calls workspace entries "tabs" (⌘N new, ⌘1–⌘9 jump, ⌘⇧W close), while a surface is also "a tab within a pane" (⌘T new, ⌘W close).
- `cmux.json` action ids follow the socket vocabulary, not the UI: `newTab` creates a **workspace**, `newSurface` creates a **tab**, `closeTab` closes a **surface**, `closeWorkspace` closes a workspace, and `nextSidebarTab`/`prevSidebarTab` move between workspaces. Every `Ctrl+Shift` binding in this repository is a surface action for that reason.
- cmux has no "close pane" action. `Ctrl+Alt+W` runs Ghostty's `close_surface`, so it closes the focused tab; the pane disappears only once its last tab closes.

### Application boundaries

VS Code editor groups use directional focus/split and separate group/editor close actions. Its integrated terminal has narrower APIs:

- Left/Up focus the previous terminal pane; Right/Down focus the next pane.
- All four split shortcuts use the configured terminal split orientation.
- While the terminal content area has focus, VS Code runs a keybinding only if its command is in `terminal.integrated.commandsToSkipShell`; every other command is typed into the shell instead. These bindings use only commands from that default list, so `Ctrl+Alt+W` kills the active terminal pane and `Ctrl+Shift+W` closes the active terminal tab when the terminal sits in the editor area. A panel terminal has no equivalent command in that list, so there `Ctrl+Shift+W` also kills the active pane. `Ctrl+Shift+W` closes a whole terminal tab from the terminal-tabs list, which is a separate focus context.

These terminal close actions terminate processes; they do not detach.

cmux's Ghostty fork pins `alt+arrow_*`, `super+arrow_*`, `alt+backspace` and `super+backspace` to its own macOS defaults and silently discards config overrides for those triggers, which is why Option+Left arrived as Ctrl+Left and looked like Ctrl. Rebinding them in the Ghostty include does nothing; the mapping has to live in `terminal.textEditingGestures`, and `textEditingGesturesInFullScreenApps` extends it into tmux, OMP and other alternate-screen programs. Both are set in `unix/cmux/cmux.json`.

Every `Ctrl+Shift` binding in cmux acts on a tab, never on a workspace or window. Closing the last tab used to take the workspace with it, so `app.keepWorkspaceOpenWhenClosingLastSurface` is on: `Ctrl+Shift+W` now leaves an empty workspace instead of destroying it. Ghostty's own `Ctrl+Shift+Tab` switches cmux *workspaces*, and cmux allows one shortcut per action with no built-in alias for surface navigation, so the include releases that key rather than let it move the workspace selection.

cmux uses native surface tabs, while tmux calls its tabs windows. `Ctrl+Alt+W` closes the focused cmux surface, not all tabs in a split-pane group. cmux's native remote-tmux mirror currently supports right/down splits, but not left/up placement. Use right/down there; local cmux and raw tmux support all four directions.

For remote work, prefer cmux's native tmux mirroring instead of nesting a raw tmux client. In a **raw local/SSH tmux client**, press `Ctrl+Alt+T` to enable the Ghostty `tmux-forward` key table; press it again to return to native pane controls. This forwards pane focus/split/close keys to tmux while it uses the alternate screen. Do not enable it in the native mirror.

There is an intentional boundary: cmux keeps `Ctrl+Shift+Left/Right/W` native even inside alternate-screen programs such as OMP. Those three keys therefore **cannot control raw nested tmux windows inside cmux**, even with forwarding enabled. Use tmux's prefix bindings for inner windows, or use the native mirror. Standalone Ghostty has no cmux interception and forwards all configured keys in this table.

macOS system shortcuts must also release these combinations. Changing OS shortcuts is a separate, explicit setup step, not part of this sync script.

### Tradeoffs to know about

- Ghostty sends `Ctrl+Backspace` as `CSI 127;5u`. Zsh and Readline (`common/readline/.inputrc`, `all` profile) understand it; other programs and remote hosts that do not will receive the literal sequence. Hosts with plain Readline need that binding added there too.
- `macos-option-as-alt = true` makes Option a terminal Alt, so Option combinations stop typing characters such as `é` or `€`. The word-editing convention depends on it.
- With cmux gestures on, Command+Left sends `Ctrl+A` even inside full-screen programs, so Command+Left in vim or less triggers that program's `Ctrl+A` binding.
- A running OMP session keeps its keybindings from launch. Restart OMP after changing `common/omp/keybindings.yml`.
- `~/.zshrc.d/95-keybindings.zsh` sets `bindkey -e` and loads late, so it owns the main keymap. An earlier `bindkey -v` in another `~/.zshrc.d` file is overridden.
- tmux uses `extended-keys always`, not `on`, because the zsh `Ctrl+Backspace` binding needs tmux to forward extended keys without the inner program asking first. `terminal-features` registers `extkeys` for `xterm-ghostty`; a remote host whose `TERM` falls back to another value may not get that feature.

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

The sync tests use isolated homes and platform fixtures. They do not overwrite the running user's settings or require access to work credentials. The VS Code tests read the installed bundle to check that every terminal-focus binding uses a command from `commandsToSkipShell`'s default value, and skip that check when VS Code is absent.

## Manual snapshots

The files in `windows/raycast/` are Windows snapshots. Installing or opening Raycast on a Mac does not import those snapshots or change its hotkey. Use Raycast's own Import/Export Settings & Data only after reviewing cross-platform compatibility.
