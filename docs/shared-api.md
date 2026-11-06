# Shared API

Helpers from `~/dotfiles/scripts/shared.sh` available to
all target install scripts.

## OS Detection

| Function      | Returns true when          |
|---------------|----------------------------|
| `is_mac`      | macOS (Darwin)             |
| `is_linux`    | Any Linux                  |
| `is_ubuntu`   | Ubuntu (ID=ubuntu)         |
| `is_centos`   | Amazon Linux or CentOS     |

## Architecture Detection

| Function  | Returns true when          |
|-----------|----------------------------|
| `is_x86`  | `uname -m` x86_64 or amd64 |
| `is_arm`  | `uname -m` aarch64 or arm64|

## Path Resolution

| Function            | Returns                          |
|---------------------|----------------------------------|
| `get_target_folder` | Parent of the target directory   |
| `get_target_name`   | Basename of the target directory |
| `get_target_config` | `~/.config/dotfiles/<target>`    |
| `get_source`        | Full path to the target directory|

## Bash Config Management

These write to `~/.config/dotfiles/<target>` which gets
sourced from `~/.bashrc`.

| Function                  | Effect                        |
|---------------------------|-------------------------------|
| `bash_init_config`        | Create/reset target config    |
| `bash_newline [text]`     | Append line to config         |
| `bash_section "title"`    | Append commented section      |
| `bash_export_path "dir"`  | Append `export PATH=dir:$PATH`|
| `bash_export_source "f"`  | Append `source f`             |
| `bash_export_source_maybe`| Source if file exists          |
| `bash_export_global K V`  | Append `export K=V`           |

## Logging

| Function          | Effect                          |
|-------------------|---------------------------------|
| `log "msg"`       | Purple prefixed message         |
| `error "msg" [c]` | Red prefixed message, return c  |
| `message "m" [c]` | Colored prefixed message        |

## Utilities

| Function          | Effect                          |
|-------------------|---------------------------------|
| `yesno "q" "def"` | Interactive yes/no prompt       |
| `is_sourced`      | True if script is being sourced |
| `assert_prev`     | Check previous command status   |
| `tolower "str"`   | Lowercase a string              |

## Kiro Linking

Idempotent helpers for composing `~/.kiro/` from several
repos. Each repo owns only the symlinks pointing into its
own source tree.

| Function                                 | Effect                               |
|------------------------------------------|--------------------------------------|
| `kiro_link_namespace dest ns src`        | `dest/ns -> src` (whole directory)   |
| `kiro_link_files_flat dest src`          | Per-file symlinks for `src/*`        |
| `kiro_prune_owned_symlinks dest prefix`  | Remove symlinks pointing into prefix |
| `kiro_ensure_real_dir dir`               | Replace legacy symlink with real dir |

Skills and steering use namespaces; agents, settings, and
prompts must be flat.

## Constants

```bash
TARGET_CONFIGS="$HOME/.config/dotfiles"
BASHRC="$HOME/.bashrc"
BASHPROFILE="$HOME/.bash_profile"
```
