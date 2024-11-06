#!/bin/bash

# Accept env variable for PORT



MESOP_PORT=${MESOP_PORT:-8888}

# Default number of workers if not set
WORKERS=${WORKERS:-1}

# Run uvicorn server
uvicorn poi_scraper.deployment.main_:app --host 0.0.0.0 --port $FASTAPI_PORT > /dev/stdout 2>&1 &

# Run gunicorn server
gunicorn --workers=$WORKERS poi_scraper.deployment.main:app --bind 0.0.0.0:$MESOP_PORT
