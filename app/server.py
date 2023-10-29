import uvicorn

import click  # isort:skip


@click.command()
@click.option("--port", default="5000", help="Port to run Blitz API on")
@click.option("--host", default="127.0.0.1", help="Host to run Blitz API on")
def main(port, host):
    """Launched with `poetry run api` at root level"""
    uvicorn.run("app.main:app", port=port, host=host)


if __name__ == "__main__":
    main()
