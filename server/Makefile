.PHONY: test test-all test-cov test-docker-compat test-docker-full-stack

PYTEST ?= python -m pytest
COV_REPORT ?= term-missing

test:
	$(PYTEST) tests/ --ignore=tests/test_docker.py --ignore=tests/test_runner_docker_compat.py -v

test-all:
	$(PYTEST) tests/ -v

test-cov:
	$(PYTEST) tests/ --ignore=tests/test_docker.py --ignore=tests/test_runner_docker_compat.py -v \
		--cov-config=.coveragerc --cov=revocompute \
		--cov-report=$(COV_REPORT)

test-docker-compat:
	$(PYTEST) tests/test_runner_docker_compat.py -v

test-docker-full-stack:
	bash tests/run_full_stack_test.sh
