# WordService deployment

`.github/workflows/deploy.yml` deploys the Linux WordService when a commit is
pushed to `main`. It is deliberately an SSH-based deployment so the target can
remain an ordinary Linux VPS rather than needing a cloud-specific GitHub
Action.

The deployment package contains the release Rust binary, the committed React
assets, `wordService/data/n2vocab.sqlite`, the tracked `clips/` tree, and the
review evidence files that the service reads at startup. The package is
extracted into a commit-named directory and exposed through the `current`
symlink. The workflow restarts systemd and calls `/api/summary`; if the new
release is unhealthy, it switches the symlink back to the previous release and
restarts the service again.

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

## 2. Install the systemd unit

Copy the example environment file, change the HTTPS origin to the real public
origin, then install and enable the unit:

```bash
sudo install -o root -g root -m 0644 deploy/n2-word-service.env.example /etc/n2-word-service.env
sudoedit /etc/n2-word-service.env
sudo install -o root -g root -m 0644 deploy/n2-word-service.service /etc/systemd/system/n2-word-service.service
sudo systemctl daemon-reload
sudo systemctl enable n2-word-service.service
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

## 3. Permit the deployment restart

The deployment account needs passwordless permission for only this unit's
restart and status checks. Create a sudoers drop-in and validate it before
enabling Actions:

```text
# /etc/sudoers.d/n2-word-service-deploy
n2vocabulary ALL=(root) NOPASSWD: /usr/bin/systemctl restart n2-word-service.service, /usr/bin/systemctl is-active n2-word-service.service
```

Use `sudo visudo -cf /etc/sudoers.d/n2-word-service-deploy` to validate the
syntax. If the SSH account differs from `n2vocabulary`, replace the username
in this rule.

## 4. Configure the GitHub `production` environment

On the repository, open `Settings > Environments`, create an environment named
`production`, and add these environment variables:

| Variable | Example | Purpose |
| --- | --- | --- |
| `DEPLOY_HOST` | `vocabulary.example.com` | VPS hostname or IP |
| `DEPLOY_USER` | `n2vocabulary` | SSH deployment account |
| `DEPLOY_PORT` | `22` | Optional; defaults to `22` |
| `DEPLOY_ROOT` | `/opt/n2-vocabulary` | Optional; defaults to this path |
| `DEPLOY_SERVICE` | `n2-word-service.service` | Optional; defaults to this unit |
| `DEPLOY_HEALTHCHECK_URL` | `http://127.0.0.1:8767/api/summary` | Optional local health URL |
| `DEPLOY_URL` | `https://vocabulary.example.com/` | Optional Actions environment link |

Add these environment secrets:

| Secret | Value |
| --- | --- |
| `DEPLOY_SSH_PRIVATE_KEY` | The private Ed25519 key whose public key is in the deployment account's `authorized_keys` |
| `DEPLOY_KNOWN_HOSTS` | The verified `ssh-keyscan -H <host>` output for the VPS |

Do not disable host-key checking or put a private key in the repository. GitHub
secrets are passed to the job through the `secrets` context, while the
non-sensitive destination settings are environment variables. GitHub's
environment can additionally require approval before a production deployment.

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
