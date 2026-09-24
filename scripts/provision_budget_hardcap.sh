#!/usr/bin/env bash
# Reproducible provisioning for a billing hard cap: when the existing
# "commerce-decision-demo safety budget" (see provision_gcp.sh's sibling
# owner-run console step, PROGRESS.md) reports spend >= 100% of its
# threshold, a Cloud Function disables billing on this project. This is a
# hard cap, not the budget's own alert emails -- see PROGRESS.md "예산
# 하드캡" decision entry for the tradeoff (it takes every billable
# resource in the project offline, including the public Cloud Run app,
# until the owner manually re-links billing).
#
# Idempotent: safe to re-run. Does NOT create the budget itself (already
# exists, created by the owner in the console) and does NOT grant the
# billing-account-level IAM role the function's service account needs to
# actually call the Billing API -- billing-account IAM is deliberately
# left as an owner-run step (see printed instructions at the end), same
# pattern as the org-policy override in PROGRESS.md "공개 전환 실행 기록".
#
# Required environment variables:
#   GCP_PROJECT_ID           existing GCP project (billing already enabled)
#   GCP_BILLING_ACCOUNT_ID   e.g. 015716-BC65BE-E667BC
# Optional:
#   GCP_REGION               default: asia-northeast3
#   BUDGET_DISPLAY_NAME      default: commerce-decision-demo safety budget
#
# Usage:
#   GCP_PROJECT_ID=commerce-decision-demo \
#     GCP_BILLING_ACCOUNT_ID=015716-BC65BE-E667BC \
#     ./scripts/provision_budget_hardcap.sh

set -euo pipefail

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID to an existing GCP project ID}"
: "${GCP_BILLING_ACCOUNT_ID:?Set GCP_BILLING_ACCOUNT_ID, e.g. 015716-BC65BE-E667BC}"
GCP_REGION="${GCP_REGION:-asia-northeast3}"
BUDGET_DISPLAY_NAME="${BUDGET_DISPLAY_NAME:-commerce-decision-demo safety budget}"

TOPIC_NAME="budget-hardcap-alerts"
FUNCTION_NAME="budget-hardcap"
SA_NAME="budget-hardcap-runtime"
SA_EMAIL="${SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

echo "Project: ${GCP_PROJECT_ID}  Region: ${GCP_REGION}  Billing account: ${GCP_BILLING_ACCOUNT_ID}"

gcloud config set project "${GCP_PROJECT_ID}" >/dev/null

echo "Enabling required APIs ..."
gcloud services enable \
    pubsub.googleapis.com \
    cloudfunctions.googleapis.com \
    eventarc.googleapis.com \
    cloudbilling.googleapis.com \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    --project="${GCP_PROJECT_ID}"

if gcloud pubsub topics describe "${TOPIC_NAME}" --project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
    echo "Pub/Sub topic ${TOPIC_NAME} already exists, skipping create."
else
    echo "Creating Pub/Sub topic ${TOPIC_NAME} ..."
    gcloud pubsub topics create "${TOPIC_NAME}" --project="${GCP_PROJECT_ID}"
fi

echo "Locating budget \"${BUDGET_DISPLAY_NAME}\" ..."
# --filter's displayName matching has been unreliable across gcloud
# versions for values containing spaces (see the "operator evaluation is
# changing" warning); list-and-grep client-side instead.
BUDGET_ID="$(gcloud billing budgets list \
    --billing-account="${GCP_BILLING_ACCOUNT_ID}" \
    --format="csv[no-heading](name.basename(),displayName)" \
    | awk -F',' -v name="${BUDGET_DISPLAY_NAME}" '$2==name {print $1}')"
if [ -z "${BUDGET_ID}" ]; then
    echo "ERROR: no budget named \"${BUDGET_DISPLAY_NAME}\" found on billing account ${GCP_BILLING_ACCOUNT_ID}." >&2
    echo "This script does not create the budget itself -- create it in the console first." >&2
    exit 1
fi
echo "  found budget ${BUDGET_ID}"

echo "Linking budget to Pub/Sub topic ..."
gcloud billing budgets update "${BUDGET_ID}" \
    --billing-account="${GCP_BILLING_ACCOUNT_ID}" \
    --notifications-rule-pubsub-topic="projects/${GCP_PROJECT_ID}/topics/${TOPIC_NAME}" \
    >/dev/null

if gcloud iam service-accounts describe "${SA_EMAIL}" >/dev/null 2>&1; then
    echo "Service account ${SA_NAME} already exists, skipping create."
else
    echo "Creating service account ${SA_NAME} ..."
    gcloud iam service-accounts create "${SA_NAME}" \
        --display-name="Budget hard-cap function runtime (disables billing only)"
fi

echo "Granting project-scoped role that has no finer-grained equivalent ..."
# billing.projectManager is what lets the function's identity call
# projects.updateBillingInfo on THIS project; it does not by itself allow
# re-linking any billing account (that needs the billing-account-level
# role granted separately below, by the owner).
gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" --role="roles/billing.projectManager" \
    --condition=None >/dev/null

# Cloud Functions gen2 builds with the project's default Compute Engine
# service account unless told otherwise, and (same finding as
# provision_gcp.sh's header comment) a fresh project's default Compute SA
# has no roles at all -- its build silently fails deep inside the
# buildpack step with no useful log output. Reuse the already-permissioned
# cloudbuild-deployer identity instead, granting it access to the two
# gen2-specific resources it doesn't already have:
#   - the auto-created "gcf-artifacts" Artifact Registry repo (image push)
#   - the auto-created gcf-v2-sources-* GCS bucket (source fetch)
echo "Granting cloudbuild-deployer access to Cloud Functions' auto-created build resources ..."
gcloud services enable cloudfunctions.googleapis.com --project="${GCP_PROJECT_ID}" >/dev/null
if ! gcloud artifacts repositories describe gcf-artifacts --location="${GCP_REGION}" --project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
    echo "  gcf-artifacts repo doesn't exist yet -- it's created by the first function deploy attempt below; re-run this script if that first attempt fails on a permission error."
fi
gcloud artifacts repositories add-iam-policy-binding gcf-artifacts \
    --location="${GCP_REGION}" --project="${GCP_PROJECT_ID}" \
    --member="serviceAccount:cloudbuild-deployer@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/artifactregistry.writer" >/dev/null 2>&1 || true
GCF_SOURCE_BUCKET="gcf-v2-sources-$(gcloud projects describe "${GCP_PROJECT_ID}" --format='value(projectNumber)')-${GCP_REGION}"
gcloud storage buckets add-iam-policy-binding "gs://${GCF_SOURCE_BUCKET}" \
    --member="serviceAccount:cloudbuild-deployer@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/storage.objectViewer" >/dev/null 2>&1 || true

echo "Deploying Cloud Function ${FUNCTION_NAME} (2nd gen) ..."
gcloud functions deploy "${FUNCTION_NAME}" \
    --project="${GCP_PROJECT_ID}" \
    --region="${GCP_REGION}" \
    --gen2 \
    --runtime=python312 \
    --source="$(dirname "$0")/budget_hardcap" \
    --entry-point=stop_billing \
    --trigger-topic="${TOPIC_NAME}" \
    --service-account="${SA_EMAIL}" \
    --build-service-account="projects/${GCP_PROJECT_ID}/serviceAccounts/cloudbuild-deployer@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
    --set-env-vars="GCP_PROJECT_ID=${GCP_PROJECT_ID}" \
    --memory=256Mi \
    --timeout=60s \
    --max-instances=1 \
    --no-allow-unauthenticated

# The gcf-artifacts repo and gcf-v2-sources-* bucket only exist after the
# first deploy attempt creates them -- if this is the very first run, that
# attempt fails on a permission error before the bindings above have
# anything to attach to. Re-grant and retry once in that case.
if ! gcloud functions describe "${FUNCTION_NAME}" --region="${GCP_REGION}" --project="${GCP_PROJECT_ID}" --gen2 --format='value(state)' 2>/dev/null | grep -q ACTIVE; then
    echo "First deploy attempt likely failed before gcf-artifacts/gcf-v2-sources-* existed -- retrying once now that they exist ..."
    gcloud artifacts repositories add-iam-policy-binding gcf-artifacts \
        --location="${GCP_REGION}" --project="${GCP_PROJECT_ID}" \
        --member="serviceAccount:cloudbuild-deployer@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
        --role="roles/artifactregistry.writer" >/dev/null
    gcloud storage buckets add-iam-policy-binding "gs://${GCF_SOURCE_BUCKET}" \
        --member="serviceAccount:cloudbuild-deployer@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
        --role="roles/storage.objectViewer" >/dev/null
    gcloud functions deploy "${FUNCTION_NAME}" \
        --project="${GCP_PROJECT_ID}" \
        --region="${GCP_REGION}" \
        --gen2 \
        --runtime=python312 \
        --source="$(dirname "$0")/budget_hardcap" \
        --entry-point=stop_billing \
        --trigger-topic="${TOPIC_NAME}" \
        --service-account="${SA_EMAIL}" \
        --build-service-account="projects/${GCP_PROJECT_ID}/serviceAccounts/cloudbuild-deployer@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
        --set-env-vars="GCP_PROJECT_ID=${GCP_PROJECT_ID}" \
        --memory=256Mi \
        --timeout=60s \
        --max-instances=1 \
        --no-allow-unauthenticated
fi

echo "Granting the function's own identity permission to invoke itself ..."
# gen2 functions run as ordinary Cloud Run services underneath; Eventarc
# delivers Pub/Sub events as an authenticated push using the function's
# own service account as the OIDC identity, which needs roles/run.invoker
# on that same underlying Cloud Run service or delivery 403s.
gcloud run services add-iam-policy-binding "${FUNCTION_NAME}" \
    --region="${GCP_REGION}" --project="${GCP_PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" --role="roles/run.invoker" >/dev/null

echo
echo "Provisioning complete, EXCEPT one step this script cannot do:"
echo "  the function's service account still needs a billing-account-level"
echo "  role to actually call the Billing API. Grant it once, as an owner"
echo "  with roles/billing.admin on the billing account:"
echo
echo "    gcloud billing accounts add-iam-policy-binding ${GCP_BILLING_ACCOUNT_ID} \\"
echo "      --member=\"serviceAccount:${SA_EMAIL}\" --role=\"roles/billing.user\""
echo
echo "  Until that's run, budget alert emails still fire, but the hard cap"
echo "  itself will NOT take effect -- the function will error out with a"
echo "  permission-denied when it tries to disable billing. Check with:"
echo "    gcloud functions logs read ${FUNCTION_NAME} --region=${GCP_REGION} --gen2"
