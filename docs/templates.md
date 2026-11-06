# Target Templates

## Main Repo (~/dotfiles)

Shared.sh is sourced relative to the target's own path:

```bash
#!/usr/bin/env bash

ROOT=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../.." \
  &> /dev/null && pwd )
source $ROOT/scripts/shared.sh

install() {
  local this=$(get_source)

  # --- Package installation (OS-specific) ---
  # if is_mac; then brew install <pkg>; fi
  # if is_ubuntu; then sudo apt install <pkg>; fi
  # if is_centos; then sudo yum install <pkg>; fi

  # --- Symlinks ---
  # ln -s -f $this/<config> $HOME/.<config>

  # --- Bash config ---
  bash_init_config
  bash_section "<Target> configuration"
  bash_export_source "$this/bashrc.aliases.sh"
}

if ! is_sourced; then
  install
fi
```

## Extension Repo (~/dotfiles-*)

Shared.sh is sourced from the sibling dotfiles repo:

```bash
#!/usr/bin/env bash

ROOT="$( cd "$( dirname "$BASH_SOURCE" )" && pwd )/../../.."
source $ROOT/dotfiles/scripts/shared.sh

install() {
  local this=$(get_source)

  # --- Symlinks ---
  # ln -s -f $this/<config> $HOME/.<config>

  # --- Bash config ---
  bash_init_config
  bash_section "<Target> configuration"
  bash_export_source "$this/bashrc.aliases.sh"
}

if ! is_sourced; then
  install
fi
```

The key difference: extension repos resolve ROOT three
levels up (`../../..`) then source
`$ROOT/dotfiles/scripts/shared.sh`. This assumes
`~/dotfiles` and `~/dotfiles-*` are siblings.

## Common Config Files

| File                  | Purpose                        |
|-----------------------|--------------------------------|
| `bashrc.aliases.sh`   | Shell aliases                  |
| `bashrc.config.sh`    | Environment variables          |
| `bashrc.functions.sh` | Shell functions                |
| `bashrc.theme.sh`     | Prompt/theme configuration     |

Not all targets need all files — create only what the
target requires.
