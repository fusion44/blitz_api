CELERY_APP ?= app.celery_app
CELERY_BROKER_URL ?= redis://localhost:6379/0
TASK_NAME ?= app.apps.tasks.update_app_state_task
TASK_ARGS ?= '[]'
TASK_KWARGS ?= '{}'

.PHONY: celery-list-tasks celery-run-task

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
	@echo "To sync current changes to a blitz for testing, type 'make sync-to-blitz'.\n   ℹ️  Adjust connection values in scripts/push_to_blitz.sh"
	@echo "To generate the client libraries type 'make generate-client-libs'"
	@echo "To build the Docker regtest image type 'make docker-regtest-image'.\n   ℹ️  The image will be available to docker as 'blitz_api'"
	@echo "To list all celery tasks type 'make celery-list-tasks'"
	@echo "To manually trigger a celery task type 'make celery-run-task [TASK_NAME TASK_ARGS TASK_KWARGS]'"
	@echo "------------------------------------"

clean:
	echo "Removing htmlcov folder and .coverage file"
	rm -rf htmlcov .coverage
	uv run python -m pyclean .

install:
	uv pip install -r requirements.txt

install-dev:
	# This command reads pyproject.toml and installs all dependencies (main + dev)
	uv sync

run:
	uv run python -m uvicorn app.main:app --reload

test:
	uv run python -m pytest

coverage:
	uv run python -m coverage run --source=. -m pytest
	uv run python -m coverage html

update-requirements-file:
	uv pip compile --all-extras --output-file requirements.txt pyproject.toml

sync-to-blitz:
	bash scripts/sync_to_blitz.sh

generate-client-libs:
	uv run python gen_client_libs.py

docker-regtest-image:
	docker build -f Dockerfile.regtest -t blitz_api .

remote-debugging-help:
	bash scripts/remote_debugging.sh help

enable-remote-debugging:
	bash scripts/remote_debugging.sh enable

disable-remote-debugging:
	bash scripts/remote_debugging.sh disable

celery-list-tasks:
	@echo "Listing registered Celery tasks..."
	@uv run celery -A $(CELERY_APP) inspect registered

celery-run-task:
	@echo "Manually triggering Celery task: $(TASK_NAME)"
	@echo "  Args: $(TASK_ARGS)"
	@echo "  Kwargs: $(TASK_KWARGS)"
	@uv run celery -A $(CELERY_APP) call $(TASK_NAME) --args=$(TASK_ARGS) --kwargs=$(TASK_KWARGS)
