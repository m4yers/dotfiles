#!/usr/bin/env bash

# depends-on: brew
# satisfies: pip, pipenv
install() {
  brew install python
  brew install python2

  pip install --user pipenv
  pip install --user tox

  bash_section "Python"
  bash_export_path "$(python -m site --user-base)/bin"

  # Freaking brew python
  bash_export_path "/usr/local/opt/python3/bin"

  bash_export_path "$(brew --prefix python)/bin"
  bash_export_path "$(brew --prefix python2)/bin"
}
