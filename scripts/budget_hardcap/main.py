"""Pub/Sub-triggered Cloud Function: disables billing on this project the
moment the linked budget's spend reaches 100% of its threshold.

This is a hard cap, not a notification -- see PROGRESS.md "예산 하드캡"
decision entry for why disabling billing (project-wide) is the only way to
guarantee no further charges, and why that necessarily takes every billable
resource in the project offline (including the public Cloud Run app) until
the owner manually re-links billing.

Trigger: Pub/Sub topic that the budget's notificationsRule.pubsubTopic
publishes to on every threshold crossing (50/90/100%). The message payload
is documented at
https://cloud.google.com/billing/docs/how-to/budgets-programmatic-notifications

Talks to the Cloud Billing REST API directly with google-auth + requests
instead of the google-cloud-billing client library -- that library pulls in
a heavy grpc/cryptography dependency chain that failed to build in the
Cloud Functions buildpack image, and this function only ever needs two
simple REST calls.
"""

import base64
import json
import logging
import os

import google.auth
import google.auth.transport.requests

PROJECT_ID = os.environ["GCP_PROJECT_ID"]
BILLING_INFO_URL = f"https://cloudbilling.googleapis.com/v1/projects/{PROJECT_ID}/billingInfo"

logging.basicConfig(level=logging.INFO)

_credentials, _ = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-billing"]
)
_session = google.auth.transport.requests.AuthorizedSession(_credentials)


def stop_billing(event, context):
    """`event`/`context` (not a single CloudEvent) because this function was
    deployed with `gcloud functions deploy --trigger-topic`, which wires a
    legacy "background function" signature even on gen2 -- functions
    framework calls it with two positional args."""
    data = json.loads(base64.b64decode(event["data"]))

    cost_amount = data.get("costAmount", 0)
    budget_amount = data.get("budgetAmount", 0)
    display_name = data.get("budgetDisplayName", "<unknown>")

    logging.info(
        "Budget alert: %s cost=%s budget=%s",
        display_name,
        cost_amount,
        budget_amount,
    )

    if budget_amount <= 0 or cost_amount < budget_amount:
        logging.info("Under budget, no action.")
        return

    info = _session.get(BILLING_INFO_URL)
    info.raise_for_status()
    if not info.json().get("billingEnabled", False):
        logging.info("Billing already disabled on %s, no action.", PROJECT_ID)
        return

    logging.warning(
        "Spend %s reached/exceeded budget %s -- disabling billing on %s",
        cost_amount,
        budget_amount,
        PROJECT_ID,
    )
    resp = _session.put(BILLING_INFO_URL, json={"billingAccountName": ""})
    resp.raise_for_status()
    logging.warning(
        "Billing disabled on %s. All billable resources will stop serving "
        "until an owner manually re-links a billing account in the console.",
        PROJECT_ID,
    )
