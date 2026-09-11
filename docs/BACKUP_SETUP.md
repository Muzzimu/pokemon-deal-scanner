# Durable backup setup

The scanner uses GitHub Actions cache for fast operational database continuity, but that cache is disposable. Long-horizon model research (T+1/T+3/T+7/T+14/T+30 calibration and T+90/T+180 holding diagnostics) is also backed up to the private repository `Muzzimu/pokemon-deal-scanner-backup`.

## One-time setup

1. Create a fine-grained GitHub personal access token restricted to `Muzzimu/pokemon-deal-scanner-backup`.
2. Give the token **Contents: Read and write** permission. Metadata read access is implicit.
3. In `Muzzimu/pokemon-deal-scanner`, add the token as the Actions repository secret `BACKUP_REPO_TOKEN`.
4. Never commit or paste the token into source files, issues, logs, or chat.

## Schedule

- A scheduled durable backup is attempted on Sunday after the successful daily scanner run.
- A manual `workflow_dispatch` also attempts a durable backup, which provides a convenient smoke test after initial setup.
- The first successful weekly/manual backup in each calendar month is also retained under `monthly/YYYY-MM.tar.gz`.

## Backup contents

Each archive contains:

- `db/pokemon_deal_scanner.sqlite`
- key model prediction/outcome/calibration exports
- current market-quality and TCGCSV reference/mapping outputs when available
- `scanner_status.json`
- `manifest.json` containing the source repository commit, Actions run ID, Dublin backup date/week/month and SHA-256 of the SQLite database

Before packaging, the workflow runs SQLite `PRAGMA integrity_check` and checkpoints the WAL.

## Recovery principle

The SQLite database is the canonical cumulative research history. Weekly/monthly archives are recovery points, not inputs to the live scanner unless a restore is intentionally performed.

## Access

The backup repository should remain private. If ChatGPT's GitHub connection is expected to inspect or maintain the repository directly, the GitHub app/connection must also be granted access to that private repository.