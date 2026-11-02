import json
import re
import unittest
from pathlib import Path


KEYBINDINGS_PATH = Path(__file__).parents[1] / "common" / "vscode" / "keybindings.json"

VSCODE_BUNDLE = Path(
    "/Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/workbench/"
    "workbench.desktop.main.js"
)

EDITOR_GROUP_WHEN = "editorFocus && !terminalFocus"
TERMINAL_WHEN = "terminalFocus"
TERMINAL_EDITOR_WHEN = "terminalFocus && editorFocus"
TERMINAL_PANEL_WHEN = "terminalFocus && !editorFocus"
TERMINAL_PANE_WHEN = "terminalFocus && terminalSplitPaneActive"
TERMINAL_TABS_WHEN = "terminalTabsFocus"
EDITOR_TEXT_WHEN = "editorTextFocus"
EDITOR_EDIT_WHEN = "editorTextFocus && !editorReadonly"

# Verified against the installed VS Code source at:
# /Applications/Visual Studio Code.app/Contents/Resources/app/out/vs/workbench/workbench.desktop.main.js
SUPPORTED_COMMANDS = {
    "cursorEnd",
    "cursorEndSelect",
    "cursorHome",
    "cursorHomeSelect",
    "cursorWordPartLeft",
    "cursorWordPartLeftSelect",
    "cursorWordPartRight",
    "cursorWordPartRightSelect",
    "deleteAllLeft",
    "deleteAllRight",
    "deleteWordPartLeft",
    "deleteWordPartRight",
    "workbench.action.closeActiveEditor",
    "workbench.action.closeEditorsAndGroup",
    "workbench.action.focusAboveGroup",
    "workbench.action.focusBelowGroup",
    "workbench.action.focusLeftGroup",
    "workbench.action.focusRightGroup",
    "workbench.action.nextEditor",
    "workbench.action.previousEditor",
    "workbench.action.splitEditorDown",
    "workbench.action.splitEditorLeft",
    "workbench.action.splitEditorRight",
    "workbench.action.splitEditorUp",
    "workbench.action.terminal.focusNext",
    "workbench.action.terminal.focusNextPane",
    "workbench.action.terminal.focusPrevious",
    "workbench.action.terminal.focusPreviousPane",
    "workbench.action.terminal.kill",
    "workbench.action.terminal.killActiveTab",
    "workbench.action.terminal.killEditor",
    "workbench.action.terminal.split",
}


def load_keybindings():
    text = KEYBINDINGS_PATH.read_text()
    without_comments = re.sub(r"(?m)^\s*//.*$", "", text)
    return json.loads(without_comments)


def binding_exists(bindings, key, command, when):
    return {
        "key": key,
        "command": command,
        "when": when,
    } in bindings


class VscodeKeybindingsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bindings = load_keybindings()

    def assert_binding(self, key, command, when):
        self.assertTrue(
            binding_exists(self.bindings, key, command, when),
            f"missing binding: {key} -> {command} when {when}",
        )

    def test_preserves_word_part_and_line_editing_scheme(self):
        expected = {
            ("alt+left", "cursorWordPartLeft", EDITOR_TEXT_WHEN),
            ("alt+right", "cursorWordPartRight", EDITOR_TEXT_WHEN),
            ("alt+shift+left", "cursorWordPartLeftSelect", EDITOR_TEXT_WHEN),
            ("alt+shift+right", "cursorWordPartRightSelect", EDITOR_TEXT_WHEN),
            ("alt+backspace", "deleteWordPartLeft", EDITOR_EDIT_WHEN),
            ("alt+delete", "deleteWordPartRight", EDITOR_EDIT_WHEN),
            ("ctrl+left", "cursorHome", EDITOR_TEXT_WHEN),
            ("ctrl+right", "cursorEnd", EDITOR_TEXT_WHEN),
            ("ctrl+backspace", "deleteAllLeft", EDITOR_EDIT_WHEN),
            ("ctrl+delete", "deleteAllRight", EDITOR_EDIT_WHEN),
            ("cmd+shift+left", "cursorHomeSelect", "editorTextFocus && isMac"),
            ("cmd+shift+right", "cursorEndSelect", "editorTextFocus && isMac"),
        }
        for key, command, when in expected:
            with self.subTest(key=key, command=command):
                self.assert_binding(key, command, when)

        self.assertFalse(
            any(
                binding["key"] in {"ctrl+shift+left", "ctrl+shift+right"}
                and binding["command"] in {"cursorHomeSelect", "cursorEndSelect"}
                for binding in self.bindings
            )
        )

    def test_editor_groups_and_tabs_match_requested_scheme(self):
        directions = {
            "left": ("Left", "Left"),
            "right": ("Right", "Right"),
            "up": ("Above", "Up"),
            "down": ("Below", "Down"),
        }
        for direction, (focus_suffix, split_suffix) in directions.items():
            with self.subTest(direction=direction, action="focus"):
                self.assert_binding(
                    f"ctrl+alt+{direction}",
                    f"workbench.action.focus{focus_suffix}Group",
                    EDITOR_GROUP_WHEN,
                )
            with self.subTest(direction=direction, action="split"):
                self.assert_binding(
                    f"ctrl+alt+shift+{direction}",
                    f"workbench.action.splitEditor{split_suffix}",
                    EDITOR_GROUP_WHEN,
                )

        self.assert_binding(
            "ctrl+alt+w",
            "workbench.action.closeEditorsAndGroup",
            EDITOR_GROUP_WHEN,
        )
        self.assert_binding(
            "ctrl+shift+left",
            "workbench.action.previousEditor",
            EDITOR_GROUP_WHEN,
        )
        self.assert_binding(
            "ctrl+shift+right",
            "workbench.action.nextEditor",
            EDITOR_GROUP_WHEN,
        )
        self.assert_binding(
            "ctrl+shift+w",
            "workbench.action.closeActiveEditor",
            EDITOR_GROUP_WHEN,
        )

    def test_terminal_bindings_use_supported_nondirectional_actions(self):
        for direction in ("left", "up"):
            with self.subTest(direction=direction, action="previous pane"):
                self.assert_binding(
                    f"ctrl+alt+{direction}",
                    "workbench.action.terminal.focusPreviousPane",
                    TERMINAL_PANE_WHEN,
                )
        for direction in ("right", "down"):
            with self.subTest(direction=direction, action="next pane"):
                self.assert_binding(
                    f"ctrl+alt+{direction}",
                    "workbench.action.terminal.focusNextPane",
                    TERMINAL_PANE_WHEN,
                )

        for direction in ("left", "right", "up", "down"):
            with self.subTest(direction=direction, action="split"):
                self.assert_binding(
                    f"ctrl+alt+shift+{direction}",
                    "workbench.action.terminal.split",
                    TERMINAL_WHEN,
                )

        self.assert_binding(
            "ctrl+alt+w",
            "workbench.action.terminal.kill",
            TERMINAL_WHEN,
        )
        self.assert_binding(
            "ctrl+shift+left",
            "workbench.action.terminal.focusPrevious",
            TERMINAL_WHEN,
        )
        self.assert_binding(
            "ctrl+shift+right",
            "workbench.action.terminal.focusNext",
            TERMINAL_WHEN,
        )
        self.assert_binding(
            "ctrl+shift+w",
            "workbench.action.terminal.killEditor",
            TERMINAL_EDITOR_WHEN,
        )
        self.assert_binding(
            "ctrl+shift+w",
            "workbench.action.terminal.kill",
            TERMINAL_PANEL_WHEN,
        )
        self.assert_binding(
            "ctrl+shift+w",
            "workbench.action.terminal.killActiveTab",
            TERMINAL_TABS_WHEN,
        )

        self.assertFalse(
            any(
                "terminal" in binding["command"]
                and any(
                    token in binding["command"]
                    for token in ("navigate", "splitPaneLeft", "splitPaneRight", "splitPaneUp", "splitPaneDown")
                )
                for binding in self.bindings
            )
        )

    def test_terminal_focus_commands_survive_the_shell_skip_list(self):
        """A terminal-focus keybinding only fires if VS Code does not forward it
        to the shell. VS Code forwards every command that is missing from
        terminal.integrated.commandsToSkipShell's default value."""
        if not VSCODE_BUNDLE.is_file():
            self.skipTest("installed VS Code bundle not found")

        bundle = VSCODE_BUNDLE.read_text(errors="replace")
        start = bundle.index('["workbench.action.terminal.clearSelection"')
        end = bundle.index("]", start)
        skip_shell = set(re.findall(r'"([^"]+)"', bundle[start:end]))
        self.assertIn("workbench.action.terminal.kill", skip_shell)
        # Regression guard: this command is absent from the default list, so a
        # terminal-focus binding for it never fires and the key reaches the shell.
        self.assertNotIn("workbench.action.terminal.killViewOrEditor", skip_shell)

        for binding in self.bindings:
            terms = [term.strip() for term in binding["when"].split("&&")]
            # Positive terminal-content focus only; `!terminalFocus` bindings
            # run in the editor and the tabs list is not a shell.
            if "terminalFocus" not in terms or "terminalTabsFocus" in terms:
                continue
            with self.subTest(key=binding["key"], command=binding["command"], when=binding["when"]):
                self.assertIn(binding["command"], skip_shell)

    def test_all_commands_are_verified_and_no_window_close_is_bound(self):
        commands = {binding["command"] for binding in self.bindings}
        self.assertTrue(commands <= SUPPORTED_COMMANDS, commands - SUPPORTED_COMMANDS)
        self.assertNotIn("workbench.action.closeWindow", commands)
        self.assertNotIn("workbench.action.closeAllGroups", commands)
        self.assertNotIn("workbench.action.terminal.killAll", commands)


if __name__ == "__main__":
    unittest.main()
