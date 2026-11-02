# Layer the dotfiles OMP model overlay over Gohan's managed ~/.omp/agent/config.yml.
#
# PI_CONFIG_FILES entries are strict: a missing file aborts omp startup, so only
# add the overlay when the installed file (or its symlink target) exists. A
# dangling link leaves the managed configuration in charge instead of breaking omp.
if [ -f "$HOME/.omp/agent/personal.yml" ]; then
  case ":${PI_CONFIG_FILES:-}:" in
    *":$HOME/.omp/agent/personal.yml:"*) ;;
    *) export PI_CONFIG_FILES="${PI_CONFIG_FILES:+$PI_CONFIG_FILES:}$HOME/.omp/agent/personal.yml" ;;
  esac
fi
