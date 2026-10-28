# GitHub integration

The application accepts GitHub webhooks and links commits and pull requests to
issues. The integration is deliberately webhook-first: it works with a normal
repository webhook, a GitHub App, or a local simulator, with no OAuth setup
required for the link metadata.

## Configure

1. Set a secret in `.env` and restart the app:
   ```bash
   GITHUB_WEBHOOK_SECRET=choose-a-long-random-string
   docker compose up -d app
   ```
   Existing installations can also set `github.webhook_secret` through the
   admin configuration. When the secret is empty, signature verification is
   skipped (development only).

2. In GitHub, open **Repository → Settings → Webhooks → Add webhook**:
   - Payload URL: `https://your-host/webhooks/github`
   - Content type: `application/json`
   - Secret: the same value as `GITHUB_WEBHOOK_SECRET`
   - Events: **Pull requests** and **Pushes**

3. Reference issues in the PR title, body or branch, or in commit messages:
   `Fixes #42`, `Closes #42`, `feature/42-payment-retry`.

## What gets stored

| Table | Content |
|---|---|
| `issue_link` | provider, repo, kind (`pull_request`/`commit`), external id, URL, state, metadata |
| `dora_event` | repo, kind, external id, timestamp, value, metadata — ready for DORA calculations |

Linked work is shown on the issue page under **Linked work**. The command
center shows commit and pull-request activity for the last 30 days when events
exist.

## Local simulation

With no secret configured:

```bash
curl -X POST http://localhost:9090/webhooks/github \
  -H 'Content-Type: application/json' \
  -H 'X-GitHub-Event: pull_request' \
  -d '{
    "action": "opened",
    "number": 42,
    "pull_request": {
      "number": 42,
      "title": "Fix #364 sprint task",
      "body": "Closes #364",
      "head": {"ref": "fix/364"},
      "html_url": "https://github.com/acme/repo/pull/42",
      "state": "open",
      "merged": false,
      "updated_at": "2026-10-28T13:00:00Z"
    },
    "repository": {"full_name": "acme/repo"}
  }'
```

Open issue `#364` to see the linked pull request. With a secret configured, add
the `X-Hub-Signature-256: sha256=...` header generated from the raw body.

## Optional auto-close

Set `github.auto_close` to `1` in the config table (or the admin config) to close
linked issues when a PR is merged. It is off by default because many teams want
a human review step.
