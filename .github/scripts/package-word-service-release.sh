#!/usr/bin/env bash
set -Eeuo pipefail

: "${RUNNER_TEMP:?GitHub Actions must provide RUNNER_TEMP}"
: "${GITHUB_SHA:?GitHub Actions must provide GITHUB_SHA}"
: "${GITHUB_OUTPUT:?GitHub Actions must provide GITHUB_OUTPUT}"
: "${MAX_GLIBC_VERSION:=2.36}"
: "${RELEASE_BINARY:=wordService/target/release/n2-word-service-rust}"
: "${RELEASE_LABEL:=}"

package_dir="$RUNNER_TEMP/n2-vocabulary-package"
archive_stem="n2-vocabulary-${GITHUB_SHA}"
if [[ -n "$RELEASE_LABEL" ]]; then
  [[ "$RELEASE_LABEL" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || {
    echo 'RELEASE_LABEL must contain only letters, numbers, dots, underscores, and hyphens' >&2
    exit 1
  }
  archive_stem="n2-vocabulary-${RELEASE_LABEL}-${GITHUB_SHA}"
fi
archive="$RUNNER_TEMP/${archive_stem}.tar.gz"
checksum="${archive}.sha256"
binary="$RELEASE_BINARY"

if [[ ! -x "$binary" ]]; then
  echo "Release binary is missing or not executable: $binary" >&2
  exit 1
fi

# The archive is built on an Ubuntu runner, so inspect the binary before it is
# copied. This catches an accidental host build that would require a newer
# glibc than the Debian 12 production host can provide.
command -v readelf >/dev/null || {
  echo 'readelf is required to verify the release binary ABI' >&2
  exit 1
}
mapfile -t glibc_versions < <(
  readelf --version-info "$binary" |
    grep -oE 'GLIBC_[0-9]+\.[0-9]+' |
    sed 's/^GLIBC_//' |
    sort -Vu
)
if ((${#glibc_versions[@]} > 0)); then
  highest_glibc_version="$(printf '%s\n' "${glibc_versions[@]}" | sort -V | tail -n 1)"
  highest_allowed_version="$(printf '%s\n' "$highest_glibc_version" "$MAX_GLIBC_VERSION" | sort -V | tail -n 1)"
  if [[ "$highest_allowed_version" != "$MAX_GLIBC_VERSION" ]]; then
    echo "Release binary requires GLIBC_$highest_glibc_version; maximum allowed is GLIBC_$MAX_GLIBC_VERSION" >&2
    exit 1
  fi
  echo "Release binary GLIBC requirements: ${glibc_versions[*]} (maximum allowed: $MAX_GLIBC_VERSION)"
else
  echo 'Release binary has no dynamic GLIBC version requirements (likely statically linked).'
fi

rm -rf "$package_dir" "$archive" "$checksum"
mkdir -p "$package_dir/bootstrap" "$package_dir/wordService/data" "$package_dir/wordService/static" "$package_dir/reviews/vocabulary_audio"

install -Dm755 "$binary" "$package_dir/n2-word-service-rust"
install -Dm644 deploy/n2-word-service.service "$package_dir/bootstrap/n2-word-service.service"
install -Dm644 deploy/n2-word-service.env.example "$package_dir/bootstrap/n2-word-service.env.example"
cp -a wordService/static/. "$package_dir/wordService/static/"
install -Dm644 wordService/data/n2vocab.sqlite "$package_dir/wordService/data/n2vocab.sqlite"
cp -a clips "$package_dir/clips"
install -Dm644 reviews/vocabulary_audio/n2_all_both_candidates.json "$package_dir/reviews/vocabulary_audio/n2_all_both_candidates.json"
install -Dm644 reviews/vocabulary_audio/n2_all_both.json "$package_dir/reviews/vocabulary_audio/n2_all_both.json"
printf '%s\n' "$GITHUB_SHA" > "$package_dir/RELEASE"

tar --create --gzip --file "$archive" --directory "$package_dir" --sort=name \
  --mtime='UTC 1970-01-01' --owner=0 --group=0 --numeric-owner .
(
  cd "$(dirname "$archive")"
  sha256sum "$(basename "$archive")" > "$checksum"
)
cat "$checksum"

echo "archive=$archive" >> "$GITHUB_OUTPUT"
echo "checksum=$checksum" >> "$GITHUB_OUTPUT"
