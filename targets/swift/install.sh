# depends-on: brew
install() {
  brew install swift
  ln -s -f $THIS/scripts/swift_demangle_filter.py ~/bin/swift-demangle-filter
}
