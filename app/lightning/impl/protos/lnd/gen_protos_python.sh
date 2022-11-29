#!/bin/bash

# clone lnd repo
# cd into lnd/lnrpc
# git clone https://github.com/googleapis/googleapis.git

set -e

# path to LND lnrpc directory
LND_RPC_DIR="."

function generate() {
  echo "Generating root gRPC protos"

  PROTOS=$(find ${LND_RPC_DIR} -not -path '*googleapis*' -name "*.proto")

  for file in $PROTOS; do
    DIRECTORY=$(dirname "${file}")

    echo "Generating protos from ${file}, into ${DIRECTORY}"
  
    # Generate the protos.
    python -m grpc_tools.protoc --proto_path=googleapis:. --python_out=. --grpc_python_out=. "${file}"
  done
}

# Compile the lnrpc package.
generate
