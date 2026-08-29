# WordService deployment

`.github/workflows/release.yml` builds a downloadable Linux WordService package
when a `v*` Git tag is pushed. `.github/workflows/deploy.yml` remains available
only as an explicit manual GitHub Actions fallback. Normal deployment is
deliberately an SSH-based local procedure so the target can remain an ordinary
Linux VPS rather than needing a cloud-specific GitHub Action.

The deployment package contains the release Rust binary, the committed React
assets, `wordService/data/n2vocab.sqlite`, the tracked `clips/` tree, review
evidence files, and bootstrap copies of the systemd unit and environment-file
template. The package is extracted into a commit-named directory and exposed
through the `current` symlink. The workflow restarts systemd and calls
`/api/summary`; if the new release is unhealthy, it switches the symlink back
to the previous release and restarts the service again.

The Rust release binary is built inside the official `rust:1-bookworm` container
on GitHub Actions. Bookworm is Debian 12 and uses glibc 2.36, so the artifact is
compatible with Debian 12 even though the GitHub runner itself may use a newer
glibc. The package step also inspects the ELF version requirements and rejects
anything newer than glibc 2.36. If the VPS is Debian 11 or older, build and test
against that older release instead; a binary built on Debian 12 is not a
guarantee for an older glibc.

## 1. Prepare the Linux host

Create an application user and the state directory. Replace `deploy` with the
SSH account that GitHub Actions will use if you choose a different account.

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin n2vocabulary
sudo install -d -o n2vocabulary -g n2vocabulary -m 0755 /opt/n2-vocabulary
sudo install -d -o n2vocabulary -g n2vocabulary -m 0750 /var/lib/n2-word-service
```

The SSH account must be able to create directories and files below
`/opt/n2-vocabulary`, and the service account must be able to read the release
tree. The simplest arrangement is to use `n2vocabulary` as the deployment SSH
user. If you use a separate deployment user, configure group membership and
ownership on `/opt/n2-vocabulary` before the first run.

The service currently supports lazy audio generation, which writes generated
clips and their paths into the content SQLite database. Therefore the release
content tree must be writable by `n2vocabulary` if those endpoints are enabled.
Treat the tracked content database and clips as the deployment source of truth:
review any server-side generated changes before a later release replaces that
content snapshot.

## 2. Automatic systemd bootstrap

On its first successful connection, the deployment installs and enables
`n2-word-service.service` if it is absent. It also creates
`/etc/n2-word-service.env` only if that file is absent; later deployments never
overwrite either file.

Before that first deployment, add the non-secret repository or `production`
environment variable `DEPLOY_PUBLIC_ORIGIN`, for example
`https://vocabulary.example.com`. It is used to set the exact HTTPS browser
origin required by the public service. `DEPLOY_URL` remains a compatibility
fallback when it already holds that same origin.

After bootstrap, inspect and adjust the preserved environment file if needed:

```bash
sudoedit /etc/n2-word-service.env
```

The reverse proxy should terminate HTTPS and forward to
`127.0.0.1:8767`. Start the service after the first workflow deployment, or
start it now only after placing a compatible release at
`/opt/n2-vocabulary/current`:

```bash
sudo systemctl start n2-word-service.service
sudo systemctl status n2-word-service.service
curl --fail http://127.0.0.1:8767/api/summary
```

The binary uses explicit environment paths because its normal local defaults
are based on the directory used when Rust compiled it. This is why the unit
must use `/etc/n2-word-service.env` rather than relying on the local Windows
defaults.

## 3. Permit deployment bootstrap and restart

The deployment account needs passwordless permission to create the dedicated
service account/state directory during first bootstrap, install the two
authoritative service files only when absent, and manage this unit. Create a
sudoers drop-in and validate it before enabling Actions:

```text
# /etc/sudoers.d/n2-word-service-deploy
deploy ALL=(root) NOPASSWD: /usr/sbin/useradd --system --create-home --shell /usr/sbin/nologin n2vocabulary, /usr/bin/install -d -o n2vocabulary -g n2vocabulary -m 0750 /var/lib/n2-word-service, /usr/bin/install -o root -g root -m 0644 /opt/n2-vocabulary/releases/*/bootstrap/n2-word-service.service /etc/systemd/system/n2-word-service.service, /usr/bin/install -o root -g root -m 0644 /opt/n2-vocabulary/releases/*/bootstrap/n2-word-service.env /etc/n2-word-service.env, /usr/bin/systemctl daemon-reload, /usr/bin/systemctl enable n2-word-service.service, /usr/bin/systemctl restart n2-word-service.service, /usr/bin/systemctl is-active n2-word-service.service
```

Use `sudo visudo -cf /etc/sudoers.d/n2-word-service-deploy` to validate the
syntax. The rule above uses the current GitHub Actions SSH account, `deploy`.
If that account changes, replace it with the new SSH username. Treat write
access to `main` as privileged: the first deployment can install the shipped
unit and environment template as root, while later runs preserve them.

## 4. Configure the GitHub deployment settings

Add these repository secrets under `Settings > Secrets and variables > Actions`:

| Secret | Example | Purpose |
| --- | --- | --- |
| `VPS_HOST` | `vocabulary.example.com` | VPS hostname or IP |
| `VPS_USER` | `n2vocabulary` | SSH deployment account |
| `VPS_PORT` | `22` | Optional; defaults to `22` |
| `VPS_SSH_KEY` | An Ed25519 private key | SSH authentication; its public key must be in `authorized_keys` |
| `VPS_KNOWN_HOSTS` | Verified `ssh-keyscan -H -p <port> <host>` output | Optional but recommended host-key pinning |

Optional non-sensitive overrides such as `DEPLOY_ROOT`, `DEPLOY_SERVICE`,
`DEPLOY_HEALTHCHECK_URL`, `DEPLOY_PUBLIC_ORIGIN`, and `DEPLOY_URL` can be added as repository or
`production` environment variables. When `VPS_KNOWN_HOSTS` is absent, the
workflow discovers the host key for that run and then enables strict host-key
checking. Pinning the verified key in the secret protects against a first-use
man-in-the-middle attack and is preferred for production.

Do not disable host-key checking or put a private key in the repository. GitHub
secrets are passed to the job through the `secrets` context. GitHub's production
environment can additionally require approval before a deployment.

## 5. Build a tagged release, then deploy it manually

Push a version tag such as `v0.1.0`. The tag workflow verifies the frontend and
Rust service, builds the binary in Debian Bookworm, verifies the glibc ABI, and
attaches the archive and its `.sha256` file to the matching GitHub Release.

```bash
git tag -a v0.1.0 -m "WordService v0.1.0"
git push origin v0.1.0
```

Download both release assets into the same local directory. Before the first
manual deployment, set `DEPLOY_PUBLIC_ORIGIN` to the real public HTTPS origin.
From a Bash environment with OpenSSH, run the repository deploy script against
the downloaded package:

```bash
export ARCHIVE='/path/to/n2-vocabulary-v0.1.0-<commit>.tar.gz'
export CHECKSUM="${ARCHIVE}.sha256"
export DEPLOY_HOST='masterofpuppet.cc'
export DEPLOY_USER='deploy'
export DEPLOY_PORT='22222'
export DEPLOY_ROOT='/opt/n2-vocabulary'
export DEPLOY_SERVICE='n2-word-service.service'
export DEPLOY_HEALTHCHECK_URL='http://127.0.0.1:8767/api/summary'
export DEPLOY_PUBLIC_ORIGIN='https://your-public-site.example'
export DEPLOY_SSH_KEY_FILE='/path/to/n2_deploy'
export DEPLOY_KNOWN_HOSTS_FILE='/path/to/known_hosts'
bash .github/scripts/deploy-word-service-release.sh
```

The script verifies the downloaded archive checksum locally, transfers the
exact archive, validates it again on the VPS, installs missing bootstrap files,
switches the `current` symlink only after extraction, restarts the service, and
checks `/api/summary`. The `RELEASE` file inside the archive supplies the commit
identifier, so no separate `RELEASE_ID` is normally needed.

The workflow keeps old release directories so rollback remains possible. Add a
separate, reviewed cleanup procedure after measuring the size of this repo's
tracked audio tree; do not delete the live `current` target or the state under
`/var/lib/n2-word-service`.
