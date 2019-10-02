#!/usr/bin/env bash

# depends-on: brew
# satisfies: pip, pipenv
install() {
  brew install python
  brew install python@2

  pip install --user pipenv
  pip install --user tox

  bash_section "Python"
  bash_export_path "$(python -m site --user-base)/bin"

  # Freaking brew python
  bash_export_path "$(brew --prefix python)/bin"
  bash_export_path "$(brew --prefix python@2)/bin"
}
