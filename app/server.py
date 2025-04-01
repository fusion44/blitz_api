import uvicorn

from app.api.config import config

import click  # isort:skip


@click.command()
@click.option("--port", default="5000", help="Port to run Blitz API on")
@click.option("--host", default="127.0.0.1", help="Host to run Blitz API on")
@click.option(
    "--root_path",
    default=None,
    help="Set the ASGI 'root_path' for applications submounted below a given URL path.",
)
def main(port, host, root_path):
    """Launched with `poetry run api` at root level"""

    p = ""
    if root_path is not None and root_path != "":
        p = root_path
    else:
        p = str(config("BAPI_ROOT_PATH", default=""))

    if p == "/":
        root_path = ""

    print(f"launching with {host}:{port}{p}")
    uvicorn.run("app.main:app", port=port, host=host, root_path=p)


if __name__ == "__main__":
    main()
