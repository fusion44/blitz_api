#!/bin/sh

echo "Entrypoint: Starting Blitz Api..."
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 80
