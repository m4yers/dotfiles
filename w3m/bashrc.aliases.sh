#!/usr/bin/env bash

alias www=w3m
alias urlencode='python -c "import sys, urllib as ul; print ul.quote_plus(sys.argv[1]);"'

duck() {
  w3m https://duckduckgo.com?q=$(urlencode "$*")
}
