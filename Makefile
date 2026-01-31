.PHONY: install setup test clean run-cli help

help:
	@echo "Congressional Trading Bot - Makefile Commands"
	@echo ""
	@echo "  make install           - Install dependencies"
	@echo "  make setup             - Setup virtual environment and install"
	@echo "  make test              - Run tests"
	@echo "  make clean             - Clean up generated files"
	@echo "  make run-cli           - Run CLI (example: make run-cli ARGS='status')"
	@echo "  make import-sample     - Import sample trade data"
	@echo "  make scrape-demo       - Run scraping demo (latest year)"
	@echo "  make scrape-recent     - Scrape last 3 years of House data"
	@echo "  make scrape-all        - Scrape all available House data"
	@echo "  make available-years   - Check available years for scraping"
	@echo "  make recommendations   - Show trade recommendations"

install:
	pip install -r requirements.txt
	pip install -e .

setup:
	python3 -m venv venv
	@echo "Virtual environment created. Activate with: source venv/bin/activate"
	@echo "Then run: make install"

test:
	pytest tests/ -v --cov=src --cov-report=html

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage .pytest_cache/
	rm -f data/congressional_trades.db

run-cli:
	python -m src.cli.cli $(ARGS)

import-sample:
	python -m src.cli.cli collect trades --csv data/sample_trades.csv

scrape-demo:
	python scrape_example.py

scrape-recent:
	python -m src.cli.cli scrape house --start-year 2021 --end-year 2023

scrape-all:
	python -m src.cli.cli scrape house --start-year 2012

available-years:
	python -m src.cli.cli scrape available-years

recommendations:
	python -m src.cli.cli recommendations

status:
	python -m src.cli.cli status

analyze:
	python -m src.cli.cli analyze $(TICKER)
