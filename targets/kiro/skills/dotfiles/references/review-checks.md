# Review Checks

Checks performed by the `review` command. Single-target
checks apply to one target; global checks apply when
reviewing `all`.

## Single Target Checks

### Structure

- install.sh exists and is executable
- install.sh sources shared.sh using the correct relative
  path: main repos use `../../scripts/shared.sh`, extension
  repos use `../../../dotfiles/scripts/shared.sh`
- install.sh has the `if ! is_sourced; then install; fi`
  guard at the bottom
- install.sh uses `get_source` (via `local this=$(get_source)`)
  for self-reference instead of hardcoded paths

### OS Consistency

- If any OS-specific branch exists (is_mac, is_ubuntu,
  is_centos), check that all expected branches are present
  or explicitly skipped
- Package install commands match the OS branch they're in
  (brew for mac, apt for ubuntu, yum for centos)

### Bash Config

- If `bash_init_config` is called, verify that at least one
  `bash_export_source` follows
- All files passed to `bash_export_source` exist in the
  target directory
- No duplicate `bash_export_source` calls for the same file

### Symlinks

- Symlinks use `ln -s -f` (force flag to overwrite)
- Source paths use `$this` variable, not hardcoded paths
- Destination paths use `$HOME` or `~`, not hardcoded
  `/home/<user>`

### Registration

- Target appears in at least one profile/OS array in the
  repo's `install.sh`

## Global Checks (review all)

### Alias Conflicts

- No two targets define the same alias name across all
  `bashrc.aliases.sh` files in all repos

### Symlink Conflicts

- No two targets symlink to the same destination path

### Export Conflicts

- No two targets export the same environment variable via
  `bash_export_global`

### Profile Coverage

- Every target directory is registered in its repo's
  `install.sh` (no orphan targets)

### Shadow Detection

- Extension repo targets don't unintentionally shadow main
  repo targets (same config file destinations, same alias
  names)

## Improvement Suggestions

After checks, suggest:
- Missing OS branches that peer targets have
- Aliases commonly found in similar tools
- Large install.sh files that could split config into
  separate bashrc.*.sh files
- Patterns repeated across targets that could be extracted
  into shared.sh helpers
