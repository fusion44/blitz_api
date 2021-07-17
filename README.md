# blitz_api

## Configuration

Update the `.env` file with your `bitcoind` and `lnd` configuration.

Please note that you will also need to install [Redis](https://redis.io/).

If you need a easy option to run a simple bitcoind & lnd client, [Polar](https://github.com/jamaljsr/polar) makes that pretty easy.

## Installation

You will need to have [Python in version 3](https://www.python.org/downloads/) installed and have the `.env` see [Configuration](#Configuration) configured correctly first.

To install the dependencies, run

`python -m pip install -r requirements.txt` on Linux / macOS or

`py -m pip install -r requirements.txt` on Windows.

After that, you can run the application with

`python -m uvicorn main:app --reload` on Linux / macOS or

`py -m uvicorn main:app --reload` on Windows.
