# Security Notes

## Secrets handling

- Never commit real secrets, production room IDs, or production homeserver values.
- Keep local runtime secrets in `.env` only.
- Keep `.env.example` sanitized placeholders only.

## Auth model (current)

- Webhook callback auth: HMAC signature verification.
- Login foundation: opaque token issuance with persisted token hash.
- Password storage: bcrypt hash only (no plaintext).
- Role model: explicit `admin` and `reader`.

## Public repository safety checklist

Before creating or publishing a remote:

1. Ensure `.env.example` contains placeholders only.
2. Run secret scans:
   - `gitleaks git .`
3. Confirm no local secret files are tracked:
   - `git ls-files | rg '^\\.env$|^\\.env\\.'`
4. Review commit history for accidental leaks if sensitive values were ever committed.

## If a secret leak is detected

1. Rotate affected credentials immediately.
2. Rewrite local git history to purge leaked values.
3. Garbage-collect unreachable git objects.
4. Re-scan history before any push.

## Reporting security issues

Until a dedicated security policy file is added, report issues privately to repository maintainers and avoid opening public issue threads with exploit details.
