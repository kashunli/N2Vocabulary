#!/usr/bin/env bash
set -Eeuo pipefail

: "${RUNNER_TEMP:?GitHub Actions must provide RUNNER_TEMP}"
: "${GITHUB_SHA:?GitHub Actions must provide GITHUB_SHA}"
: "${GITHUB_OUTPUT:?GitHub Actions must provide GITHUB_OUTPUT}"

package_dir="$RUNNER_TEMP/n2-vocabulary-package"
archive="$RUNNER_TEMP/n2-vocabulary-${GITHUB_SHA}.tar.gz"
checksum="${archive}.sha256"

rm -rf "$package_dir" "$archive" "$checksum"
mkdir -p "$package_dir/wordService/data" "$package_dir/wordService/static" "$package_dir/reviews/vocabulary_audio"

install -Dm755 wordService/target/release/n2-word-service-rust "$package_dir/n2-word-service-rust"
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
