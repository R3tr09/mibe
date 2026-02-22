.PHONY: all install test test-cov lint format check clean run help

PYTHON := python3
UV := uv

all: install check

help:
	@echo "Available targets:"
	@echo "  install    - Install dependencies using uv"
	@echo "  test       - Run tests"
	@echo "  test-cov   - Run tests with coverage"
	@echo "  lint       - Run ruff linter"
	@echo "  format     - Format code with ruff"
	@echo "  check      - Run lint and type checks"
	@echo "  clean      - Clean cache files"
	@echo "  run        - Run the main application"
	@echo "  login      - Test login with miservice"
	@echo "  monitor    - Start monitoring"

install:
	$(UV) sync

test:
	$(UV) run pytest -v

test-cov:
	$(UV) run pytest -v --cov=mibe --cov-report=term-missing --cov-report=html

lint:
	$(UV) run ruff check .
	$(UV) run ruff check . --select I

format:
	$(UV) run ruff format .
	$(UV) run ruff check . --select I --fix

check: lint test

clean:
	rm -rf __pycache__ .pytest_cache .coverage htmlcov .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete

run:
	$(UV) run python main.py

login:
	$(UV) run python mibe.py login

monitor:
	$(UV) run python mibe.py monitor
