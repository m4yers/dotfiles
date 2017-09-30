#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import codecs
import sys
import re

from subprocess import Popen, PIPE


GLOBAL = re.compile('(@[_a-zA-Z0-9]+)')
LOCAL = re.compile('(%[_a-zA-Z0-9]+)')
SECTIONS = ["_IVARS_", "_DATA_", "_METACLASS_DATA_"]


def run_swift_demangle(name):
  command = ['xcrun', 'swift-demangle', '-compact', name]
  return Popen(command, stdout=PIPE).communicate()[0].splitlines()[0]


def demangle(symbol):
  result = run_swift_demangle(symbol)
  if result != symbol:
    return result

  for section in SECTIONS:
    if symbol.startswith(section):
      name = symbol.replace(section, "")
      result = run_swift_demangle(name)
      return "{},{}".format(section, result)

  name = "_" + symbol
  result = run_swift_demangle(name)
  if result != name:
    return result

  return symbol


def filter_input(opts):
  cache = dict()

  filein = codecs.open(opts.file, "r", "utf-8") if opts.file else sys.stdin
  fileout = codecs.open(opts.out, "w", "utf-8") if opts.out else sys.stdout

  for line in filein:
    symbols = set(GLOBAL.findall(line)) | set(LOCAL.findall(line))
    for symbol in symbols:
      if symbol not in cache:
        cache[symbol] = demangle(symbol[1:])
      demangled = cache.get(symbol)
      if demangled != symbol[1:]:
        demangled = demangled.replace('"', "\\34")
        replacement = '{}"{}"'.format(symbol[:1], demangled)
        line = line.replace(symbol, replacement)
    fileout.write(line)

  if filein != sys.stdin:
    filein.close()

  if fileout != sys.stdout:
    fileout.close()


def main():
  parser = argparse.ArgumentParser(
      prog="Swift Demangling Filter",
      description="Filters a file through swift-filter_input.")

  parser.add_argument("file", metavar="FILENAME", nargs="?",
                      help="File to filter. If omitted STDIN is used")

  parser.add_argument("-t", "--type", metavar="TYPE",
                      choices=["sil", "llvm", "asm"],
                      default="llvm",
                      help="Input type(sil, llvm or asm). Default: llvm")

  parser.add_argument("-o", "--out",
                      help="Output file. If omitted STDOUT will be used")

  opts = parser.parse_args(sys.argv[1:])
  filter_input(opts)

main()
