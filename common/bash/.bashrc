export PATH="$HOME/.local/bin:$PATH"

if [[ $- == *i* ]]; then
  shopt -s histappend
  eval "$(starship init bash)"

  # Ctrl+Z undoes an edit at the prompt. A running program still suspends.
  _prompt_ctrl_z_undo() {
    [[ -t 0 ]] || return 0
    stty susp undef 2>/dev/null || true
  }
  _command_ctrl_z_suspend() {
    [[ -t 0 ]] || return 0
    stty susp '^Z' 2>/dev/null || true
  }
  PROMPT_COMMAND="${PROMPT_COMMAND:+$PROMPT_COMMAND;}_prompt_ctrl_z_undo"
  trap '_command_ctrl_z_suspend' DEBUG
fi
