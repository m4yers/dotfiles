#!/usr/bin/env python3
"""Scaffold a new dotfile target directory."""
import argparse
import os
import stat
import sys

HOME = os.path.expanduser("~")
MAIN = os.path.join(HOME, "dotfiles")

MAIN_TEMPLATE = '''#!/usr/bin/env bash

ROOT=$( cd -- "$( dirname -- "${{BASH_SOURCE[0]}}" )/../.." \\
  &> /dev/null && pwd )
source $ROOT/scripts/shared.sh

install() {{
  local this=$(get_source)

  bash_init_config
  bash_section "{name} configuration"
  bash_export_source "$this/bashrc.aliases.sh"
}}

if ! is_sourced; then
  install
fi
'''

EXT_TEMPLATE = '''#!/usr/bin/env bash

ROOT="$( cd "$( dirname "$BASH_SOURCE" )" && pwd )/../../.."
source $ROOT/dotfiles/scripts/shared.sh

install() {{
  local this=$(get_source)

  bash_init_config
  bash_section "{name} configuration"
  bash_export_source "$this/bashrc.aliases.sh"
}}

if ! is_sourced; then
  install
fi
'''

ALIASES_TEMPLATE = '''#!/usr/bin/env bash

# {name} aliases
'''


def resolve_repo(repo_name):
    if repo_name == "main":
        return MAIN
    # Try dotfiles-<name>
    path = os.path.join(HOME, "dotfiles-" + repo_name)
    if os.path.isdir(path):
        return path
    # Try as-is
    if os.path.isdir(repo_name):
        return repo_name
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Scaffold a new dotfile target"
    )
    parser.add_argument("name", help="Target name")
    parser.add_argument("repo", help="Repo: 'main' or extension name")
    args = parser.parse_args()

    repo = resolve_repo(args.repo)
    if not repo:
        print(
            "Repo '{}' not found".format(args.repo), file=sys.stderr
        )
        sys.exit(1)

    target_dir = os.path.join(repo, "targets", args.name)
    if os.path.exists(target_dir):
        print(
            "Target '{}' already exists at {}".format(
                args.name, target_dir
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    os.makedirs(target_dir)

    # Choose template
    is_main = os.path.samefile(repo, MAIN)
    template = MAIN_TEMPLATE if is_main else EXT_TEMPLATE

    # Write install.sh
    install_path = os.path.join(target_dir, "install.sh")
    with open(install_path, "w") as f:
        f.write(template.format(name=args.name))
    os.chmod(install_path, os.stat(install_path).st_mode | stat.S_IEXEC)

    # Write bashrc.aliases.sh
    aliases_path = os.path.join(target_dir, "bashrc.aliases.sh")
    with open(aliases_path, "w") as f:
        f.write(ALIASES_TEMPLATE.format(name=args.name))

    short = "~/{}".format(os.path.basename(repo))
    print("Created {}/targets/{}".format(short, args.name))
    print("Files:")
    print("  install.sh")
    print("  bashrc.aliases.sh")
    print(
        "\nRemember to register in {}/install.sh".format(short)
    )


if __name__ == "__main__":
    main()
