import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class WorkstationSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / 'home'
        self.home.mkdir()
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        shutil.copy2(REPO / 'sync.sh', self.repo / 'sync.sh')
        fixtures = {
            'common/starship/starship.toml': 'add_newline = false\n',
            'common/omp/keybindings.yml': 'app.model.selectTemporary: [Alt+P, Alt+O]\ntui.editor.cursorWordLeft: [alt+left]\n',
            'common/vscode/keybindings.json': '[{"key":"ctrl+shift+right","command":"next"}]\n',
            'unix/cmux/cmux.json': '{"schemaVersion":1}\n',
            'unix/ghostty/keybindings.conf': 'keybind = alt+left=esc:b\n',
            'unix/tmux/tmux.conf': 'bind-key -n C-M-Left select-pane -L\n',
            'unix/zsh/keybindings.zsh': 'bindkey -e\n',
            'common/bash/.bashrc': 'REPLACED_BASHRC\n',
            'common/bash/.bash_profile': 'REPLACED_PROFILE\n',
            'common/readline/.inputrc': 'REPLACED_READLINE\n',
            'common/gh/config.yml': 'REPLACED_GH\n',
            'common/vscode/settings.json': 'REPLACED_SETTINGS\n',
            'common/vscode/mcp.json': 'REPLACED_MCP\n',
            'windows/windows-terminal/settings.json': '{"actions":[]}\n',
        }
        for name, text in fixtures.items():
            file = self.repo / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(text)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        uname = self.bin / 'uname'
        uname.write_text('#!/bin/sh\nprintf "%s\\n" "${TEST_PLATFORM:-Darwin}"\n')
        uname.chmod(0o755)
        self.env = {**os.environ, 'HOME': str(self.home), 'PATH': f'{self.bin}:/usr/bin:/bin', 'TEST_PLATFORM': 'Darwin'}
        for key in ('XDG_CONFIG_HOME', 'APPDATA', 'LOCALAPPDATA', 'OMP_AGENT_DIR', 'PI_CODING_AGENT_DIR', 'PI_CONFIG_DIR', 'DOTFILES_COPY_ONLY'):
            self.env.pop(key, None)

    def run_sync(self, command='apply', profile='workstation', check=True):
        result = subprocess.run(['/bin/bash', str(self.repo / 'sync.sh'), command, profile], env=self.env, text=True, capture_output=True)
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_mac_links_canonical_configs_without_replacing_unrelated_settings(self):
        untouched = {
            '.bashrc': 'work bashrc\n', '.bash_profile': 'work profile\n', '.inputrc': 'existing readline\n',
            '.config/gh/config.yml': 'work gh\n',
            'Library/Application Support/Code/User/settings.json': '{"work":true}\n',
            'Library/Application Support/Code/User/mcp.json': '{"private":true}\n',
        }
        for name, text in untouched.items():
            path = self.home / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        self.run_sync()
        expected = {
            '.config/starship.toml': 'common/starship/starship.toml',
            '.omp/agent/keybindings.yml': 'common/omp/keybindings.yml',
            '.tmux.conf': 'unix/tmux/tmux.conf',
            '.zshrc.d/95-keybindings.zsh': 'unix/zsh/keybindings.zsh',
            '.config/cmux/cmux.json': 'unix/cmux/cmux.json',
            '.config/ghostty/keybindings.conf': 'unix/ghostty/keybindings.conf',
            'Library/Application Support/Code/User/keybindings.json': 'common/vscode/keybindings.json',
        }
        for target, source in expected.items():
            self.assertEqual((self.home / target).resolve(), self.repo / source)
        for name, text in untouched.items():
            self.assertEqual((self.home / name).read_text(), text, name)

    def test_linux_only_deploys_shell_agent_prompt_and_tmux(self):
        self.env['TEST_PLATFORM'] = 'Linux'
        self.run_sync()
        for target in ('.config/starship.toml', '.omp/agent/keybindings.yml', '.tmux.conf', '.zshrc.d/95-keybindings.zsh'):
            self.assertTrue((self.home / target).is_symlink(), target)
        for target in ('.config/cmux', '.config/ghostty', '.config/Code', '.bash_profile', '.inputrc'):
            self.assertFalse((self.home / target).exists(), target)

    def test_ghostty_preserves_appearance_and_moves_keys_to_one_include(self):
        original = self.root / 'legacy-ghostty'
        original.write_text('font-family = My Font\nfont-size = 14\nbackground-opacity = 0.9\nkeybind = super+left=old\n')
        target = self.home / '.config/ghostty/config'
        target.parent.mkdir(parents=True)
        target.symlink_to(original)
        self.run_sync()
        self.assertFalse(target.is_symlink())
        text = target.read_text()
        self.assertIn('font-family = My Font', text)
        self.assertIn('background-opacity = 0.9', text)
        self.assertNotIn('keybind = ', text)
        self.assertEqual(text.count('config-file = keybindings.conf'), 1)
        self.assertIn('keybind = super+left=old', original.read_text())
        backups = list((self.home / '.dotfiles-backup').glob('*/.config/ghostty/config'))
        self.assertEqual(len(backups), 1)
        self.assertFalse(backups[0].is_symlink())
        self.assertEqual(backups[0].read_text(), original.read_text())

    def test_second_apply_is_idempotent_and_does_not_make_more_backups(self):
        target = self.home / '.config/starship.toml'
        target.parent.mkdir(parents=True)
        target.write_text('old prompt\n')
        self.run_sync()
        backups_before = sorted(p.relative_to(self.home) for p in (self.home / '.dotfiles-backup').rglob('*') if p.is_file())
        config_before = (self.home / '.config/ghostty/config').read_text()
        self.run_sync()
        backups_after = sorted(p.relative_to(self.home) for p in (self.home / '.dotfiles-backup').rglob('*') if p.is_file())
        self.assertEqual(backups_after, backups_before)
        self.assertEqual((self.home / '.config/ghostty/config').read_text(), config_before)

    def test_missing_canonical_file_fails_before_any_installation(self):
        (self.repo / 'unix/tmux/tmux.conf').unlink()
        result = self.run_sync(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.home / '.config/starship.toml').exists())

    def test_destination_directory_fails_before_any_installation(self):
        (self.home / '.tmux.conf').mkdir()
        result = self.run_sync(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.home / '.config/starship.toml').exists())

    def test_ghostty_wrapper_directory_fails_before_any_installation(self):
        (self.home / '.config/ghostty/config').mkdir(parents=True)
        result = self.run_sync(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.home / '.config/starship.toml').exists())

    def test_copy_mode_is_supported_and_backups_survive_legacy_source_removal(self):
        self.env['DOTFILES_COPY_ONLY'] = '1'
        legacy = self.root / 'legacy-starship.toml'
        legacy.write_text('old prompt from removed legacy source\n')
        target = self.home / '.config/starship.toml'
        target.parent.mkdir(parents=True)
        target.symlink_to(legacy)
        self.run_sync()
        self.assertFalse(target.is_symlink())
        legacy.unlink()
        backups = list((self.home / '.dotfiles-backup').glob('*/.config/starship.toml'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), 'old prompt from removed legacy source\n')

    def test_windows_workstation_preserves_profiles_and_uses_windows_terminal(self):
        self.env['TEST_PLATFORM'] = 'MINGW64_NT-10.0'
        self.env['DOTFILES_COPY_ONLY'] = '1'
        self.run_sync()
        self.assertFalse((self.home / '.bash_profile').exists())
        self.assertFalse((self.home / '.tmux.conf').exists())
        terminal = self.home / 'AppData/Local/Packages/Microsoft.WindowsTerminal_8wekyb3d8bbwe/LocalState/settings.json'
        self.assertEqual(terminal.read_text(), '{"actions":[]}\n')
        self.assertTrue((self.home / 'AppData/Roaming/Code/User/keybindings.json').exists())

    def test_unknown_profile_is_rejected_without_writes(self):
        result = self.run_sync(profile='invalid', check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_collect_workstation_works_with_system_bash_and_does_not_collect_settings(self):
        self.run_sync()
        target = self.home / '.omp/agent/keybindings.yml'
        target.unlink()
        target.write_text('local edited keys\n')
        result = self.run_sync(command='collect')
        self.assertEqual((self.repo / 'common/omp/keybindings.yml').read_text(), 'local edited keys\n')
        self.assertNotIn('extensions.txt', result.stdout)


if __name__ == '__main__':
    unittest.main()
