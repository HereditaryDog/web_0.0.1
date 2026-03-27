#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env.server"
FORWARD_TO="${1:-http://127.0.0.1:8000/webhooks/stripe/}"
EVENTS="checkout.session.completed,checkout.session.async_payment_succeeded,checkout.session.async_payment_failed,checkout.session.expired"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE" >&2
  exit 1
fi

set -a
source "$ENV_FILE"
set +a

if [[ -z "${STRIPE_SECRET_KEY:-}" ]]; then
  echo "STRIPE_SECRET_KEY is empty in .env.server" >&2
  exit 1
fi

if command -v stripe >/dev/null 2>&1; then
  STRIPE_BIN="$(command -v stripe)"
else
  STRIPE_BIN="$(brew --prefix stripe/stripe-cli/stripe 2>/dev/null)/bin/stripe"
fi

if [[ ! -x "$STRIPE_BIN" ]]; then
  echo "Stripe CLI not found. Install it first: brew install stripe/stripe-cli/stripe" >&2
  exit 1
fi

echo "Fetching current Stripe CLI webhook signing secret..."
CLI_SECRET="$("$STRIPE_BIN" listen \
  --api-key "$STRIPE_SECRET_KEY" \
  --events "$EVENTS" \
  --forward-to "$FORWARD_TO" \
  --skip-update \
  --print-secret)"

if [[ -z "$CLI_SECRET" ]]; then
  echo "Failed to obtain Stripe CLI webhook signing secret." >&2
  exit 1
fi

CURRENT_SECRET="$(sed -n 's/^STRIPE_WEBHOOK_SECRET=//p' "$ENV_FILE" | head -n 1)"
if [[ "$CURRENT_SECRET" != "$CLI_SECRET" ]]; then
  perl -0pi -e "s/^STRIPE_WEBHOOK_SECRET=.*/STRIPE_WEBHOOK_SECRET=$CLI_SECRET/m" "$ENV_FILE"
  echo "Updated STRIPE_WEBHOOK_SECRET in .env.server"
  docker compose --env-file "$ENV_FILE" up -d web >/dev/null
fi

echo "Forwarding Stripe webhook events to $FORWARD_TO"
echo "Using signing secret: $CLI_SECRET"
echo "Press Ctrl+C to stop."

exec "$STRIPE_BIN" listen \
  --api-key "$STRIPE_SECRET_KEY" \
  --events "$EVENTS" \
  --forward-to "$FORWARD_TO" \
  --skip-update
