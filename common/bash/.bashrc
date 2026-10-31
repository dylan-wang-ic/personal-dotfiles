export PATH="$HOME/.local/bin:$PATH"

if [[ $- == *i* ]]; then
  shopt -s histappend
  eval "$(starship init bash)"
fi
