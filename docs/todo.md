# TODO

Open work items for this repo. Keep entries short, one per line, with the
file they concern. Remove the line when the work lands.

## Installer

- [ ] Differentiate home and work installs properly: add `is_home` /
  `is_work` to `scripts/shared.sh` so target installers know which
  profile they run under, instead of inferring it from OS or hostname.
- [ ] `install.sh` `bash_init`: back up the existing `~/.bashrc` before
  overwriting it, and replace the `cat > $BASHRC` hack.
- [ ] `targets/tmux/install.sh` `install_centos`: build tmux from source
  instead of no-op.
- [ ] `targets/vim/install.sh`: drop UltiSnips in favour of loading snippet
  files directly.

## Vim

- [ ] `targets/vim/vimrc`: move `ctrlp_custom_ignore` (work-specific dirs)
  to the hidden config repo.
- [ ] `targets/vim/vimrc`: make `NERDTreeWinSize` depend on window size.
- [ ] `targets/vim/vimrc` `pl_FSwitch`: remove the project-specific `make`
  subfolder handling.
- [ ] `targets/vim/vimrc`: `FocusLost` autosave does not fire in iTerm.

## Scripts

- [ ] `targets/scripts/export/gpgdisk`: unmount all subdirectories on close.
