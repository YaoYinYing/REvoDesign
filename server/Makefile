.PHONY: test test-all test-cov

test:
	python -m pytest tests/ --ignore=tests/test_docker.py -v

test-all:
	python -m pytest tests/ -v

test-cov:
	python -m pytest tests/ --ignore=tests/test_docker.py -v \
		--cov-config=../.coveragerc-server --cov=pssm_gremlin_server \
		--cov-report=term-missing
