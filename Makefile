# The @ makes sure that the command itself isn't echoed in the terminal
help:
	@echo "---------------HELP-----------------"
	@echo "To clean the workspace type 'make clean'"
	@echo "To install the projects dependencies type 'make install'"
	@echo "To install the projects dependencies for development type 'make install-dev'"
	@echo "To run the project type 'make run'"
	@echo "To test the project type 'make test'"
	@echo "To assess test coverage type 'make coverage'"
	@echo "To generate the requirements.txt file for pip type 'make requirements'"
	@echo "To sync current changes to a blitz for testing, type 'make sync-to-blitz'.\n   ℹ️  Adjust connection values in scripts/push_to_blitz.sh"
	@echo "To generate the client libraries type 'make generate-client-libs'"
	@echo "------------------------------------"

clean:
	echo "Removing htmlcov folder and .coverage file"
	rm -rf htmlcov .coverage
	python -m pyclean .

install:
	python -m pip install -r requirements.txt

install-dev:
	poetry shell && poetry install && pre-commit install

run:
	python -m uvicorn app.main:app --reload

test:
	python -m pytest

coverage:
	python -m coverage run --source=. -m pytest
	python -m coverage html

update-requirements-file:
	poetry update && poetry export --output requirements.txt

sync-to-blitz:
	bash scripts/sync_to_blitz.sh

pre-commit:
	pre-commit run --all-files

generate-client-libs:
	python gen_client_libs.py
