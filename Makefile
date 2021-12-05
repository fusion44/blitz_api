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
	@echo "To sync current changes to a blitz for testing, type 'make sync_to_blitz'. Adjust connection values in scripts/push_to_blitz.sh"
	@echo "------------------------------------"

clean:
	echo "Removing htmlcov folder and .coverage file"
	rm -rf htmlcov .coverage
	python -m pyclean .
	
install:
	python -m pip install -r requirements.txt

install_dev:
	poetry shell && poetry install

run:
	python -m uvicorn app.main:app --reload

test: 
	python -m pytest

coverage:
	python -m coverage run --source=. -m pytest
	python -m coverage html

requirements:
	poetry export > requirements.txt

sync_to_blitz:
	bash scripts/sync_to_blitz.sh