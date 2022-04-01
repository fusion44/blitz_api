# blitz_api

[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)

## Configuration

Create a `.env` file with your `bitcoind` and `lnd` configuration. See the `.env_sample` file for all configuration options.

### Dependencies

- [Python in version 3.7](https://www.python.org/downloads/)
- [Redis](https://redis.io)
- [Polar](https://github.com/jamaljsr/polar)
  If you need an easy option to run a simple bitcoind & lnd client

## Installation

:warning: To setup a development environment for BlitzAPI skip to the [Development](#Development) section.

### Linux / macOS

```sh
make install
```

or

```sh
python -m pip install -r requirements.txt
```

### Windows

```sh
py -m pip install -r requirements.txt
```

## Run the application

### Linux / macOS

```sh
make run
```

or

```sh
python -m uvicorn app.main:app --reload
```

### Windows

```sh
py -m uvicorn app.main:app --reload
```

## Development

It is recommended to have [python-poetry installed](<(https://python-poetry.org/docs/master/#installation)>).

From within the `blitz_api` folder [open a poetry shell](https://python-poetry.org/docs/master/cli/#shell) via:

```sh
poetry shell
```

(To exit the poetry shell use: `exit`)

### Installation

```
poetry install
pre-commit install
```

or

```sh
make install_dev
```

If python dependencies have been changed it's necessary to freeze all requirements to requirements.txt:

```sh
poetry export -f requirements.txt --output requirements.txt
```

> :information_source: This will skip all dev dependencies by default.\
> This step is required to avoid having to install poetry for final deployment.

### Testing

Make sure to include tests for important pieces of submitted code.

#### Run the tests with pytest

```sh
make test
```

#### Run tests and generate a coverage

```sh
make coverage
```

This will run tests and generate a coverage html file in this folder: `./htmlcov`

### Before you commit

This project uses [pre-commit](https://pre-commit.com) to keep the source code structured. Please make sure to run either `make pre_commit` or `pre-commit run --all-files`. The CI pipeline will reject pull requests that fail this step. This step helps to ensures that the source code is formatted consistently and pull requests are as tidy as possible.

### [Swagger](https://swagger.io)

Once the API is running swagger docs can be found here:

```
http://127.0.0.1:8000/latest/docs
```

## Useful cURL commands to test the API

```sh
curl -N http://127.0.0.1:8000/v1/sse/subscribe
```

```sh
curl -N http://127.0.0.1:8000/v1/bitcoin/getblockchaininfo
```

```sh
curl -X POST -N http://127.0.0.1:8000/v1/setup/type/1
```

```sh
curl --header "Content-Type: application/json" \
  --request POST \
  --data '{"password":"12345678"}' \
  http://127.0.0.1:8000/system/login
```

### Acknowledgements

Integrated Libraries:

- [sse-starlette](https://github.com/sysid/sse-starlette)
- [fastapi-versioning](https://github.com/DeanWay/fastapi-versioning)
