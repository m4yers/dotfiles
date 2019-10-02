#!/usr/bin/env bash

export TERM="xterm-color"
export CLICOLOR=1

# Less Colors for Man Pages
export LESS_TERMCAP_mb=$'\e[01;31m'       # begin blinking
export LESS_TERMCAP_md=$'\e[01;33;5;74m'  # begin bold
export LESS_TERMCAP_me=$'\e[0m'           # end mode
export LESS_TERMCAP_se=$'\e[0m'           # end standout-mode
export LESS_TERMCAP_so=$'\e[30;5;46m'     # begin standout-mode - info box
export LESS_TERMCAP_ue=$'\e[0m'           # end underline
export LESS_TERMCAP_us=$'\e[04;34;5;146m' # begin underline]]]

PS1='\[\033[01;31m\]\h\[\033[00m\]|\[\033[01;33m\]\W⤷ \[\033[00m\]\[\033[01;37m\]'
trap 'tput sgr0' DEBUG
