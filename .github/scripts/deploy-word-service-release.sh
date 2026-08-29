#!/usr/bin/env bash
set -Eeuo pipefail

: "${ARCHIVE:?Package step must provide ARCHIVE}"
: "${CHECKSUM:?Package step must provide CHECKSUM}"
: "${GITHUB_SHA:?GitHub Actions must provide GITHUB_SHA}"
: "${RUNNER_TEMP:?GitHub Actions must provide RUNNER_TEMP}"
: "${DEPLOY_PUBLIC_ORIGIN:=}"

key_file="$RUNNER_TEMP/n2-vocabulary-deploy-key"
known_hosts_file="$RUNNER_TEMP/n2-vocabulary-known-hosts"
remote_archive="/tmp/n2-vocabulary-${GITHUB_SHA}.tar.gz"
remote_checksum="${remote_archive}.sha256"
target="$DEPLOY_USER@$DEPLOY_HOST"

umask 077
printf '%s\n' "$DEPLOY_SSH_PRIVATE_KEY" > "$key_file"
if [[ -n "${DEPLOY_KNOWN_HOSTS:-}" ]]; then
  printf '%s\n' "$DEPLOY_KNOWN_HOSTS" > "$known_hosts_file"
else
  echo 'VPS_KNOWN_HOSTS is not configured; discovering the SSH host key for this run.'
  ssh-keyscan -T 10 -H -p "$DEPLOY_PORT" "$DEPLOY_HOST" > "$known_hosts_file"
  [[ -s "$known_hosts_file" ]] || { echo 'Could not discover the VPS SSH host key' >&2; exit 1; }
fi
# A throttled or unavailable VPS should fail this job promptly instead of
# leaving an SSH/SCP process running until GitHub Actions cancels the job.
ssh_opts=(-i "$key_file" -p "$DEPLOY_PORT" -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=15 -o ConnectionAttempts=1 -o ServerAliveInterval=15 -o ServerAliveCountMax=4 -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$known_hosts_file")
scp_opts=(-i "$key_file" -P "$DEPLOY_PORT" -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=15 -o ConnectionAttempts=1 -o ServerAliveInterval=15 -o ServerAliveCountMax=4 -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$known_hosts_file")

ssh "${ssh_opts[@]}" "$target" "install -d -m 0755 '$DEPLOY_ROOT/incoming' '$DEPLOY_ROOT/releases'"
scp "${scp_opts[@]}" "$ARCHIVE" "$target:$remote_archive"
scp "${scp_opts[@]}" "$CHECKSUM" "$target:$remote_checksum"

quoted_root=$(printf '%q' "$DEPLOY_ROOT")
quoted_sha=$(printf '%q' "$GITHUB_SHA")
quoted_archive=$(printf '%q' "$remote_archive")
quoted_checksum=$(printf '%q' "$remote_checksum")
quoted_service=$(printf '%q' "$DEPLOY_SERVICE")
quoted_healthcheck=$(printf '%q' "$DEPLOY_HEALTHCHECK_URL")
quoted_public_origin=$(printf '%q' "$DEPLOY_PUBLIC_ORIGIN")

ssh "${ssh_opts[@]}" "$target" \
  "DEPLOY_ROOT=$quoted_root RELEASE_SHA=$quoted_sha REMOTE_ARCHIVE=$quoted_archive REMOTE_CHECKSUM=$quoted_checksum SERVICE=$quoted_service HEALTHCHECK_URL=$quoted_healthcheck PUBLIC_ORIGIN=$quoted_public_origin bash -s" <<'REMOTE_SCRIPT'
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

bootstrap_service() {
  local service_unit="/etc/systemd/system/$SERVICE"
  local environment_file='/etc/n2-word-service.env'
  local bootstrap_dir="$release_dir/bootstrap"
  local generated_environment="$bootstrap_dir/n2-word-service.env"
  local need_unit=false
  local need_environment=false

  [[ -e "$service_unit" ]] || need_unit=true
  [[ -e "$environment_file" ]] || need_environment=true
  if [[ "$need_unit" == false && "$need_environment" == false ]]; then
    return
  fi

  if [[ "$SERVICE" != 'n2-word-service.service' ]]; then
    echo "Automatic bootstrap supports only n2-word-service.service, not $SERVICE" >&2
    exit 1
  fi
  test -f "$bootstrap_dir/n2-word-service.service"
  test -f "$bootstrap_dir/n2-word-service.env.example"

  if ! id -u n2vocabulary >/dev/null 2>&1; then
    sudo -n useradd --system --create-home --shell /usr/sbin/nologin n2vocabulary
  fi
  sudo -n install -d -o n2vocabulary -g n2vocabulary -m 0750 /var/lib/n2-word-service

  if [[ "$need_environment" == true ]]; then
    if [[ -z "$PUBLIC_ORIGIN" ]]; then
      echo 'Cannot create /etc/n2-word-service.env: set the DEPLOY_PUBLIC_ORIGIN repository variable to the public HTTPS origin first.' >&2
      exit 1
    fi
    case "$PUBLIC_ORIGIN" in
      https://*) ;;
      *)
        echo 'DEPLOY_PUBLIC_ORIGIN must begin with https:// for the public service.' >&2
        exit 1
        ;;
    esac
    while IFS= read -r line || [[ -n "$line" ]]; do
      if [[ "$line" == N2_WORD_SERVICE_ORIGIN=* ]]; then
        printf 'N2_WORD_SERVICE_ORIGIN=%s\n' "$PUBLIC_ORIGIN"
      else
        printf '%s\n' "$line"
      fi
    done < "$bootstrap_dir/n2-word-service.env.example" > "$generated_environment"
    sudo -n install -o root -g root -m 0644 "$generated_environment" "$environment_file"
    echo "Installed initial $environment_file. Future deployments will preserve it."
  fi

  if [[ "$need_unit" == true ]]; then
    sudo -n install -o root -g root -m 0644 "$bootstrap_dir/n2-word-service.service" "$service_unit"
    sudo -n systemctl daemon-reload
    sudo -n systemctl enable "$SERVICE"
    echo "Installed and enabled $SERVICE. Future deployments will preserve the unit file."
  fi
}

bootstrap_service

ln -sfn "$release_dir" "$DEPLOY_ROOT/current.next"
mv -Tf "$DEPLOY_ROOT/current.next" "$DEPLOY_ROOT/current"

healthy() {
  sudo -n systemctl is-active --quiet "$SERVICE" && \
    curl --fail --silent --show-error --retry 20 --retry-delay 1 "$HEALTHCHECK_URL" >/dev/null
}

if ! sudo -n systemctl restart "$SERVICE" || ! healthy; then
  echo 'New release failed its service or health check; attempting rollback.' >&2
  if [[ -n "$previous_target" ]]; then
    ln -sfn "$previous_target" "$DEPLOY_ROOT/current.next"
    mv -Tf "$DEPLOY_ROOT/current.next" "$DEPLOY_ROOT/current"
    sudo -n systemctl restart "$SERVICE"
  fi
  exit 1
fi

rm -f "$REMOTE_ARCHIVE" "$REMOTE_CHECKSUM"
echo "Deployment $RELEASE_SHA is healthy."
REMOTE_SCRIPT
