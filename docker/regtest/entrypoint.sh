#!/bin/sh

echo "LN_BACKEND: $LN_BACKEND"


if [ "$LN_BACKEND" = "cln1" ]; then
  cp /code/.env.cln1 /code/.env
elif [ "$LN_BACKEND" = "cln2" ]; then
  cp /code/.env.cln2 /code/.env
elif [ "$LN_BACKEND" = "lnd1" ]; then
  cp /code/.env.lnd1 /code/.env
elif [ "$LN_BACKEND" = "lnd2" ]; then
  cp /code/.env.lnd2 /code/.env
elif [ "$LN_BACKEND" = "lnd3" ]; then
  cp /code/.env.lnd3 /code/.env
else
  echo "Unknown LN_BACKEND: $LN_BACKEND"
fi

# wait until the nodes are ready
echo "Waiting for node $LN_BACKEND to finish bootstrapping..."
sleep 120

python3 -m uvicorn app.main:app --host 0.0.0.0 --port 80
