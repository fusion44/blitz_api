#!/bin/sh


if [ "$LN_BACKEND" = "cln-1" ]; then
  cp /code/.env.cln1 /code/.env
else
  cp /code/.env.lnd1 /code/.env
fi

# wait until the nodes are ready
sleep 60

python3 -m uvicorn app.main:app --host 0.0.0.0 --port 80
