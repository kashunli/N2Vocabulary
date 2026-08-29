# WordService deployment

`.github/workflows/deploy.yml` deploys the Linux WordService when a commit is
pushed to `main`. It is deliberately an SSH-based deployment so the target can
remain an ordinary Linux VPS rather than needing a cloud-specific GitHub
Action.

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

## 5. Branch and first run

The current repository checkout still has `master` as its default branch. The
deployment workflow intentionally listens only to `main`, so create or rename
the production branch and make it the repository default before expecting an
automatic run. The existing verification workflow accepts both `master` and
`main` during this transition.

After the workflow file is present on `main`, push a small verified commit to
that branch. In the Actions tab, confirm that the run passes the frontend and
Rust checks, then watch the package, SSH, systemd, and health-check steps. A
successful run ends with `Deployment <commit> is healthy.`

The workflow keeps old release directories so rollback remains possible. Add a
separate, reviewed cleanup procedure after measuring the size of this repo's
tracked audio tree; do not delete the live `current` target or the state under
`/var/lib/n2-word-service`.
