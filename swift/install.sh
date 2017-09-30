#brew: swift
install() {
  local HERE=$ROOT/swift
  ln -s -f $HERE/scripts/swift_demangle_filter.py ~/bin/swift-demangle-filter
}
