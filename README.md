# blitz_api

## Configuration

Create a `.env` file with your `bitcoind` and `lnd` configuration. See the `.env_sample` file for all configuration options.  

Please note that you will also need to install [Redis](https://redis.io/).

If you need a easy option to run a simple bitcoind & lnd client, [Polar](https://github.com/jamaljsr/polar) makes that pretty easy.

## Installation

You will need to have [Python in version 3.7](https://www.python.org/downloads/) installed and have the `.env` see [Configuration](#Configuration) configured correctly first.


>**NOTE:** To setup a development environment for BlitzAPI skip to the [Development](#Development) section.


To install the dependencies, run

`python -m pip install -r requirements.txt` on Linux / macOS or

`py -m pip install -r requirements.txt` on Windows.

After that, you can run the application with

`python -m uvicorn main:app --reload` on Linux / macOS or

`py -m uvicorn main:app --reload` on Windows.

## Development
For development it is recommended to have python-poetry installed. Install instructions can be found [here](https://python-poetry.org/docs/master/#installation)

Install dependencies with all dev dependencies:

`poetry install`

If any dependencies have changed it becomes necessary to freeze all requirements to requirements.txt:

`poetry export -f requirements.txt --output requirements.txt`

> **Note**: This will skip all dev dependencies by default.<br> 
> This step is required to avoid having to install poetry for final deployment.


