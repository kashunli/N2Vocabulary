#!/usr/bin/env bash
set -Eeuo pipefail

# Keep the VPS boundary explicit: unknown configuration must stop before any
# build work, and SSH host identity must be pinned rather than discovered live.
: "${DEPLOY_HOST:?Set repository secret VPS_HOST}"
: "${DEPLOY_USER:?Set repository secret VPS_USER}"
: "${DEPLOY_SSH_PRIVATE_KEY:?Set repository secret VPS_SSH_KEY}"
: "${DEPLOY_KNOWN_HOSTS:?Set repository secret VPS_KNOWN_HOSTS to the target SSH host key}"
[[ "$DEPLOY_PORT" =~ ^[0-9]+$ ]] || { echo 'VPS_PORT must be numeric' >&2; exit 1; }
[[ "$DEPLOY_ROOT" =~ ^/[A-Za-z0-9_-]+(/[A-Za-z0-9._-]+)*$ ]] || { echo 'DEPLOY_ROOT must be an absolute path without shell-special characters' >&2; exit 1; }
[[ "$DEPLOY_SERVICE" =~ ^[A-Za-z0-9_.@-]+$ ]] || { echo 'DEPLOY_SERVICE contains unsupported characters' >&2; exit 1; }
