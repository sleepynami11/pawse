#!/usr/bin/env bash
# Deploy the public demo to Cloud Run: bash scripts/deploy_cloudrun.sh <gcp-project> [region]
# One instance (min=max=1): the case cache in pawse/state.py is in memory.
# Before the first run, put the keys in Secret Manager, for example:
#   printf %s "$KEY" | gcloud secrets create pawse-gemini-key --data-file=- --project <gcp-project>
set -euo pipefail
PROJECT="${1:?usage: deploy_cloudrun.sh <gcp-project> [region]}"
REGION="${2:-europe-west6}"
SECRETS="GEMINI_API_KEY=pawse-gemini-key:latest"
if gcloud secrets describe pawse-gradium-key --project "$PROJECT" >/dev/null 2>&1; then
  SECRETS="$SECRETS,GRADIUM_API_KEY=pawse-gradium-key:latest"
fi
cd "$(dirname "$0")/.."
deploy() {
  gcloud run deploy pawse --project "$PROJECT" --region "$REGION" --source . \
    --allow-unauthenticated --min-instances 1 --max-instances 1 --timeout 3600 \
    --set-secrets "$SECRETS" --set-env-vars "^@^PAWSE_PUBLIC_DEMO=1@PAWSE_ALLOWED_HOSTS=$1" "${@:2}"
}
# The host allowlist needs the service URL, which only exists after the first deploy.
URL=$(gcloud run services describe pawse --project "$PROJECT" --region "$REGION" --format 'value(status.url)' 2>/dev/null || true)
deploy "${URL#https://}" --quiet
URL=$(gcloud run services describe pawse --project "$PROJECT" --region "$REGION" --format 'value(status.url)')
# Cloud Run serves two URLs (hash and project-number form); allow both.
HOSTS=$(gcloud run services describe pawse --project "$PROJECT" --region "$REGION" --format json | python3 -c '
import json, sys
d = json.load(sys.stdin)
urls = [d["status"]["url"], *json.loads(d["metadata"].get("annotations", {}).get("run.googleapis.com/urls", "[]"))]
print(",".join(sorted({u.removeprefix("https://") for u in urls})))')
gcloud run services update pawse --project "$PROJECT" --region "$REGION" --update-env-vars "^@^PAWSE_ALLOWED_HOSTS=$HOSTS" --quiet
curl -fsS "$URL/api/v1/health" && echo && echo "Live: $URL"
