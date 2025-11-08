#!/usr/bin/env bash

print_path() {
  while read -r -d':' line; do
    echo $line
  done <<< $PATH
}

print_colors() {
  # This file echoes a bunch of color codes to the terminal to demonstrate what's
  # available.  Each line is the color code of one forground color, out of 17
  # (default + 16 escapes), followed by a test use of that color on all nine
  # background colors (default + 8 escapes).
  #
  # Source: http://www.tldp.org/HOWTO/Bash-Prompt-HOWTO/x329.html

  T='gYw'   # The test text

  echo -e "\n               \
    40m     41m     42m     43m     44m     45m     46m     47m";

  for FGs in '    m' '   1m' '  30m' '1;30m' '  31m' '1;31m' '  32m' \
    '1;32m' '  33m' '1;33m' '  34m' '1;34m' '  35m' '1;35m' \
    '  36m' '1;36m' '  37m' '1;37m';
    do FG=${FGs// /}
      echo -en " $FGs \033[$FG  $T  "
        for BG in 40m 41m 42m 43m 44m 45m 46m 47m;
        do echo -en "$EINS \033[$FG\033[$BG  $T  \033[0m";
      done
      echo;
  done
  echo
}

# Collect statistics on used machine instructions
binary-asm-stats() {
  INPUT=$1
  OUTPUT="$1-code-statistics.txt"

  objdump -d $1 | sed -e 's/^ *[0-9a-f]*:[\t 0-9a-f]*[ \t]\([a-z][0-9a-z][0-9a-z][0-9a-z]*\)[ \t]\(.*\)$/\1/g' | grep '^[a-z0-9]*$' >> $OUTPUT
  cat $OUTPUT | awk '/./ { arrs[$1] += 1 } END { for (val in arrs) { print arrs[val], val; sum += arrs[val] } print sum, "Total" }' | sort -n -r | head -n 50 | less
}

# Report
binary-bitcode-stats() {
  local binary=$1
  local archs=$(lipo -info $binary)
  archs=${archs##*:}

  for arch in $archs; do
    echo "$arch:"
    echo " - objects: $(otool -hv -arch $arch $binary | grep MH_MAGIC | wc -l)"
    echo " - bitcode: $(otool -lv -arch $arch $binary | grep bitcode  | wc -l)"
    echo " - bundles: $(otool -lv -arch $arch $binary | grep bundle   | wc -l)"
    echo
  done
}

binary-bitcode-sect() {
  local binary=$1
  local archs=$(lipo -info $binary)
  archs=${archs##*:}

  for arch in $archs; do
    echo "$arch:"
    otool -lv -arch $arch $binary | pcregrep -M "sectname (__bundle|__bitcode)(.|\n)*?segname __LLVM(.|\n)*?attributes"
  done
}

ipa-unpack() {
  local ipa=$(realpath $1)
  if [[ -z "$ipa" ]]; then echo "Which ipa?"; exit 1; fi

  local file="${ipa##*/}"
  local name="${file%%.*}"
  local unpacked="$ipa.unpacked"

  rm -rf "$unpacked" &> /dev/null
  unzip -d "$unpacked" "$ipa" > /dev/null
  pushd "$unpacked/Payload/$name.app" > /dev/null
  echo "$name"
  ebcutil --extract "$name"
  for f in *; do llvm-dis $f; done
}

pkg-unpack() {
local pkg=$(realpath $1)
  if [[ -z $pkg ]]; then echo "Which pkg?"; exit 1; fi

  local file=${pkg##*/}
  local name=${file%%.*}
  local unpacked=$pkg.unpacked

  rm -rf $unpacked &> /dev/null

  pushd $unpacked > /dev/null
  xar -xf ../$pkg
  cd $pkg.pkg
  cat Payload | gunzip -dc |cpio -i
  popd
}

notify() {
 say -v Moira "$@ is complete"
}

copy-directory() {
  local src="$1"
  local dest="$2"

  # Only the last component of the source path
  local basename=$(basename "$src")

  echo "Copying $src → $dest"

  # Ensure destination exists
  mkdir -p "$dest"

  # Archive only the last component and extract into destination
  tar -C "$(dirname "$src")" -cf - "$basename" | pv | tar xf - -C "$dest"

  echo "Done."
}

net-show-ports() {
  sudo netstat -lntup
}

net-show-arp() {
  arp -a | awk 'NR==1 {print; next} {print | "sort"}'
}
