#!/usr/bin/env bash
# Destroys the GCP resources created by scripts/provision_gcp.sh,
# scripts/deploy_app.sh, and scripts/provision_scheduler.sh:
#   - the GCS data bucket and the Cloud Build staging bucket
#   - the raw/staging/metrics BigQuery datasets (and all tables/views)
#   - the Cloud Run service and its Artifact Registry image repo, if deployed
#   - the Cloud Scheduler job and Cloud Run Job + its image repo, if provisioned
#   - the three dedicated service accounts (cloudbuild-deployer,
#     commerce-app-runtime, commerce-refresh-runtime)
#
# This is IRREVERSIBLE. It is provided for the owner to run manually and
# is never invoked automatically by the agent/pipeline. Requires an
# explicit --yes flag as a deliberate confirmation step.
#
# Required environment variables: GCP_PROJECT_ID, GCS_BUCKET
# Optional: BQ_DATASET_RAW / BQ_DATASET_STAGING / BQ_DATASET_METRICS /
#           GCP_REGION / SERVICE_NAME / SCHEDULER_LOCATION / JOB_NAME
#
# Usage:
#   GCP_PROJECT_ID=my-project GCS_BUCKET=my-project-commerce-lab \
#     ./scripts/teardown_gcp.sh --yes

set -euo pipefail

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
: "${GCS_BUCKET:?Set GCS_BUCKET}"
BQ_DATASET_RAW="${BQ_DATASET_RAW:-raw}"
BQ_DATASET_STAGING="${BQ_DATASET_STAGING:-staging}"
BQ_DATASET_METRICS="${BQ_DATASET_METRICS:-metrics}"
GCP_REGION="${GCP_REGION:-asia-northeast3}"
SERVICE_NAME="${SERVICE_NAME:-commerce-decision-app}"
SCHEDULER_LOCATION="${SCHEDULER_LOCATION:-$GCP_REGION}"
JOB_NAME="${JOB_NAME:-commerce-lab-refresh}"
BUILD_STAGING_BUCKET="${GCP_PROJECT_ID}-build-staging"

if [[ "${1:-}" != "--yes" ]]; then
    echo "Refusing to run: this permanently deletes the bucket gs://${GCS_BUCKET}"
    echo "and gs://${BUILD_STAGING_BUCKET}, the ${BQ_DATASET_RAW}/${BQ_DATASET_STAGING}/"
    echo "${BQ_DATASET_METRICS} datasets, the ${SERVICE_NAME} Cloud Run service + image"
    echo "repo, the ${JOB_NAME} Cloud Scheduler job + Cloud Run Job + image repo, and"
    echo "the cloudbuild-deployer/commerce-app-runtime/commerce-refresh-runtime service"
    echo "accounts, in project ${GCP_PROJECT_ID}."
    echo "Re-run with --yes to confirm."
    exit 1
fi

gcloud config set project "${GCP_PROJECT_ID}" >/dev/null

echo "Deleting bucket gs://${GCS_BUCKET} (and all objects) ..."
gcloud storage rm --recursive "gs://${GCS_BUCKET}" || echo "Bucket already absent."

echo "Deleting Cloud Build staging bucket gs://${BUILD_STAGING_BUCKET} ..."
gcloud storage rm --recursive "gs://${BUILD_STAGING_BUCKET}" || echo "Bucket already absent."

for dataset in "${BQ_DATASET_RAW}" "${BQ_DATASET_STAGING}" "${BQ_DATASET_METRICS}"; do
    echo "Deleting dataset ${dataset} (and all tables/views) ..."
    bq rm -r -f --dataset "${GCP_PROJECT_ID}:${dataset}" || echo "Dataset ${dataset} already absent."
done

echo "Deleting Cloud Run service ${SERVICE_NAME} (${GCP_REGION}) ..."
gcloud run services delete "${SERVICE_NAME}" --region="${GCP_REGION}" --quiet || echo "Service already absent."

echo "Deleting Artifact Registry repo ${SERVICE_NAME} (${GCP_REGION}) ..."
gcloud artifacts repositories delete "${SERVICE_NAME}" --location="${GCP_REGION}" --quiet || echo "Repo already absent."

echo "Deleting Cloud Scheduler job ${JOB_NAME} (${SCHEDULER_LOCATION}) ..."
gcloud scheduler jobs delete "${JOB_NAME}" --location="${SCHEDULER_LOCATION}" --quiet || echo "Scheduler job already absent."

echo "Deleting Cloud Run Job ${JOB_NAME} (${GCP_REGION}) ..."
gcloud run jobs delete "${JOB_NAME}" --region="${GCP_REGION}" --quiet || echo "Job already absent."

echo "Deleting Artifact Registry repo ${JOB_NAME} (${GCP_REGION}) ..."
gcloud artifacts repositories delete "${JOB_NAME}" --location="${GCP_REGION}" --quiet || echo "Repo already absent."

for SA in cloudbuild-deployer commerce-app-runtime commerce-refresh-runtime budget-hardcap-runtime; do
    echo "Deleting service account ${SA}@${GCP_PROJECT_ID}.iam.gserviceaccount.com ..."
    gcloud iam service-accounts delete "${SA}@${GCP_PROJECT_ID}.iam.gserviceaccount.com" --quiet \
        || echo "Service account already absent."
done

echo "Deleting budget hard-cap function budget-hardcap (${GCP_REGION}) ..."
gcloud functions delete budget-hardcap --region="${GCP_REGION}" --gen2 --quiet || echo "Function already absent."

echo "Deleting Pub/Sub topic budget-hardcap-alerts ..."
gcloud pubsub topics delete budget-hardcap-alerts --quiet || echo "Topic already absent."

echo "Note: the billing budget itself and its billing-account-level IAM grant"
echo "(roles/billing.user for budget-hardcap-runtime) are NOT removed by this"
echo "script -- the budget was created manually in the console and leaving it"
echo "is harmless; the IAM grant becomes inert once the SA above is deleted."

echo "Teardown complete."
