#!/usr/bin/env bash

# depends-on: brew
# satisfies: pip, pipenv
install() {
  brew install python

  pip install --user pipenv
  pip install --user tox

  bash_section "Python"
  bash_export_path "$(python -m site --user-base)/bin"
}
