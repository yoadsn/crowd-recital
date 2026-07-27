#!/bin/bash
set -euo pipefail

# ─── Load credentials from .env ──────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: .env file not found at $ENV_FILE"
  echo "Copy .env.example to .env and fill in your xhost credentials."
  exit 1
fi

# shellcheck source=/dev/null
source "$ENV_FILE"

for var in XHOST_TOKEN XHOST_APP_ID XHOST_CHANNEL_ID XHOST_CHANNEL; do
  if [ -z "${!var:-}" ]; then
    echo "ERROR: $var is not set in .env"
    exit 1
  fi
done

XHOST_API="https://api.xhostd.com"
XHOST_USER="yoad"
REMOTE_URL="https://${XHOST_USER}:${XHOST_TOKEN}@git.xhostd.com/${XHOST_USER}/crowd-recital.git"
CLEAN_REMOTE_URL="https://git.xhostd.com/${XHOST_USER}/crowd-recital.git"
# The remote branch name on xhost (bound to the channel's git_ref_binding) - NOT
# necessarily the local branch name. Defaults to the channel name since that's
# our convention (preview channel <-> preview branch, prod channel <-> master).
BRANCH="${XHOST_BRANCH:-$XHOST_CHANNEL}"

# Always strip the token back out of the git remote on exit, even on a failed/
# interrupted run (Ctrl-C, a curl error under `set -e`, etc.) - it should never
# be left sitting in plaintext in .git/config.
cleanup() {
  git remote set-url xhost "$CLEAN_REMOTE_URL" 2>/dev/null || true
}
trap cleanup EXIT

echo "=== xhost deploy ==="
echo "App:     crowd-recital ($XHOST_APP_ID)"
echo "Channel: $XHOST_CHANNEL ($XHOST_CHANNEL_ID)"
echo "Branch:  $BRANCH"
echo ""

# ─── Configure git remote with auth ──────────────────────────────────────────
echo "Configuring xhost remote..."
# `set-url` fails if the remote was never added (e.g. a fresh clone) - add it
# first if missing, otherwise just point it at the token-bearing URL.
git remote add xhost "$REMOTE_URL" 2>/dev/null || git remote set-url xhost "$REMOTE_URL"

# ─── Push to xhost ───────────────────────────────────────────────────────────
echo "Pushing to xhost ($BRANCH)..."
# Push HEAD (whatever is currently checked out locally, regardless of its own
# branch name) to the named branch on xhost - do NOT assume the local branch
# is literally named "$BRANCH".
git push xhost "HEAD:$BRANCH" --force

# ─── Trigger deploy ──────────────────────────────────────────────────────────
echo ""
echo "Triggering deploy..."
DEPLOY_RESPONSE=$(curl -sS -X POST "$XHOST_API/apps/$XHOST_APP_ID/channels/$XHOST_CHANNEL_ID/deploy" \
  -H "Authorization: Bearer $XHOST_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"ref\": \"$BRANCH\"}")

DEPLOY_ID=$(echo "$DEPLOY_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['deploy_id'])" 2>/dev/null || echo "")

if [ -z "$DEPLOY_ID" ]; then
  echo "ERROR: Failed to trigger deploy"
  echo "$DEPLOY_RESPONSE"
  exit 1
fi

echo "Deploy queued: $DEPLOY_ID"
echo ""

# ─── Poll until the deploy reaches a terminal state ──────────────────────────
# Docker builds for this app (torch + stanza) can take several minutes on a
# cold cache and mere seconds on a warm one - poll instead of a fixed sleep.
echo "Waiting for build to complete..."
LOG_URL="$XHOST_API/apps/$XHOST_APP_ID/channels/$XHOST_CHANNEL_ID/logs?deploy=$DEPLOY_ID"
MAX_WAIT_SEC=600
ELAPSED=0
DEPLOY_LOG=""
while [ "$ELAPSED" -lt "$MAX_WAIT_SEC" ]; do
  DEPLOY_LOG=$(curl -sS "$LOG_URL" -H "Authorization: Bearer $XHOST_TOKEN")
  if echo "$DEPLOY_LOG" | grep -qE "^deploy (success|failed)"; then
    break
  fi
  sleep 5
  ELAPSED=$((ELAPSED + 5))
done

echo ""
echo "=== Build log ==="
echo "$DEPLOY_LOG"

if ! echo "$DEPLOY_LOG" | grep -q "^deploy success"; then
  echo ""
  echo "ERROR: deploy did not report success within ${MAX_WAIT_SEC}s (see log above)."
  exit 1
fi

# ─── Print preview URL ──────────────────────────────────────────────────────
APP_JSON=$(curl -sS "$XHOST_API/apps/$XHOST_APP_ID" \
  -H "Authorization: Bearer $XHOST_TOKEN")

HOSTNAME=$(echo "$APP_JSON" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for ch in data.get('channels', []):
    if ch['id'] == '$XHOST_CHANNEL_ID':
        print(ch.get('hostname', ''))
        break
" 2>/dev/null || echo "")

if [ -n "$HOSTNAME" ]; then
  echo ""
  echo "Preview: https://$HOSTNAME"
fi
