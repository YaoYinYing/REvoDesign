# Build, package, test, and clean
PROJECT=REvoDesign
TESTDIR=tmp-test-dir-with-unique-name
PYTEST_ARGS=--cov-config=../.coveragerc --cov-report=term-missing --cov=$(PROJECT) -v --pyargs --durations=0
PYTEST_CASES_PATH=../REvoDesign/tests/cases/
LINT_FILES=$(PROJECT)
CHECK_STYLE=$(PROJECT) tests 
BLACK_STYLE=-l 79 -t py39 -t py310 -t py311
BLACK_EXCLUDES_EXTEND=--extend-exclude '\.ui|\.svg|\.yaml|\.md|\.pyc|\.ico|\.png' 
CHECK_STYLE_LAZY=--extend-ignore E501,F401,E227 $(PROJECT) tests

PYREVERSE_CLASS_OPT=-ASmy --colorized
PYREVERSE_DIR=image/svg
PYREVERSE_OPTS=--colorized --no-standalone --only-classnames --module-names n
PYREVERSE_IGNORE=--ignore Ui_REvoDesign.py,UnitTests.py,QtTests.py,TestData.py,QtTestWorker.py,SessionMerger.py,client_tools.py,customized_widgets.py,mutant_tools.py,pymol_utils.py,system_tools.py,utils.py,exceptions.py,warnings.py
PYREVERSE_DOT_OPTS=-Ln10 


MACOS_PYMOL_BIN_PATH=/Applications/PyMOL.app/Contents/bin/

help:
	@echo "Commands:"
	@echo ""
	@echo "  help                   print this message and exit"
	@echo "  build                  build source and wheel distributions"
	@echo "  setup-ubuntu           Setup ubuntu display for GitHub Actions"
	@echo "  setup-display          Setup ubuntu display for CircleCI"
	@echo "  install                install from pip "
	@echo "  install-no-dept        install from pip, no dependencies"
	@echo "  install-pytorch-cpu    install torch-cpu for ci runner image"
	@echo "  reinstall              reinstall after code changes"
	@echo "  translate              translate UI"
	@echo "  prepare-test           run pip to install pytest-related packages"
	@echo "  test                   run the UnitTest suite"
	@echo "  ui-test                run the QtTest suite"
	@echo "  ui-test-pymol          run the QtTest suite with PyMOL GUI integration."
	@echo "  all-test               run all tests"
	@echo "  macos-rosetta-test     run UI tests versus PyMOL incentive installation (MacOS Application)"
	@echo "  pymol-test             run PyMOL script tests"
	@echo "  memray                 memoray profile for leakage, saved as html file"
	@echo "  memray-live            memoray profile for leakage in live mode"
	@echo "  format                 automatically format the code"
	@echo "  check                  run code style and quality checks"
	@echo "  tag                    pin a new tag from package version to github tag"
	@echo "  black                  black format for all python files"
	@echo "  reverse                run pyreverse for package and methods and create SVGs"
	@echo "  black-check            "
	@echo "  license-update         license updates for all files"
	@echo "  license-check          check license for all files"
	@echo "  flake8                 "
	@echo "  flake8-lazy            "
	@echo "  lint                   run pylint for a deeper (and slower) quality check"
	@echo "  clean                  clean up build and generated files" 
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
	python -m pip install ".[full,unittest]" -U --no-cache-dir
	pip install bibtexparser --pre -U

# only for unittest on ci runner or local machine that already have all depencies installed.
install-no-dept:
	python -m pip install . --no-dependencies --no-cache-dir
	pip install bibtexparser --pre -U

# ci docker image, before make install
install-pytorch-cpu:
	python -m pip install 'torch>2.0.1+cpu' 'torchvision>0.16.0+cpu' 'torchaudio>2.0.1+cpu' -i https://download.pytorch.org/whl/cpu --no-cache-dir

# local dev
reinstall:
	make clean
	make black;rm -r /Users/yyy/.REvoDesign/config/; pip install . -U

# update translation
translate:
	# recompile ui to py
	pyuic5 REvoDesign/UI/REvoDesign.ui -o REvoDesign/UI/Ui_REvoDesign.py
	# update translation file
	#lupdate  REvoDesign/UI/REvoDesign.ui -ts REvoDesign/UI/language/eng-eng.ts
	lupdate  REvoDesign/UI/REvoDesign.ui -ts REvoDesign/UI/language/eng-chs.ts

	# release translation file to binarys
	cd REvoDesign/UI/;lrelease liguist.pro

prepare-test:
	python -m pip install pytest pytest-cov pytest-order coverage -q --no-cache-dir  

# unit test
test:
	# Run a tmp folder to make sure the tests are run on the installed version
	mkdir -p $(TESTDIR)
	cd $(TESTDIR); python -m pytest -x $(PYTEST_ARGS) $(PYTEST_CASES_PATH)/UnitTests.py

# ui test
ui-test:
	# Run a tmp folder to make sure the tests are run on the installed version
	mkdir -p $(TESTDIR)
	cd $(TESTDIR); python -m pytest -x $(PYTEST_ARGS) $(PYTEST_CASES_PATH)/QtTests.py;

# ui test with pymol
# see https://github.com/schrodinger/pymol-open-source/pull/106/files#diff-5c3fa597431eda03ac3339ae6bf7f05e1a50d6fc7333679ec38e21b337cb6721R57
ui-test-pymol:
	# Run a tmp folder to make sure the tests are run on the installed version
	mkdir -p $(TESTDIR)
	cd $(TESTDIR); pymol -ckqy /Users/yyy/miniconda_py39_arm64/lib/python3.10/site-packages/REvoDesign/tests/cases/QtTests.py;

# all test
all-test:
	# Run a tmp folder to make sure the tests are run on the installed version
	mkdir -p $(TESTDIR)
	# https://stackoverflow.com/questions/36804181/long-running-py-test-stop-at-first-failure
	cd $(TESTDIR); python -m pytest -x $(PYTEST_ARGS) $(PYTEST_CASES_PATH)/QtTests.py $(PYTEST_CASES_PATH)/UnitTests.py
	cp $(TESTDIR)/.coverage* .

macos-rosetta-test:
	$(MACOS_PYMOL_BIN_PATH)/python -m pip install ".[unittest]" -U --no-cache-dir
	# Run a tmp folder to make sure the tests are run on the installed version
	mkdir -p $(TESTDIR)
	# https://stackoverflow.com/questions/36804181/long-running-py-test-stop-at-first-failure
	$(MACOS_PYMOL_BIN_PATH)/python -m pip install pytest pytest-cov coverage psutil -q --no-cache-dir 
	$(MACOS_PYMOL_BIN_PATH)/python -m pip install bibtexparser --pre -U
	cd $(TESTDIR); $(MACOS_PYMOL_BIN_PATH)/python -m pytest -x $(PYTEST_ARGS) $(PYTEST_CASES_PATH)/QtTests.py -k 'not mpnn'


pymol-test:
	# Run a tmp folder to make sure the tests are run on the installed version
	mkdir -p $(TESTDIR)
	cd $(TESTDIR); if command -v pymol;then pymol ../tests/PyMOLTests.pml; else PyMOL.exe ../tests/PyMOLTests.pml;fi 
	
memray:
	# Run a tmp folder to make sure the tests are run on the installed version
	mkdir -p $(TESTDIR)
	cd $(TESTDIR);PYTHONMALLOC=malloc memray run --native -m pytest  $(PYTEST_CASES_PATH)/QtTests.py;  memray flamegraph --leak --split-threads --temporal `ls memray-pytest.*.bin`  

fake:
	cat 

memray-live:
	# Run a tmp folder to make sure the tests are run on the installed version
	mkdir -p $(TESTDIR)
	cd $(TESTDIR);memray run --live -m pytest  $(PYTEST_CASES_PATH)/QtTests.py;

format: license-update black

check: black-check flake8-lazy lint

tag:
	bash tools/release_tag.sh

black:
	black $(CHECK_STYLE) $(BLACK_EXCLUDES_EXTEND) $(BLACK_STYLE)

reverse-class:
	mkdir -p $(PYREVERSE_DIR)
	cd $(PYREVERSE_DIR); pyreverse $(PROJECT) $(PYREVERSE_CLASS_OPT) --class $(class); dot $(PYREVERSE_DOT_OPTS) -Tsvg $(class).dot > $(class).svg

reverse:
	mkdir -p $(PYREVERSE_DIR)
	cd $(PYREVERSE_DIR); pyreverse $(PROJECT) $(PYREVERSE_OPTS) $(PYREVERSE_IGNORE); dot $(PYREVERSE_DOT_OPTS) -Tsvg classes.dot > classes.svg; dot $(PYREVERSE_DOT_OPTS) -Tsvg packages.dot > packages.svg
	

black-check:
	black --check $(CHECK_STYLE) $(BLACK_EXCLUDES_EXTEND) $(BLACK_STYLE)

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
	rm -rvf build dist MANIFEST *.egg-info __pycache__ .coverage .cache .pytest_cache $(PROJECT)/_version.py tests/testdata/pssm/1nww_A_ascii_mtx_file.csv
	rm -rvf $(TESTDIR) dask-worker-space
	rm -rvf logs surface_residue_records downloaded mutations_design_profile pockets temperal_pdb expanded_compressed_files analysis screenshots
	rm -rvf tests/logs tests/surface_residue_records tests/mutations_design_profile tests/pockets tests/temperal_pdb tests/analysis/ gremlin_co_evolved_pairs/ seg_chain_resn_sel/ seg_chainA_resn_sel/ mutant_pdbs/
	git clean -ffdx