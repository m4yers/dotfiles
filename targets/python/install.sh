#!/usr/bin/env bash

# depends-on: bash, brew
install() {
  brew install python

  pip install --user pipenv
  pip install --user tox

  bash_init_config
  bash_export_path "$(python -m site --user-base)/bin"
}
