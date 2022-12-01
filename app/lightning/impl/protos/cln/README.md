# Build the Python gRPC files

Build for lightningd tagged v0.12.1

```sh
cd ~/dev/lightning/clightning/cln-grpc/proto
poetry shell
pip install grpcio grpcio-tools googleapis-common-protos
python -m grpc_tools.protoc --proto_path=. --python_out=. --grpc_python_out=. primitives.proto
python -m grpc_tools.protoc --proto_path=. --python_out=. --grpc_python_out=. node.proto
cp node_pb2.py node_pb2_grpc.py primitives_pb2.py primitives_pb2_grpc.py ~/dev/blitz/api/refactor_system/app/lightning/impl/protos/cln/
```
