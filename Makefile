# The @ makes sure that the command itself isn't echoed in the terminal
help:
	@echo "---------------HELP-----------------"
	@echo "To clean the workspace type 'make clean'"
	@echo "To install the projects dependencies type 'make install'"
	@echo "To install the projects dependencies for development type 'make install-dev'"
	@echo "To run the project type 'make run'"
	@echo "To test the project type 'make test'"
	@echo "To assess test coverage type 'make coverage'"
	@echo "To generate the requirements.txt file for pip type 'make update-requirements-file'"
	@echo "To sync current changes to a blitz for testing, type 'make sync-to-blitz'.\n   ℹ️  Adjust connection values in scripts/push_to_blitz.sh"
	@echo "To generate the client libraries type 'make generate-client-libs'"
	@echo "To build the Docker regtest image type 'make docker-regtest-image'.\n   ℹ️  The image will be available to docker as 'blitz_api'"
	@echo "------------------------------------"

clean:
	echo "Removing htmlcov folder and .coverage file"
	rm -rf htmlcov .coverage
	poetry run python -m pyclean .

install:
	poetry run python -m pip install -r requirements.txt

install-dev:
	poetry install && poetry run pre-commit install

run:
	poetry run python -m uvicorn app.main:app --reload

test:
	poetry run python -m pytest

coverage:
	poetry run python -m coverage run --source=. -m pytest
	poetry run python -m coverage html

update-requirements-file:
	poetry update && poetry export --without dev --output requirements.txt

sync-to-blitz:
	bash scripts/sync_to_blitz.sh

pre-commit:
	poetry run pre-commit run --all-files

generate-client-libs:
	poetry run python gen_client_libs.py

docker-regtest-image:
	docker build -f Dockerfile.regtest -t blitz_api .

remote-debugging-help:
	bash scripts/remote_debugging.sh help

enable-remote-debugging:
	bash scripts/remote_debugging.sh enable

disable-remote-debugging:
	bash scripts/remote_debugging.sh disable
