# blitz_api

## Configuration

Create a `.env` file with your `bitcoind` and `lnd` configuration. See the `.env_sample` file for all configuration options.  

Please note that you will also need to install [Redis](https://redis.io/).

If you need a easy option to run a simple bitcoind & lnd client, [Polar](https://github.com/jamaljsr/polar) makes that pretty easy.

## Installation

You will need to have [Python in version 3.7](https://www.python.org/downloads/) installed and have the `.env` see [Configuration](#Configuration) configured correctly first.


>:warning: To setup a development environment for BlitzAPI skip to the [Development](#Development) section.


To install the dependencies, run

`make install` or `python -m pip install -r requirements.txt` on Linux / macOS or

`py -m pip install -r requirements.txt` on Windows.

After that, you can run the application with

`make run` or `python -m uvicorn app.main:app --reload` on Linux / macOS or

`py -m uvicorn app.main:app --reload` on Windows.

## Development
For development it is recommended to have python-poetry installed. Install instructions can be found [here](https://python-poetry.org/docs/master/#installation)

From within the blitz_api folder open a shell via `poetry shell`.

Install dependencies with all dev dependencies: `make install_dev` or `poetry install`

If any dependencies have changed it becomes necessary to freeze all requirements to requirements.txt:

`poetry export -f requirements.txt --output requirements.txt`

> :information_source: This will skip all dev dependencies by default.<br> 
> This step is required to avoid having to install poetry for final deployment.

### Testing
Make sure to include test for important pieces of code submitted. 
To run the tests run `make tests` to test with pytest or run `make coverage` to test and generate a coverage html file in a folder called `htmlcov`

## Useful cURL commands to test the API
`curl -N http://127.0.0.1:8000/v1/sse/subscribe`

`curl -N http://127.0.0.1:8000/v1/bitcoin/getblockchaininfo`

`curl -X POST -N http://127.0.0.1:8000/v1/setup/type/1`

```sh
curl --header "Content-Type: application/json" \
  --request POST \
  --data '{"password":"12345678"}' \
  http://127.0.0.1:8000/system/login
```

### Acknowledgements

Integrated Libraries:

* [sse-starlette](https://github.com/sysid/sse-starlette)
* [fastapi-versioning](https://github.com/DeanWay/fastapi-versioning)
