#!/usr/bin/env bash

INPUT=$1
OUTPUT="$1-code-statistics.txt"

objdump -d $1 | sed -e 's/^ *[0-9a-f]*:[\t 0-9a-f]*[ \t]\([a-z][0-9a-z][0-9a-z][0-9a-z]*\)[ \t]\(.*\)$/\1/g' | grep '^[a-z0-9]*$' >> $OUTPUT
cat $OUTPUT | awk '/./ { arrs[$1] += 1 } END { for (val in arrs) { print arrs[val], val; sum += arrs[val] } print sum, "Total" }' | sort -n -r | head -n 50 | less
