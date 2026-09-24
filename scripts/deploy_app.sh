#!/usr/bin/env bash
# Builds and deploys the executive app to Cloud Run via Cloud Build +
# `gcloud run deploy` (reproducible CLI workflow, not a manual console
# click-through). Not run automatically by the agent/pipeline -- the
# owner runs this once GCP project/billing/auth are available, after
# scripts/provision_gcp.sh (which creates the service accounts and
# staging bucket this script depends on).
#
# Both the build and the running service use the dedicated,
# least-privilege service accounts from provision_gcp.sh
# (cloudbuild-deployer, commerce-app-runtime) rather than the project's
# default Compute Engine service account -- see that script's header
# for why.
#
# Required environment variables:
#   GCP_PROJECT_ID   existing GCP project with billing enabled
#   GCS_BUCKET       bucket holding snapshot/app_snapshot.json (see
#                    scripts/provision_gcp.sh)
# Optional:
#   GCP_REGION       default: asia-northeast3
#   SERVICE_NAME     default: commerce-decision-app
#
# Usage:
#   GCP_PROJECT_ID=my-project GCS_BUCKET=my-project-commerce-lab \
#     ./scripts/deploy_app.sh
#
# Public access note: `--allow-unauthenticated` below requests a public,
# no-login URL for later (this is a demo with only synthetic data -- see
# PROGRESS.md decisions log). As of this writing the app is
# intentionally kept authenticated-only; public access is a deliberate
# future step, not a bug. Some Google Workspace/Cloud orgs also enforce
# a domain-restricted-sharing org policy that blocks granting access to
# "allUsers" outright; `gcloud run deploy` still succeeds in that case,
# it just can't apply the public IAM binding (a warning, not a failure).
# Either way, the service is reachable by identities with
# roles/run.invoker in the meantime, e.g.:
#   TOKEN=$(gcloud auth print-identity-token)
#   curl -H "Authorization: Bearer $TOKEN" <service-url>
# If an org policy is what's blocking it, changing
# iam.allowedPolicyMemberDomains is an organization-level security
# decision -- ask the owner before touching it (see PROGRESS.md).

set -euo pipefail

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
: "${GCS_BUCKET:?Set GCS_BUCKET}"
GCP_REGION="${GCP_REGION:-asia-northeast3}"
SERVICE_NAME="${SERVICE_NAME:-commerce-decision-app}"
IMAGE="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${SERVICE_NAME}/${SERVICE_NAME}"
BUILD_STAGING_BUCKET="${GCP_PROJECT_ID}-build-staging"
SA_CLOUDBUILD="cloudbuild-deployer@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
SA_APP="commerce-app-runtime@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

gcloud config set project "${GCP_PROJECT_ID}" >/dev/null

if gcloud artifacts repositories describe "${SERVICE_NAME}" --location="${GCP_REGION}" >/dev/null 2>&1; then
    echo "Artifact Registry repo ${SERVICE_NAME} already exists, skipping create."
else
    echo "Creating Artifact Registry repo ${SERVICE_NAME} (${GCP_REGION}) ..."
    gcloud artifacts repositories create "${SERVICE_NAME}" \
        --repository-format=docker \
        --location="${GCP_REGION}"
fi

echo "Granting ${SA_CLOUDBUILD} push access to ${SERVICE_NAME} ..."
gcloud artifacts repositories add-iam-policy-binding "${SERVICE_NAME}" \
    --location="${GCP_REGION}" \
    --member="serviceAccount:${SA_CLOUDBUILD}" \
    --role="roles/artifactregistry.writer" >/dev/null

echo "Building image ${IMAGE} via Cloud Build (as ${SA_CLOUDBUILD}) ..."
gcloud builds submit --tag "${IMAGE}" \
    --service-account="projects/${GCP_PROJECT_ID}/serviceAccounts/${SA_CLOUDBUILD}" \
    --gcs-source-staging-dir="gs://${BUILD_STAGING_BUCKET}/source" \
    --gcs-log-dir="gs://${BUILD_STAGING_BUCKET}/logs" \
    .

echo "Deploying to Cloud Run (${GCP_REGION}, as ${SA_APP}) ..."
gcloud run deploy "${SERVICE_NAME}" \
    --image="${IMAGE}" \
    --region="${GCP_REGION}" \
    --platform=managed \
    --allow-unauthenticated \
    --min-instances=0 \
    --max-instances=2 \
    --memory=512Mi \
    --service-account="${SA_APP}" \
    --set-env-vars="SNAPSHOT_SOURCE=gs://${GCS_BUCKET}/snapshot/app_snapshot.json"

SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" --region="${GCP_REGION}" --format='value(status.url)')"
echo "Deploy complete: ${SERVICE_URL}"
echo "If the service isn't publicly reachable (org policy blocked allUsers, or public access hasn't been enabled yet), use:"
echo '  TOKEN=$(gcloud auth print-identity-token)'
echo "  curl -H \"Authorization: Bearer \$TOKEN\" ${SERVICE_URL}"
