#!/usr/bin/env bash

ROOT=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../.." \
  &> /dev/null && pwd )
source $ROOT/scripts/shared.sh

# Pinned release; bump deliberately. Releases:
# https://github.com/dandavison/delta/releases
DELTA_VERSION="0.20.1"

install_mac() {
  brew install git-delta
}

install_ubuntu() {
  local arch
  if is_arm; then arch="arm64"; else arch="amd64"; fi
  local deb="git-delta_${DELTA_VERSION}_${arch}.deb"
  local url="https://github.com/dandavison/delta/releases/download"
  url="$url/$DELTA_VERSION/$deb"
  local tmp=$(mktemp -d)
  curl -fsSL -o "$tmp/$deb" "$url"
  sudo dpkg -i "$tmp/$deb"
  rm -rf "$tmp"
}

# No yum package on Amazon Linux / CentOS; install the prebuilt binary
# into ~/.local/bin (on PATH via the bash target). x86 gets the static
# musl build; there is no musl build for arm64, so it gets the gnu one.
install_centos() {
  local triple
  if is_arm; then
    triple="aarch64-unknown-linux-gnu"
  else
    triple="x86_64-unknown-linux-musl"
  fi
  local name="delta-${DELTA_VERSION}-${triple}"
  local url="https://github.com/dandavison/delta/releases/download"
  url="$url/$DELTA_VERSION/$name.tar.gz"
  local tmp=$(mktemp -d)
  curl -fsSL -o "$tmp/delta.tgz" "$url"
  tar -xzf "$tmp/delta.tgz" -C "$tmp"
  mkdir -p "$HOME/.local/bin"
  # Not /usr/bin/install: that name is shadowed by the install() function
  # every target defines. Rename into place so a running delta (pager)
  # does not block the update with "Text file busy".
  chmod 755 "$tmp/$name/delta"
  mv -f "$tmp/$name/delta" "$HOME/.local/bin/delta"
  rm -rf "$tmp"
}

# Idempotent: add $1 to include.path only if not already present. The
# path is stored relative to ~ so the tracked gitconfig stays portable
# across machines (git expands ~ in include.path).
git_include() {
  local path="~${1#$HOME}"
  if ! git config --global --get-all include.path | grep -qxF "$path"; then
    git config --global --add include.path "$path"
  fi
}

install() {
  local this=$(get_source)

  if is_mac; then
    install_mac
  fi

  if is_ubuntu; then
    install_ubuntu
  fi

  if is_centos; then
    install_centos
  fi

  # Keep the delta config in this target and pull it into ~/.gitconfig
  # via include.path, so it works whether the git target symlinked
  # .gitconfig or configured an existing one in place.
  log "Including gitconfig from dotfiles"
  git_include "$this/gitconfig"

  bash_init_config
  bash_section "delta configuration"
  bash_export_source "$this/bashrc.aliases.sh"
}

if ! is_sourced; then
  install
fi
