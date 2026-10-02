.PHONY: install run test lint docs

install:
	pip install -r requirements-dev.txt

run:
	streamlit run app.py

test:
	python3 tests/test_engine.py

lint:
	flake8 .

docs:
	python3 docs/make_architecture.py
