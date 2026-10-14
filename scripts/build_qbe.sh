#!/bin/sh
# Rebuild the exact backend baseline into a caller-owned, disposable directory.
set -eu
if [ "$#" -ne 1 ]; then
	printf 'Usage: %s destination-directory\n' "$0" >&2
	exit 1
fi
mkdir -p "$1"
cd "$1"
curl -fsSL https://c9x.me/compile/release/qbe-1.2.tar.xz -o qbe-1.2.tar.xz
printf '%s  %s\n' \
	a6d50eb952525a234bf76ba151861f73b7a382ac952d985f2b9af1df5368225d \
	qbe-1.2.tar.xz | sha256sum -c -
tar -xf qbe-1.2.tar.xz
make -C qbe-1.2 -j2
