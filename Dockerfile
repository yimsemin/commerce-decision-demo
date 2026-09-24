# Executive Decision App -- Cloud Run container.
# Reads the snapshot from GCS at runtime (SNAPSHOT_SOURCE env var);
# never queries BigQuery or Gemini directly on page load.
FROM python:3.14-slim

WORKDIR /app

# Only the app's own core dependencies (pandas/numpy/streamlit/
# google-cloud-storage) go into this image -- not the full dev/pipeline
# requirements.txt (pytest, google-cloud-bigquery), which the app never
# imports and the serving container doesn't need.
COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir .

ENV STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Cloud Run sets $PORT; default to 8080 for local `docker run`.
ENV PORT=8080
EXPOSE 8080

CMD streamlit run src/commerce_lab/app/main.py --server.port=${PORT}
