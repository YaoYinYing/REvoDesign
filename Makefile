# Build, package, test, and clean
PROJECT=REvoDesign
TESTDIR=tmp-test-dir-with-unique-name
PYTEST_ARGS=--cov-config=../.coveragerc --cov-report=term-missing --cov=$(PROJECT) -v --pyargs
LINT_FILES=$(PROJECT)
CHECK_STYLE=$(PROJECT) tests
CHECK_STYLE_LAZY=--extend-ignore E501,F401,E227 $(PROJECT) tests

help:
	@echo "Commands:"
	@echo ""
	@echo "  install   install in editable mode"
	@echo "  test      run the test suite (including doctests) and report coverage"
	@echo "  format    automatically format the code"
	@echo "  check     run code style and quality checks"
	@echo "  lint      run pylint for a deeper (and slower) quality check"
	@echo "  build     build source and wheel distributions"
	@echo "  clean     clean up build and generated files"
	@echo ""

build:
	python -m build .

install:
	python -m pip install ".[full]" -U

test:
	# Run a tmp folder to make sure the tests are run on the installed version
	python -m pip install pytest-cov -q
	mkdir -p $(TESTDIR)
	cd $(TESTDIR); pytest $(PYTEST_ARGS) ../tests/UnitTests.py
	cp $(TESTDIR)/.coverage* .
	rm -r $(TESTDIR)

format: license-update black

check: black-check flake8-lazy lint

black:
	black $(CHECK_STYLE)

black-check:
	black --check $(CHECK_STYLE)

license-update:
	python tools/license_notice.py

license-check:
	python tools/license_notice.py --check

flake8:
	python -m pip install flake8
	flake8 $(CHECK_STYLE)

flake8-lazy:
	python -m pip install flake8
	flake8 $(CHECK_STYLE_LAZY)

lint:
	python -m pip install pylint
	pylint --jobs=0 $(LINT_FILES)

clean:
	find . -name "*.pyc" -exec rm -v {} \;
	find . -name "*.orig" -exec rm -v {} \;
	find . -name ".coverage.*" -exec rm -v {} \;
	find . -name ".DS_Store" -exec rm -v {} \;
	rm -rvf build dist MANIFEST *.egg-info __pycache__ .coverage .cache .pytest_cache $(PROJECT)/_version.py
	rm -rvf $(TESTDIR) dask-worker-space