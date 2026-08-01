#!/bin/sh
set -e

# /app is bind-mounted from the host and node_modules is a named volume, so the
# dependency tree outlives image rebuilds. When package.json changes, that volume
# silently keeps the old tree: Vite's dependency scan then fails on the missing
# package, skips pre-bundling entirely, and falls back to discovering deps one
# request at a time — each discovery forcing a full page reload. That is the slow
# first load. Re-sync whenever the lockfile no longer matches what was installed.
LOCK=/app/package-lock.json
STAMP=/app/node_modules/.lock-stamp

if [ ! -f "$LOCK" ]; then
	echo "entrypoint: no package-lock.json, skipping dependency sync" >&2
elif [ ! -f "$STAMP" ] || ! cmp -s "$LOCK" "$STAMP"; then
	echo "entrypoint: lockfile changed since install, running npm ci"
	npm ci --no-audit --no-fund
	cp "$LOCK" "$STAMP"
else
	echo "entrypoint: dependencies up to date"
fi

exec "$@"
