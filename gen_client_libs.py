import importlib
import json
import os
import shutil
from subprocess import PIPE, Popen

from fastapi.openapi.utils import get_openapi

# npm install @openapitools/openapi-generator-cli -g
# sudo apt install default-jre

# For now assume that the clients repository is a sibling to the current working directory.
out_path = os.path.abspath(os.path.join("../", f"blitz_api_client_libraries"))

mod = importlib.import_module(f"app.main")

app = getattr(mod, "app")
version = "v1"

if version:
    for route in app.router.routes:
        if version in route.path:
            app = route.app
            break


def _generate(generator: str):
    p = os.path.abspath(os.path.join(out_path, f"clients/{generator}"))

    print(f"Removing {p}")
    if os.path.exists(p):
        shutil.rmtree(p)

    print(f"Recreating directory {p}")
    os.makedirs(p, exist_ok=True)

    print(f"Generating client files {generator}")

    process = Popen(
        [
            "openapi-generator-cli",
            "generate",
            "-i",
            "openapi.json",
            "-g",
            generator,
            "-o",
            p,
        ],
        stdout=PIPE,
        stderr=PIPE,
    )
    _, stderr = process.communicate()
    if stderr:
        print(stderr)


def main():
    # Gets the OpenAPI specs.
    specs = get_openapi(
        title=app.title if app.title else None,
        version=app.version if app.version else None,
        openapi_version=app.openapi_version if app.openapi_version else None,
        description=app.description if app.description else None,
        routes=app.routes if app.routes else None,
    )

    with open(f"openapi.json", "w") as f:
        json.dump(specs, f, indent=2)

    _generate("dart-dio")
    _generate("dart")
    _generate("go")
    _generate("javascript")
    _generate("kotlin")
    _generate("python")
    _generate("typescript-axios")
    _generate("typescript-fetch")


if __name__ == "__main__":
    main()
