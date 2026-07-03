# Blitz API

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A management backend for bitcoin and lightning node operators written in Python with FastAPI.

## Beta Disclaimer
This software is still considered BETA and may contain bugs. Don't expose it to the open internet or use with a lot of funds.

- [Blitz API](#blitz-api)
  - [Beta Disclaimer](#beta-disclaimer)
  - [Configuration](#configuration)
    - [Dependencies](#dependencies)
  - [Installation](#installation)
    - [Linux / macOS](#linux--macos)
    - [Windows](#windows)
  - [Run the application](#run-the-application)
    - [Linux / macOS](#linux--macos-1)
    - [Windows](#windows-1)
  - [Development](#development)
      - [Using the nix package manager](#using-the-nix-package-manager)
    - [Installation](#installation-1)
    - [Sync changes to a RaspiBlitz](#sync-changes-to-a-raspiblitz)
    - [Debugging code running on a remote machine via VSCode](#debugging-code-running-on-a-remote-machine-via-vscode)
      - [Prepare local machine](#prepare-local-machine)
      - [Prepare the RaspiBlitz](#prepare-the-raspiblitz)
    - [Unit / Integration testing](#unit--integration-testing)
      - [Run the tests with pytest](#run-the-tests-with-pytest)
      - [Run tests and generate a coverage](#run-tests-and-generate-a-coverage)
    - [Client libraries](#client-libraries)
      - [Generating client libraries](#generating-client-libraries)
    - [Before you commit](#before-you-commit)
    - [Swagger / OpenAPI](#swagger--openapi)
    - [Useful cURL commands to test the API](#useful-curl-commands-to-test-the-api)
  - [Acknowledgements](#acknowledgements)

## Configuration

Create a `.env` file with your `bitcoind` and `lnd` configuration. See the `.env_sample` file for all configuration options.

The `.env` file is expected to be at the project root folder by default.
To use a custom path, set the `BAPI_ENV_PATH` env variable to the `.env` file path.

### Dependencies

- [Python](https://www.python.org/downloads/) in version 3.11 or 3.12
- [uv](https://docs.astral.sh/uv/) for dependency management
- [Redis](https://redis.io)
- [Polar](https://github.com/jamaljsr/polar)
  If you need an easy option to run a simple bitcoind & lnd client

## Installation

⚠️ To setup a development environment for BlitzAPI skip to the [Development](#Development) section.

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

Dependencies are managed with [uv](https://docs.astral.sh/uv/). Install it by following the [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/).

`uv` creates and manages a local `.venv` for you. Prefix commands with `uv run` (e.g. `uv run pytest`) to run them inside the project environment, or activate the venv manually via `source .venv/bin/activate`.

#### Using the nix package manager
Blitz API provides a [Nix](https://github.com/NixOS/nix) Flake file to create a development environment. Execute `nix develop` (make sure you have flakes enabled) to enter the environment.

In this environment a hidden folder `.venv` is created to install the python dependencies locally. If pyright can't find these dependencies create the following file in the root
folder of the project:
```json
{
  "venvPath": ".",
  "venv": ".venv"
}
```

### Installation

```sh
make install-dev
```

or

```sh
uv sync
```

This reads `pyproject.toml` and installs all dependencies (main + dev) into `.venv`.

If python dependencies have been changed it's necessary to freeze all requirements to requirements.txt:

```sh
make update-requirements-file
```

or

```sh
uv pip compile --all-extras --universal --output-file requirements.txt pyproject.toml
```

> ℹ️ The final deployment installs via pip from `requirements.txt` (see `make install`) to avoid having to install uv on the target machine, so keep this file in sync when dependencies change.

### Sync changes to a RaspiBlitz

Create a file `/script/sync_to_blitz.personal.sh` (will be ignored by github) the SSH connection data to your RaspiBlitz.

localIP="192.168.178.61"
sshPort="22"
passwordA=""

Then you can run always `make sync-to-blitz` to copy your latest code over to your RaspiBlitz. The script automatically restarts the backend API with the new code on your RaspiBlitz and shows you the logs.

To test the backend API then call the SwaggerUI: `http://[LOCALIP]/api/v1/docs` - to call protected endpoints run the `/system/login` endpoint first with HTTP POST body:
```
{
  "password": "[PASSWORDA]"
}
```
and then copy the JWT Auth string returned to `Authorize` in the top section of the SwaggerUI.

*You can also now test the RaspiBlitz WebUI against the API by running it locally on your dev laptop when you configure it to use the backend API of your RaspiBlitz.*

### Debugging code running on a remote machine via VSCode
To debug Python code that is running on another machine, like a RaspiBlitz, follow these steps.

#### Prepare local machine
* run `make install-dev`.
* open the `.vscode/launch.json` file and change the host to your remote machines IP
  * ```json
      "connect": {
        "host": "192.168.1.49",
        "port": 5678
      }
      ```
* open your `.env_sample` file and replace the line `# remote_debugging=false` with `remote_debugging=true`
  <details>
    This is necessary because we're going to synchronize the local source with the remote node. The blitz_api service will be restarted on the remote node. Any changes to the `.env' file will be overwritten by the setup script on the Blitz. This script will use the `.env_sample` file as a base and fill it with data. This way we can trick the Blitz into enabling this setting every time we change something without the Blitz explicitly supporting it.
  </details>
* make sure you follow the steps in the [Sync changes to a RaspiBlitz](#sync-changes-to-a-raspiblitz) section
* execute `make sync-to-blitz`
* Make sure to chose `Attach` in the RUN AND DEBUG windows of VSCode
* Hit F5 and voila you should be connected to your RaspiBlitz and debug code remotely

#### Prepare the RaspiBlitz
* SSH into the Blitz, and run `sudo -i -u blitzapi`
* `cd blitz_api`
* Finally run `make enable-remote-debugging`


Refer to [this documentation](https://code.visualstudio.com/docs/python/debugging#_debugging-by-attaching-over-a-network-connection) to learn how to setup VSCode correctly.

### Unit / Integration testing

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

### Client libraries

> ℹ️ The client libraries live in an extra repository:
https://github.com/fusion44/blitz_api_client_libraries

#### Generating client libraries
Install [OpenAPI Generator](https://openapi-generator.tech) and Java:


```sh
npm install @openapitools/openapi-generator-cli -g
sudo apt install default-jre
```


Clone https://github.com/fusion44/blitz_api_client_libraries next to the blitz_api folder.

```sh
make generate-client-libs
```
> ⚠️ The first run requires `sudo` as it must download a Java .jar file to the system npm package folder.

### [Swagger / OpenAPI](https://swagger.io)

Once the API is running swagger docs can be found here:

```
http://127.0.0.1:8000/latest/docs
```

### Useful cURL commands to test the API

```sh
curl -N -H "Authorization: Bearer JWT_TOKEN_HERE" http://127.0.0.1:8000/sse/subscribe
```

```sh
curl -N -H "Authorization: Bearer JWT_TOKEN_HERE" http://127.0.0.1:8000/v1/bitcoin/getblockchaininfo
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

## Acknowledgements

Integrated Libraries:

- [sse-starlette](https://github.com/sysid/sse-starlette)
- [fastapi-versioning](https://github.com/DeanWay/fastapi-versioning)
