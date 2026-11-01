# Start from the standard Emacs ZLE map, then add the shared personal bindings.
bindkey -e

# Alt moves/deletes by word; Ctrl moves/deletes by line.
bindkey '\e[1;3D' backward-word
bindkey '\e[1;3C' forward-word
bindkey '\e[1;5D' beginning-of-line
bindkey '\e[1;5C' end-of-line
bindkey '\e\x7f' backward-kill-word
bindkey '\e[3;3~' kill-word
bindkey '\e[127;5u' backward-kill-line
bindkey '\e[3;5~' kill-line

# Extend an active ZLE selection, or start one at the current cursor.
function _terminal_begin_selection() {
  if (( ! REGION_ACTIVE )); then
    MARK=$CURSOR
    REGION_ACTIVE=1
  fi
}

function _terminal_select_word_left() {
  _terminal_begin_selection
  zle backward-word
}

function _terminal_select_word_right() {
  _terminal_begin_selection
  zle forward-word
}

function _terminal_select_line_start() {
  _terminal_begin_selection
  zle beginning-of-line
}

function _terminal_select_line_end() {
  _terminal_begin_selection
  zle end-of-line
}

zle -N terminal-select-word-left _terminal_select_word_left
zle -N terminal-select-word-right _terminal_select_word_right
zle -N terminal-select-line-start _terminal_select_line_start
zle -N terminal-select-line-end _terminal_select_line_end

# Use Option+Shift for word selection and Command+Shift for line selection.
# Ctrl+Shift+Left/Right are deliberately left free for previous/next tab.
bindkey '\e[1;4D' terminal-select-word-left
bindkey '\e[1;4C' terminal-select-word-right
bindkey '\e[1;2H' terminal-select-line-start
bindkey '\e[1;2F' terminal-select-line-end
