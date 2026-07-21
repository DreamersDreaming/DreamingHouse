#!/usr/bin/env bash
set -euo pipefail

# Intended for AWS CloudShell in ap-southeast-2 (Sydney). The script never
# prints the CockroachDB URLs. It prints the generated judge key only after
# deployment so the founder can copy it into private judge instructions.
export AWS_REGION="${AWS_REGION:-ap-southeast-2}"
export AWS_DEFAULT_REGION="$AWS_REGION"

if [[ -z "${COCKROACH_ADMIN_URL:-}" ]]; then
  read -r -s -p "CockroachDB administrator connection URL: " COCKROACH_ADMIN_URL
  printf '\n'
  export COCKROACH_ADMIN_URL
fi

if [[ -z "${DEMO_API_KEY:-}" ]]; then
  DEMO_API_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  export DEMO_API_KEY
fi

python3 -m pip install --user -r requirements.txt
DATABASE_URL="$(python3 scripts/bootstrap_database.py)"
export DATABASE_URL
unset COCKROACH_ADMIN_URL

sam build
sam deploy \
  --stack-name doream-recall \
  --region "$AWS_REGION" \
  --resolve-s3 \
  --capabilities CAPABILITY_IAM \
  --no-confirm-changeset \
  --no-fail-on-empty-changeset \
  --parameter-overrides \
    DatabaseUrl="$DATABASE_URL" \
    DemoApiKey="$DEMO_API_KEY"

printf 'Deployment complete. Keep the following key private; it is not written to the repository.\n'
printf 'DEMO_API_KEY=%s\n' "$DEMO_API_KEY"
aws cloudformation describe-stacks \
  --stack-name doream-recall \
  --region "$AWS_REGION" \
  --query 'Stacks[0].Outputs[].[OutputKey,OutputValue]' \
  --output table
