#!/bin/sh


if [ "$LN_BACKEND" = "cln-1" ]; then
  cp /code/.env.cln1 /code/.env
elif [ "$LN_BACKEND" = "cln-2" ]; then
  cp /code/.env.cln2 /code/.env
elif [ "$LN_BACKEND" = "lnd-1" ]; then
  cp /code/.env.lnd1 /code/.env
elif [ "$LN_BACKEND" = "lnd-2" ]; then
  cp /code/.env.lnd2 /code/.env
elif [ "$LN_BACKEND" = "lnd-3" ]; then
  cp /code/.env.lnd3 /code/.env
else
  echo "Unknown LN_BACKEND: $LN_BACKEND"
fi

# wait until the nodes are ready
sleep 60

python3 -m uvicorn app.main:app --host 0.0.0.0 --port 80
