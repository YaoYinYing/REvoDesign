# Build, package, test, and clean
PROJECT=REvoDesign
TESTDIR=tmp-test-dir-with-unique-name
PYTEST_ARGS=--cov-config=../.coveragerc --cov-report=term-missing --cov=$(PROJECT) -v --pyargs
LINT_FILES=$(PROJECT)
CHECK_STYLE=$(PROJECT) tests
CHECK_STYLE_LAZY=--extend-ignore E501,F401,E227 $(PROJECT) tests
PYREVERSE_DIR=image/svg
PYREVERSE_ARGS=../$(PROJECT)

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

setup-ubuntu:
	sudo apt install -y libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-xinerama0 libxcb-xfixes0 x11-utils
	/sbin/start-stop-daemon --start --quiet --pidfile /tmp/custom_xvfb_99.pid --make-pidfile --background --exec /usr/bin/Xvfb -- :99 -screen 0 1920x1200x24 -ac +extension GLX

setup-display:
	Xvfb :99 -screen 0 1280x1024x24 &
	fluxbox &
	sleep 3

# only for unittest on runner or local machine.
install:
	python -m pip install ".[full,unittest]" -U

reinstall:
	make clean
	make black;rm -r /Users/yyy/.REvoDesign/config/; pip install . -U


prepare-test:
	python -m pip install pytest pytest-cov coverage -q

test:
	# Run a tmp folder to make sure the tests are run on the installed version
	mkdir -p $(TESTDIR)
	cd $(TESTDIR); python -m pytest $(PYTEST_ARGS) ../tests/UnitTests.py

memray:
	# Run a tmp folder to make sure the tests are run on the installed version
	mkdir -p $(TESTDIR)
	cd $(TESTDIR);memray run --native -m pytest  ../tests/QtTests.py;

memray-live:
	# Run a tmp folder to make sure the tests are run on the installed version
	mkdir -p $(TESTDIR)
	cd $(TESTDIR);memray run --live -m pytest  ../tests/QtTests.py;

ui-test:
	# Run a tmp folder to make sure the tests are run on the installed version
	mkdir -p $(TESTDIR)
	cd $(TESTDIR); python -m pytest $(PYTEST_ARGS) ../tests/QtTests.py;

all-test:
	# Run a tmp folder to make sure the tests are run on the installed version
	mkdir -p $(TESTDIR)
	cd $(TESTDIR); python -m pytest $(PYTEST_ARGS) ../tests/QtTests.py ../tests/UnitTests.py;
	cp $(TESTDIR)/.coverage* .
	rm -r $(TESTDIR)

format: license-update black

check: black-check flake8-lazy lint

tag:
	bash tools/release_tag.sh

black:
	black $(CHECK_STYLE)

reverse:
	mkdir -p $(PYREVERSE_DIR)
	cd $(PYREVERSE_DIR); pyreverse $(PROJECT); dot -Tsvg classes.dot > classes.svg; dot -Tsvg packages.dot > packages.svg
	

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
	find . -name "*.pdb" -exec rm -v {} \;
	find . -name "*.fasta" -exec rm -v {} \;
	find . -name "*.cif" -exec rm -v {} \;
	rm -rvf build dist MANIFEST *.egg-info __pycache__ .coverage .cache .pytest_cache $(PROJECT)/_version.py
	rm -rvf $(TESTDIR) dask-worker-space
	rm -rvf logs surface_residue_records downloaded mutations_design_profile pockets temperal_pdb expanded_compressed_files analysis screenshots
	rm -rvf tests/logs tests/surface_residue_records tests/mutations_design_profile tests/pockets tests/temperal_pdb tests/analysis/