#!/usr/bin/env bash
# Builds the refresh-job image, creates/updates a Cloud Run Job, and
# wires a Cloud Scheduler job to trigger it daily -- the PROJECT.md §10
# "Cloud Scheduler -> scheduled refresh" automation. Idempotent (checks
# for existing resources before creating). Never invoked automatically;
# the owner runs this once GCP project/billing/auth are available, after
# scripts/provision_gcp.sh (which creates the service account and
# staging bucket this script depends on).
#
# Uses the dedicated `commerce-refresh-runtime` service account (created
# by provision_gcp.sh, least-privilege: GCS read/write on the data
# bucket, BigQuery WRITER on the three datasets, bigquery.jobUser,
# aiplatform.user) as both the Cloud Run Job's own runtime identity and
# the Cloud Scheduler's caller identity. Reusing one dedicated SA for
# both purposes -- not the project's broad default Compute Engine SA --
# is the pattern Google's own Cloud Run Jobs + Scheduler tutorials use;
# see PROGRESS.md for the write-up of why the default SA was rejected.
#
# Builds via a Cloud Build config file (cloudbuild.job.yaml), not the
# `--tag`/`--dockerfile` shortcut: this gcloud version has no
# --dockerfile flag, and --tag alone only looks for a file literally
# named "Dockerfile", not Dockerfile.job.
#
# Required environment variables: GCP_PROJECT_ID, GCS_BUCKET
# Optional:
#   GCP_REGION          default: asia-northeast3
#   SCHEDULER_LOCATION   default: same as GCP_REGION (override if Cloud
#                        Scheduler isn't available there -- verify with
#                        `gcloud scheduler locations list`)
#   JOB_NAME             default: commerce-lab-refresh
#   SCHEDULE             default: "0 6 * * *" (06:00 daily)
#   TIME_ZONE             default: Asia/Seoul
#
# Usage:
#   GCP_PROJECT_ID=my-project GCS_BUCKET=my-project-commerce-lab \
#     ./scripts/provision_scheduler.sh

set -euo pipefail

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
: "${GCS_BUCKET:?Set GCS_BUCKET}"
GCP_REGION="${GCP_REGION:-asia-northeast3}"
SCHEDULER_LOCATION="${SCHEDULER_LOCATION:-$GCP_REGION}"
JOB_NAME="${JOB_NAME:-commerce-lab-refresh}"
SCHEDULE="${SCHEDULE:-0 6 * * *}"
TIME_ZONE="${TIME_ZONE:-Asia/Seoul}"
JOB_IMAGE="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${JOB_NAME}/${JOB_NAME}"
BUILD_STAGING_BUCKET="${GCP_PROJECT_ID}-build-staging"
SA_CLOUDBUILD="cloudbuild-deployer@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
SA_REFRESH="commerce-refresh-runtime@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

gcloud config set project "${GCP_PROJECT_ID}" >/dev/null

if gcloud artifacts repositories describe "${JOB_NAME}" --location="${GCP_REGION}" >/dev/null 2>&1; then
    echo "Artifact Registry repo ${JOB_NAME} already exists, skipping create."
else
    echo "Creating Artifact Registry repo ${JOB_NAME} (${GCP_REGION}) ..."
    gcloud artifacts repositories create "${JOB_NAME}" \
        --repository-format=docker \
        --location="${GCP_REGION}"
fi

echo "Granting ${SA_CLOUDBUILD} push access to ${JOB_NAME} ..."
gcloud artifacts repositories add-iam-policy-binding "${JOB_NAME}" \
    --location="${GCP_REGION}" \
    --member="serviceAccount:${SA_CLOUDBUILD}" \
    --role="roles/artifactregistry.writer" >/dev/null

echo "Building refresh-job image ${JOB_IMAGE} via Cloud Build (as ${SA_CLOUDBUILD}) ..."
gcloud builds submit --config=cloudbuild.job.yaml --substitutions=_IMAGE="${JOB_IMAGE}" \
    --service-account="projects/${GCP_PROJECT_ID}/serviceAccounts/${SA_CLOUDBUILD}" \
    --gcs-source-staging-dir="gs://${BUILD_STAGING_BUCKET}/source" \
    --gcs-log-dir="gs://${BUILD_STAGING_BUCKET}/logs" \
    .

if gcloud run jobs describe "${JOB_NAME}" --region="${GCP_REGION}" >/dev/null 2>&1; then
    echo "Updating existing Cloud Run Job ${JOB_NAME} ..."
    ACTION=update
else
    echo "Creating Cloud Run Job ${JOB_NAME} ..."
    ACTION=create
fi
gcloud run jobs "${ACTION}" "${JOB_NAME}" \
    --image="${JOB_IMAGE}" \
    --region="${GCP_REGION}" \
    --max-retries=1 \
    --task-timeout=600 \
    --service-account="${SA_REFRESH}" \
    --set-env-vars="GCP_PROJECT_ID=${GCP_PROJECT_ID},GCS_BUCKET=${GCS_BUCKET}"

echo "Granting ${SA_REFRESH} permission to invoke ${JOB_NAME} (Scheduler -> Job caller identity) ..."
gcloud run jobs add-iam-policy-binding "${JOB_NAME}" \
    --region="${GCP_REGION}" \
    --member="serviceAccount:${SA_REFRESH}" \
    --role="roles/run.invoker" >/dev/null

SCHEDULER_URI="https://run.googleapis.com/v2/projects/${GCP_PROJECT_ID}/locations/${GCP_REGION}/jobs/${JOB_NAME}:run"

if gcloud scheduler jobs describe "${JOB_NAME}" --location="${SCHEDULER_LOCATION}" >/dev/null 2>&1; then
    echo "Updating existing Cloud Scheduler job ${JOB_NAME} ..."
    gcloud scheduler jobs update http "${JOB_NAME}" \
        --location="${SCHEDULER_LOCATION}" \
        --schedule="${SCHEDULE}" \
        --time-zone="${TIME_ZONE}" \
        --uri="${SCHEDULER_URI}" \
        --http-method=POST \
        --oauth-service-account-email="${SA_REFRESH}" \
        --oauth-token-scope="https://www.googleapis.com/auth/cloud-platform"
else
    echo "Creating Cloud Scheduler job ${JOB_NAME} (${SCHEDULE}, ${TIME_ZONE}) ..."
    gcloud scheduler jobs create http "${JOB_NAME}" \
        --location="${SCHEDULER_LOCATION}" \
        --schedule="${SCHEDULE}" \
        --time-zone="${TIME_ZONE}" \
        --uri="${SCHEDULER_URI}" \
        --http-method=POST \
        --oauth-service-account-email="${SA_REFRESH}" \
        --oauth-token-scope="https://www.googleapis.com/auth/cloud-platform"
fi

echo "Scheduler provisioning complete: ${JOB_NAME} runs on '${SCHEDULE}' (${TIME_ZONE})."
