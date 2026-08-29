#!/usr/bin/env bash
set -Eeuo pipefail

: "${ARCHIVE:?Package step must provide ARCHIVE}"
: "${CHECKSUM:?Package step must provide CHECKSUM}"
: "${GITHUB_SHA:?GitHub Actions must provide GITHUB_SHA}"
: "${RUNNER_TEMP:?GitHub Actions must provide RUNNER_TEMP}"

key_file="$RUNNER_TEMP/n2-vocabulary-deploy-key"
known_hosts_file="$RUNNER_TEMP/n2-vocabulary-known-hosts"
remote_archive="/tmp/n2-vocabulary-${GITHUB_SHA}.tar.gz"
remote_checksum="${remote_archive}.sha256"
target="$DEPLOY_USER@$DEPLOY_HOST"

umask 077
printf '%s\n' "$DEPLOY_SSH_PRIVATE_KEY" > "$key_file"
printf '%s\n' "$DEPLOY_KNOWN_HOSTS" > "$known_hosts_file"
ssh_opts=(-i "$key_file" -p "$DEPLOY_PORT" -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$known_hosts_file")
scp_opts=(-i "$key_file" -P "$DEPLOY_PORT" -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$known_hosts_file")

ssh "${ssh_opts[@]}" "$target" "install -d -m 0755 '$DEPLOY_ROOT/incoming' '$DEPLOY_ROOT/releases'"
scp "${scp_opts[@]}" "$ARCHIVE" "$target:$remote_archive"
scp "${scp_opts[@]}" "$CHECKSUM" "$target:$remote_checksum"

quoted_root=$(printf '%q' "$DEPLOY_ROOT")
quoted_sha=$(printf '%q' "$GITHUB_SHA")
quoted_archive=$(printf '%q' "$remote_archive")
quoted_checksum=$(printf '%q' "$remote_checksum")
quoted_service=$(printf '%q' "$DEPLOY_SERVICE")
quoted_healthcheck=$(printf '%q' "$DEPLOY_HEALTHCHECK_URL")

ssh "${ssh_opts[@]}" "$target" \
  "DEPLOY_ROOT=$quoted_root RELEASE_SHA=$quoted_sha REMOTE_ARCHIVE=$quoted_archive REMOTE_CHECKSUM=$quoted_checksum SERVICE=$quoted_service HEALTHCHECK_URL=$quoted_healthcheck bash -s" <<'REMOTE_SCRIPT'
set -Eeuo pipefail

release_dir="$DEPLOY_ROOT/releases/$RELEASE_SHA"
temporary_dir="$DEPLOY_ROOT/releases/.${RELEASE_SHA}.tmp"
previous_target=''
if [[ -L "$DEPLOY_ROOT/current" ]]; then
  previous_target=$(readlink "$DEPLOY_ROOT/current")
fi

if [[ -e "$release_dir" ]]; then
  echo "Release $RELEASE_SHA already exists; validating it instead of extracting again."
else
  rm -rf "$temporary_dir"
  install -d -m 0755 "$temporary_dir"
  (
    cd "$(dirname "$REMOTE_ARCHIVE")"
    sha256sum --check "$(basename "$REMOTE_CHECKSUM")"
  )
  tar --extract --gzip --file "$REMOTE_ARCHIVE" --directory "$temporary_dir"
  test -x "$temporary_dir/n2-word-service-rust"
  test -f "$temporary_dir/wordService/data/n2vocab.sqlite"
  test -f "$temporary_dir/wordService/static/react-rail/index.html"
  mv "$temporary_dir" "$release_dir"
fi

ln -sfn "$release_dir" "$DEPLOY_ROOT/current.next"
mv -Tf "$DEPLOY_ROOT/current.next" "$DEPLOY_ROOT/current"

healthy() {
  sudo systemctl is-active --quiet "$SERVICE" && \
    curl --fail --silent --show-error --retry 20 --retry-delay 1 "$HEALTHCHECK_URL" >/dev/null
}

if ! sudo systemctl restart "$SERVICE" || ! healthy; then
  echo 'New release failed its service or health check; attempting rollback.' >&2
  if [[ -n "$previous_target" ]]; then
    ln -sfn "$previous_target" "$DEPLOY_ROOT/current.next"
    mv -Tf "$DEPLOY_ROOT/current.next" "$DEPLOY_ROOT/current"
    sudo systemctl restart "$SERVICE"
  fi
  exit 1
fi

rm -f "$REMOTE_ARCHIVE" "$REMOTE_CHECKSUM"
echo "Deployment $RELEASE_SHA is healthy."
REMOTE_SCRIPT
