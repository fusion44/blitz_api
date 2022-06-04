# Build the Python gRPC files

Build for lightningd v0.11.0.1

```sh
cd ~/dev/lightning/clightning/cln-grpc/proto
poetry shell
pip install grpcio grpcio-tools googleapis-common-protos
git clone https://github.com/googleapis/googleapis.git
python -m grpc_tools.protoc --proto_path=googleapis:. --python_out=. --grpc_python_out=. primitives.proto
python -m grpc_tools.protoc --proto_path=googleapis:. --python_out=. --grpc_python_out=. node.proto
```
