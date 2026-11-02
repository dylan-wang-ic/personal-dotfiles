from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[1]
CMUX_CONFIG = ROOT / "unix/cmux/cmux.json"
GHOSTTY_CONFIG = ROOT / "unix/ghostty/keybindings.conf"
TMUX_CONFIG = ROOT / "unix/tmux/tmux.conf"
ZSH_CONFIG = ROOT / "unix/zsh/keybindings.zsh"

CANONICAL_CMUX_BINDINGS = {
    "focusLeft": "ctrl+alt+left",
    "focusRight": "ctrl+alt+right",
    "focusUp": "ctrl+alt+up",
    "focusDown": "ctrl+alt+down",
    "splitRight": "ctrl+alt+shift+right",
    "splitDown": "ctrl+alt+shift+down",
    "closeTab": "ctrl+shift+w",
    "prevSurface": "ctrl+shift+left",
    "nextSurface": "ctrl+shift+right",
}

TMUX_FORWARD_SEQUENCES = {
    "ctrl+alt+arrow_left": "csi:1;7D",
    "ctrl+alt+arrow_right": "csi:1;7C",
    "ctrl+alt+arrow_up": "csi:1;7A",
    "ctrl+alt+arrow_down": "csi:1;7B",
    "ctrl+alt+shift+arrow_left": "csi:1;8D",
    "ctrl+alt+shift+arrow_right": "csi:1;8C",
    "ctrl+alt+shift+arrow_up": "csi:1;8A",
    "ctrl+alt+shift+arrow_down": "csi:1;8B",
    "ctrl+alt+w": "csi:119;7u",
    "ctrl+shift+w": "csi:119;6u",
    "ctrl+shift+arrow_left": "csi:1;6D",
    "ctrl+shift+arrow_right": "csi:1;6C",
}


class TerminalConfigTests(unittest.TestCase):
    def test_cmux_keeps_surface_tabs_native_in_alternate_screen(self) -> None:
        config = json.loads(CMUX_CONFIG.read_text())

        self.assertEqual(config["schemaVersion"], 1)
        self.assertEqual(config["shortcuts"]["bindings"], CANONICAL_CMUX_BINDINGS)
        self.assertEqual(
            config["shortcuts"]["when"],
            {
                "focusLeft": "terminalFocus && !terminalAlternateScreen",
                "focusRight": "terminalFocus && !terminalAlternateScreen",
                "focusUp": "terminalFocus && !terminalAlternateScreen",
                "focusDown": "terminalFocus && !terminalAlternateScreen",
                "splitRight": "terminalFocus && !terminalAlternateScreen",
                "splitDown": "terminalFocus && !terminalAlternateScreen",
                # OMP also uses the alternate screen. cmux must keep ownership of
                # surface-tab navigation and close there; embedded Ghostty tab
                # actions target workspaces instead of cmux surface tabs.
                "closeTab": "terminalFocus",
                "prevSurface": "terminalFocus",
                "nextSurface": "terminalFocus",
            },
        )

    def test_cmux_owns_macos_option_and_command_text_editing(self) -> None:
        """cmux's Ghostty fork pins alt/super arrow and backspace to its own
        macOS defaults and discards config overrides for those triggers, so
        Option never reaches the shell as Alt. cmux's text-editing gestures
        restore the split: Option moves by word, Command moves by line."""
        config = json.loads(CMUX_CONFIG.read_text())

        terminal = config["terminal"]
        self.assertIs(terminal["textEditingGestures"], True)
        self.assertIs(terminal["textEditingGesturesInFullScreenApps"], True)
        # The browser-style layout would give Command word movement, which is the
        # opposite of the Windows Ctrl convention.
        self.assertNotIn("textEditingCommandMovesByWord", terminal)

        text = GHOSTTY_CONFIG.read_text()
        for trigger in ("alt+arrow_left", "super+arrow_left", "alt+backspace", "super+backspace"):
            with self.subTest(trigger=trigger):
                self.assertNotIn(
                    f"keybind = {trigger}=",
                    text,
                    "cmux discards this override; the mapping belongs in cmux.json",
                )

    def test_cmux_config_passes_installed_semantic_validator(self) -> None:
        cmux = shutil.which("cmux")
        if cmux is None:
            self.skipTest("cmux is not installed")

        result = subprocess.run(
            [cmux, "config", "doctor", "--path", str(CMUX_CONFIG)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_ghostty_contains_only_key_behavior_and_preserves_old_sequences(self) -> None:
        text = GHOSTTY_CONFIG.read_text()

        self.assertIn("macos-option-as-alt = true", text)
        self.assertNotIn("font-", text)
        self.assertIn("keybind = alt+shift+arrow_left=csi:1;4D", text)
        self.assertIn("keybind = alt+shift+arrow_right=csi:1;4C", text)
        self.assertIn("keybind = super+shift+arrow_left=csi:1;2H", text)
        self.assertIn("keybind = super+shift+arrow_right=csi:1;2F", text)
        self.assertIn("keybind = shift+enter=csi:13;2u", text)
        self.assertIn("keybind = ctrl+backspace=csi:127;5u", text)

    def test_ghostty_native_mode_and_explicit_tmux_forwarding_mode(self) -> None:
        text = GHOSTTY_CONFIG.read_text()

        native_bindings = {
            "ctrl+alt+arrow_left": "goto_split:left",
            "ctrl+alt+arrow_right": "goto_split:right",
            "ctrl+alt+arrow_up": "goto_split:up",
            "ctrl+alt+arrow_down": "goto_split:down",
            "ctrl+alt+shift+arrow_left": "new_split:left",
            "ctrl+alt+shift+arrow_right": "new_split:right",
            "ctrl+alt+shift+arrow_up": "new_split:up",
            "ctrl+alt+shift+arrow_down": "new_split:down",
            "ctrl+alt+w": "close_surface",
        }
        for trigger, action in native_bindings.items():
            self.assertIn(f"keybind = {trigger}={action}", text)

        self.assertIn(
            "keybind = ctrl+alt+t=activate_key_table:tmux-forward", text
        )
        self.assertIn(
            "keybind = tmux-forward/ctrl+alt+t=deactivate_key_table", text
        )
        for trigger, action in TMUX_FORWARD_SEQUENCES.items():
            self.assertIn(f"keybind = tmux-forward/{trigger}={action}", text)

    def test_ghostty_does_not_misroute_surface_tabs_to_cmux_workspaces(self) -> None:
        text = GHOSTTY_CONFIG.read_text()

        # cmux's embedded Ghostty maps these generic Ghostty tab actions to
        # whole cmux workspaces, not the surface tabs inside a split pane.
        for action in ("previous_tab", "next_tab", "close_tab"):
            self.assertNotIn(f"={action}", text)

    def test_ghostty_config_passes_available_validator(self) -> None:
        candidates = [
            shutil.which("ghostty"),
            "/Applications/cmux.app/Contents/Resources/bin/ghostty",
        ]
        ghostty = next(
            (candidate for candidate in candidates if candidate and Path(candidate).is_file()),
            None,
        )
        if ghostty is None:
            self.skipTest("Ghostty config validator is not installed")

        result = subprocess.run(
            [ghostty, "+validate-config", f"--config-file={GHOSTTY_CONFIG}"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_tmux_bindings_match_the_canonical_scheme(self) -> None:
        text = TMUX_CONFIG.read_text()
        expected_lines = {
            "set-option -s extended-keys always",
            "set-option -as terminal-features ',xterm-ghostty:extkeys'",
            "bind-key -n C-M-Left select-pane -L",
            "bind-key -n C-M-Right select-pane -R",
            "bind-key -n C-M-Up select-pane -U",
            "bind-key -n C-M-Down select-pane -D",
            'bind-key -n C-M-S-Left split-window -h -b -c "#{pane_current_path}"',
            'bind-key -n C-M-S-Right split-window -h -c "#{pane_current_path}"',
            'bind-key -n C-M-S-Up split-window -v -b -c "#{pane_current_path}"',
            'bind-key -n C-M-S-Down split-window -v -c "#{pane_current_path}"',
            "bind-key -n C-M-w kill-pane",
            "bind-key -n C-S-w kill-window",
            "bind-key -n C-S-Left previous-window",
            "bind-key -n C-S-Right next-window",
        }
        for line in expected_lines:
            self.assertIn(line, text)

    def _assert_tmux_config_parses_on_isolated_socket(self, tmux: str) -> None:
        socket_name = f"dt-{uuid.uuid4().hex[:8]}"
        with tempfile.TemporaryDirectory(prefix="dt-") as tmux_tmpdir:
            env = {**os.environ, "TMUX_TMPDIR": tmux_tmpdir}
            base = [tmux, "-L", socket_name, "-f", str(TMUX_CONFIG)]
            try:
                create = subprocess.run(
                    [*base, "new-session", "-d", "-s", "config-test", "sleep 30"],
                    text=True,
                    capture_output=True,
                    check=False,
                    env=env,
                )
                if "Operation not permitted" in create.stderr:
                    self.skipTest("sandbox does not permit isolated tmux sockets")
                self.assertEqual(create.returncode, 0, create.stdout + create.stderr)

                listed = subprocess.run(
                    [tmux, "-L", socket_name, "list-keys", "-T", "root"],
                    text=True,
                    capture_output=True,
                    check=False,
                    env=env,
                )
                self.assertEqual(listed.returncode, 0, listed.stdout + listed.stderr)
                expected_key_spellings = {
                    "Ctrl+Alt+Left": ("C-M-Left",),
                    "Ctrl+Alt+Shift+Left": ("C-M-S-Left",),
                    # tmux 3.2a prints equivalent letter modifiers in a
                    # different order than newer releases.
                    "Ctrl+Alt+W": ("C-M-w", "M-C-w"),
                    "Ctrl+Shift+W": ("C-S-w", "S-C-w"),
                    "Ctrl+Shift+Left": ("C-S-Left",),
                    "Ctrl+Shift+Right": ("C-S-Right",),
                }
                for label, spellings in expected_key_spellings.items():
                    self.assertTrue(
                        any(spelling in listed.stdout for spelling in spellings),
                        f"missing {label} binding in:\n{listed.stdout}",
                    )

                extended_keys = subprocess.run(
                    [tmux, "-L", socket_name, "show-options", "-sv", "extended-keys"],
                    text=True,
                    capture_output=True,
                    check=False,
                    env=env,
                )
                self.assertEqual(
                    extended_keys.returncode,
                    0,
                    extended_keys.stdout + extended_keys.stderr,
                )
                self.assertEqual(extended_keys.stdout.strip(), "always")
            finally:
                subprocess.run(
                    [tmux, "-L", socket_name, "kill-server"],
                    text=True,
                    capture_output=True,
                    check=False,
                    env=env,
                )

    def test_installed_tmux_parser_accepts_config_on_isolated_socket(self) -> None:
        tmux = shutil.which("tmux")
        if tmux is None:
            self.skipTest("tmux is not installed")

        self._assert_tmux_config_parses_on_isolated_socket(tmux)

    def test_tmux_32a_parser_accepts_config_on_isolated_socket(self) -> None:
        tmux = os.environ.get("TMUX_32_BIN")
        if tmux is None:
            self.skipTest("set TMUX_32_BIN to an isolated tmux 3.2a binary")

        version = subprocess.run(
            [tmux, "-V"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(version.returncode, 0, version.stdout + version.stderr)
        self.assertEqual(version.stdout.strip(), "tmux 3.2a")
        self._assert_tmux_config_parses_on_isolated_socket(tmux)

    def test_zsh_bindings_match_word_line_delete_and_selection_contract(self) -> None:
        text = ZSH_CONFIG.read_text()

        expected = {
            "\\e[1;3D": "backward-word",
            "\\e[1;3C": "forward-word",
            "\\e[1;5D": "beginning-of-line",
            "\\e[1;5C": "end-of-line",
            "\\e\\x7f": "backward-kill-word",
            "\\e[3;3~": "kill-word",
            "\\e[127;5u": "backward-kill-line",
            "\\e[3;5~": "kill-line",
            "\\e[1;4D": "terminal-select-word-left",
            "\\e[1;4C": "terminal-select-word-right",
            "\\e[1;2H": "terminal-select-line-start",
            "\\e[1;2F": "terminal-select-line-end",
        }
        for sequence, widget in expected.items():
            self.assertIn(f"bindkey '{sequence}' {widget}", text)

        self.assertNotIn("\\e[1;6D", text)
        self.assertNotIn("\\e[1;6C", text)


if __name__ == "__main__":
    unittest.main()
