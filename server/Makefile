.PHONY: test test-all test-cov

PYTEST ?= python -m pytest
COV_REPORT ?= term-missing

test:
	$(PYTEST) tests/ --ignore=tests/test_docker.py -v

test-all:
	$(PYTEST) tests/ -v

test-cov:
	$(PYTEST) tests/ --ignore=tests/test_docker.py -v \
		--cov-config=.coveragerc --cov=pssm_gremlin_server \
		--cov-report=$(COV_REPORT)
