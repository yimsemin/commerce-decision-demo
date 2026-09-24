#!/usr/bin/env bash
# Reproducible provisioning script (not Terraform/IaC by design -- see
# PROGRESS.md decisions log) for the GCP resources this project needs:
#   - required APIs (Storage, BigQuery, Cloud Run, Cloud Build,
#     Cloud Scheduler, Vertex AI, Artifact Registry)
#   - one GCS bucket for data (raw synthetic-data + app snapshot) and
#     one for Cloud Build source/log staging
#   - three BigQuery datasets: raw, staging, metrics (+ raw tables and
#     staging/metrics views)
#   - three dedicated, least-privilege service accounts (standard GCP
#     practice: since mid-2024 a fresh project's default Compute Engine
#     service account has NO project-level roles by default, and Google
#     explicitly recommends dedicated service accounts over relying on
#     it -- see https://docs.cloud.google.com/build/docs/cloud-build-service-account-updates):
#       cloudbuild-deployer       builds container images (Cloud Build)
#       commerce-app-runtime      runs the Cloud Run web app (read-only)
#       commerce-refresh-runtime  runs the refresh Cloud Run Job and
#                                 authenticates the Cloud Scheduler
#                                 trigger (read/write)
#     Each is granted roles scoped to the specific bucket/dataset/repo
#     it needs, not the project as a whole, except where GCP's IAM model
#     has no finer grain (BigQuery job execution and Vertex AI
#     prediction are project-scoped resources, not per-dataset/model --
#     this is normal, not a workaround).
#
# Idempotent: safe to re-run. Uses `gcloud storage` (not the legacy
# `gsutil`) and `bq`. Does NOT create a GCP project, enable billing, or
# grant any IAM role to anyone other than this project's own dedicated
# service accounts -- creating a project / linking billing / any
# broader IAM change stays an owner-only action per CLAUDE.md.
#
# Windows note: if `bq` fails with "python3.14: command not found" even
# though Python 3.14 is on PATH, `bq`'s own interpreter-selection logic
# doesn't recognize 3.14 yet. This is `bq`'s own documented override
# mechanism (see its --help), not a hack:
#   CLOUDSDK_PYTHON="C:\Python314\python.exe" CLOUDSDK_BQ_PYTHON="C:\Python314\python.exe" ./scripts/provision_gcp.sh
#
# Required environment variables:
#   GCP_PROJECT_ID   existing GCP project with billing already enabled
#   GCS_BUCKET       globally-unique bucket name to create/use
# Optional:
#   GCP_REGION       default: asia-northeast3
#   BQ_DATASET_RAW / BQ_DATASET_STAGING / BQ_DATASET_METRICS
#                    defaults: raw / staging / metrics
#
# Usage:
#   GCP_PROJECT_ID=my-project GCS_BUCKET=my-project-commerce-lab \
#     ./scripts/provision_gcp.sh

set -euo pipefail

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID to an existing GCP project ID}"
: "${GCS_BUCKET:?Set GCS_BUCKET to the bucket name to create/use}"
GCP_REGION="${GCP_REGION:-asia-northeast3}"
BQ_DATASET_RAW="${BQ_DATASET_RAW:-raw}"
BQ_DATASET_STAGING="${BQ_DATASET_STAGING:-staging}"
BQ_DATASET_METRICS="${BQ_DATASET_METRICS:-metrics}"
BUILD_STAGING_BUCKET="${GCP_PROJECT_ID}-build-staging"

SA_CLOUDBUILD="cloudbuild-deployer@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
SA_APP="commerce-app-runtime@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
SA_REFRESH="commerce-refresh-runtime@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

# Reuse whatever Python the operator already pointed `bq` at (see the
# Windows note above); on Windows a bare `python3` may resolve to the
# Microsoft Store's non-functional stub, so verify before trusting it.
PYTHON_BIN="${CLOUDSDK_PYTHON:-${CLOUDSDK_BQ_PYTHON:-}}"
if [ -z "${PYTHON_BIN}" ]; then
    if command -v python3 >/dev/null 2>&1 && python3 -c "" >/dev/null 2>&1; then
        PYTHON_BIN=python3
    else
        PYTHON_BIN=python
    fi
fi

echo "Project: ${GCP_PROJECT_ID}  Region: ${GCP_REGION}  Bucket: ${GCS_BUCKET}"

gcloud config set project "${GCP_PROJECT_ID}" >/dev/null

echo "Enabling required APIs ..."
gcloud services enable \
    storage.googleapis.com \
    bigquery.googleapis.com \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    cloudscheduler.googleapis.com \
    aiplatform.googleapis.com \
    artifactregistry.googleapis.com \
    --project="${GCP_PROJECT_ID}"

echo "Creating dedicated service accounts (if missing) ..."
for pair in "cloudbuild-deployer:Cloud Build deployer" \
            "commerce-app-runtime:Cloud Run app runtime (read-only)" \
            "commerce-refresh-runtime:Refresh job runtime + Scheduler caller"; do
    NAME="${pair%%:*}"
    DISPLAY="${pair#*:}"
    if gcloud iam service-accounts describe "${NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com" >/dev/null 2>&1; then
        echo "  ${NAME} already exists, skipping create."
    else
        gcloud iam service-accounts create "${NAME}" --display-name="${DISPLAY}"
    fi
done

if gcloud storage buckets describe "gs://${GCS_BUCKET}" >/dev/null 2>&1; then
    echo "Bucket gs://${GCS_BUCKET} already exists, skipping create."
else
    echo "Creating bucket gs://${GCS_BUCKET} in ${GCP_REGION} ..."
    gcloud storage buckets create "gs://${GCS_BUCKET}" \
        --project="${GCP_PROJECT_ID}" \
        --location="${GCP_REGION}" \
        --uniform-bucket-level-access \
        --public-access-prevention
fi

if gcloud storage buckets describe "gs://${BUILD_STAGING_BUCKET}" >/dev/null 2>&1; then
    echo "Bucket gs://${BUILD_STAGING_BUCKET} already exists, skipping create."
else
    echo "Creating Cloud Build source/log staging bucket gs://${BUILD_STAGING_BUCKET} ..."
    gcloud storage buckets create "gs://${BUILD_STAGING_BUCKET}" \
        --project="${GCP_PROJECT_ID}" \
        --location="${GCP_REGION}" \
        --uniform-bucket-level-access \
        --public-access-prevention
fi

echo "Granting bucket-scoped roles ..."
gcloud storage buckets add-iam-policy-binding "gs://${GCS_BUCKET}" \
    --member="serviceAccount:${SA_APP}" --role="roles/storage.objectViewer" >/dev/null
gcloud storage buckets add-iam-policy-binding "gs://${GCS_BUCKET}" \
    --member="serviceAccount:${SA_REFRESH}" --role="roles/storage.objectAdmin" >/dev/null
gcloud storage buckets add-iam-policy-binding "gs://${BUILD_STAGING_BUCKET}" \
    --member="serviceAccount:${SA_CLOUDBUILD}" --role="roles/storage.objectAdmin" >/dev/null
# objectAdmin alone only covers object.* permissions; Cloud Build also
# needs bucket.get to validate the staging bucket, which requires this
# additional (bucket-scoped, still least-privilege) role.
gcloud storage buckets add-iam-policy-binding "gs://${BUILD_STAGING_BUCKET}" \
    --member="serviceAccount:${SA_CLOUDBUILD}" --role="roles/storage.legacyBucketReader" >/dev/null

for dataset in "${BQ_DATASET_RAW}" "${BQ_DATASET_STAGING}" "${BQ_DATASET_METRICS}"; do
    if bq show --dataset "${GCP_PROJECT_ID}:${dataset}" >/dev/null 2>&1; then
        echo "Dataset ${dataset} already exists, skipping create."
    else
        echo "Creating BigQuery dataset ${dataset} in ${GCP_REGION} ..."
        bq mk --dataset --location="${GCP_REGION}" "${GCP_PROJECT_ID}:${dataset}"
    fi
done

echo "Granting dataset-scoped BigQuery WRITER access to ${SA_REFRESH} ..."
# `bq add-iam-policy-binding -d` requires allowlisting on some projects;
# the classic, universally-supported way to scope BigQuery access to one
# dataset is updating its access-control list directly (bq update
# --source), which is exactly what the BigQuery console's "Share
# dataset" UI does under the hood.
TMP_ACCESS_DIR="$(mktemp -d)"
for dataset in "${BQ_DATASET_RAW}" "${BQ_DATASET_STAGING}" "${BQ_DATASET_METRICS}"; do
    ACCESS_FILE="${TMP_ACCESS_DIR}/${dataset}.json"
    bq show --format=prettyjson "${GCP_PROJECT_ID}:${dataset}" > "${ACCESS_FILE}"
    # On Git Bash, a native Windows Python (CLOUDSDK_PYTHON pointing at
    # C:\...\python.exe) can't resolve a POSIX /tmp/... path -- convert
    # it if cygpath is available.
    PY_ACCESS_FILE="${ACCESS_FILE}"
    if command -v cygpath >/dev/null 2>&1; then
        PY_ACCESS_FILE="$(cygpath -w "${ACCESS_FILE}")"
    fi
    "${PYTHON_BIN}" - "${PY_ACCESS_FILE}" "${SA_REFRESH}" <<'PYEOF'
import json, sys
path, sa = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as f:
    d = json.load(f)
if not any(a.get("userByEmail") == sa for a in d["access"]):
    d["access"].append({"role": "WRITER", "userByEmail": sa})
with open(path, "w", encoding="utf-8") as f:
    json.dump({"access": d["access"]}, f)
PYEOF
    bq update --source="${ACCESS_FILE}" "${GCP_PROJECT_ID}:${dataset}"
done
rm -rf "${TMP_ACCESS_DIR}"

# BigQuery job execution (running a query/load job) and Vertex AI
# prediction are project-scoped resources in GCP's IAM model -- there
# is no dataset-level or model-level equivalent to grant instead. This
# is BigQuery/Vertex AI's normal permission structure, not a shortcut.
echo "Granting project-scoped roles that have no finer-grained equivalent ..."
gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
    --member="serviceAccount:${SA_REFRESH}" --role="roles/bigquery.jobUser" \
    --condition=None >/dev/null
gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
    --member="serviceAccount:${SA_REFRESH}" --role="roles/aiplatform.user" \
    --condition=None >/dev/null
gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
    --member="serviceAccount:${SA_CLOUDBUILD}" --role="roles/logging.logWriter" \
    --condition=None >/dev/null

echo "Applying raw table DDL ..."
bq query --use_legacy_sql=false --project_id="${GCP_PROJECT_ID}" < sql/raw/create_raw_tables.sql

echo "Applying staging view DDL ..."
bq query --use_legacy_sql=false --project_id="${GCP_PROJECT_ID}" < sql/staging/create_staging_views.sql

echo "Applying metrics view DDL ..."
for f in sql/metrics/*.sql; do
    echo "  ${f}"
    bq query --use_legacy_sql=false --project_id="${GCP_PROJECT_ID}" < "${f}"
done

echo "Applying Artifact Registry cleanup policy (keep 3 most recent versions, delete untagged, delete anything older than 14d) ..."
for repo in "commerce-decision-app" "commerce-lab-refresh"; do
    gcloud artifacts repositories set-cleanup-policies "${repo}" \
        --project="${GCP_PROJECT_ID}" --location="${GCP_REGION}" \
        --policy="$(dirname "$0")/artifact_cleanup_policy.json" \
        --no-dry-run >/dev/null
done

echo "Provisioning complete."
