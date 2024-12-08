# Build, package, test, and clean
PROJECT=REvoDesign
TESTDIR=tmp-test-dir-with-unique-name
PYTEST_ARGS=--cov-config=../.coveragerc --cov-report=term-missing --cov=$(PROJECT) -v --pyargs --durations=0 -vv --emoji
PYTEST_CASES_PATH=../tests/cases
PYTEST_KW=all
LINT_FILES=$(PROJECT)
CHECK_STYLE=$(PROJECT) tests 
CHECK_STYLE_LAZY=--extend-ignore E501,F401,E227 $(PROJECT) tests

PYREVERSE_CLASS_OPT=-ASmy --colorized
PYREVERSE_DIR=image/svg
PYREVERSE_OPTS=--colorized --no-standalone --only-classnames --module-names n
PYREVERSE_IGNORE=--ignore Ui_REvoDesign.py,UnitTests.py,TestData.py,QtTestWorker.py,SessionMerger.py,client_tools.py,customized_widgets.py,mutant_tools.py,pymol_utils.py,system_tools.py,utils.py,exceptions.py,warnings.py
PYREVERSE_DOT_OPTS=-Ln10 


MACOS_PYMOL_BIN_PATH=/Applications/PyMOL.app/Contents/bin/

help:
	@echo "Commands:"
	@echo ""
	@echo "  help                   print this message and exit"
	@echo "  build                  build source and wheel distributions"
	@echo "  setup-ubuntu           Setup ubuntu display for GitHub Actions"
	@echo "  setup-display          Setup ubuntu display for CircleCI"
	@echo "  upload-gists           Upload Gist files"
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
	@echo "  memray                 memoray profile for leakage, saved as html file"
	@echo "  memray-live            memoray profile for leakage in live mode"
	@echo "  format                 automatically format the code"
	@echo "  tag                    pin a new tag from package version to github tag"
	@echo "  black                  black format for all python files"
	@echo "  reverse                run pyreverse for package and methods and create SVGs"
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

upload-gists:
	# installer
	gh gist edit c1e8bfe0fc0b9c60bf49ea04a550a044 -f REvoDesign_PyMOL.py src/REvoDesign/tools/package_manager.py
	# installer ui
	gh gist edit c1e8bfe0fc0b9c60bf49ea04a550a044 -f REvoDesign-PyMOL-entry.ui src/REvoDesign/UI/REvoDesign-PyMOL-entry.ui
	# JSONs for installer
	gh gist edit c1e8bfe0fc0b9c60bf49ea04a550a044 -f REvoDesignDeptsTable.json jsons/REvoDesignDeptsTable.json
	gh gist edit c1e8bfe0fc0b9c60bf49ea04a550a044 -f REvoDesignExtrasTable.json jsons/REvoDesignExtrasTable.json


# only for test on runner or local machine.
install:
	python -m pip install ".[dlpacker,pippack,colabdesign,test]" -U --no-cache-dir

# only for test on ci runner or local machine that already have all depencies installed.
install-no-dept:
	python -m pip install . --no-dependencies --no-cache-dir

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
	cd $(TESTDIR); python -m pytest -x $(PYTEST_ARGS) $(PYTEST_CASES_PATH)/tabs;

ui-test-lan:
	# Run a tmp folder to make sure the tests are run on the installed version
	mkdir -p $(TESTDIR)
	cd $(TESTDIR); python -m pytest -x $(PYTEST_ARGS) $(PYTEST_CASES_PATH)/tabs -k 'test_non_english_input';


# ui test with pymol
# see https://github.com/schrodinger/pymol-open-source/pull/106/files#diff-5c3fa597431eda03ac3339ae6bf7f05e1a50d6fc7333679ec38e21b337cb6721R57
ui-test-pymol:
	# Run a tmp folder to make sure the tests are run on the installed version
	mkdir -p $(TESTDIR)
	cd $(TESTDIR); pymol -ckqy /Users/yyy/miniconda_py39_arm64/lib/python3.10/site-packages/REvoDesign/tests/cases/tabs/;

# all test
all-test:
	# Run a tmp folder to make sure the tests are run on the installed version
	mkdir -p $(TESTDIR)
	# https://stackoverflow.com/questions/36804181/long-running-py-test-stop-at-first-failure
	cd $(TESTDIR); python -m pytest -x $(PYTEST_ARGS) $(PYTEST_CASES_PATH)
	cp $(TESTDIR)/.coverage* .

# all test with keyword
kw-test:
	# Run a tmp folder to make sure the tests are run on the installed version
	mkdir -p $(TESTDIR)
	# https://stackoverflow.com/questions/36804181/long-running-py-test-stop-at-first-failure
	cd $(TESTDIR); python -m pytest -x $(PYTEST_ARGS) $(PYTEST_CASES_PATH)  -k $(PYTEST_KW)
	cp $(TESTDIR)/.coverage* .

macos-rosetta-test:
	$(MACOS_PYMOL_BIN_PATH)/python -m pip install ".[test]" -U --no-cache-dir
	# Run a tmp folder to make sure the tests are run on the installed version
	mkdir -p $(TESTDIR)
	# https://stackoverflow.com/questions/36804181/long-running-py-test-stop-at-first-failure
	$(MACOS_PYMOL_BIN_PATH)/python -m pip install pytest pytest-cov coverage psutil -q --no-cache-dir 
	cd $(TESTDIR); $(MACOS_PYMOL_BIN_PATH)/python -m pytest -x $(PYTEST_ARGS) $(PYTEST_CASES_PATH)/tabs/ -k 'not mpnn'



memray:
	# Run a tmp folder to make sure the tests are run on the installed version
	mkdir -p $(TESTDIR)
	cd $(TESTDIR);PYTHONMALLOC=malloc memray run --native -m pytest  $(PYTEST_CASES_PATH)/tabs/;  memray flamegraph --leak --split-threads --temporal `ls memray-pytest.*.bin`  

fake:
	cat 

memray-live:
	# Run a tmp folder to make sure the tests are run on the installed version
	mkdir -p $(TESTDIR)
	cd $(TESTDIR);memray run --live -m pytest  $(PYTEST_CASES_PATH)/tabs/;

format: license-update black

tag:
	bash tools/release_tag.sh

black:
	pre-commit run --all-files

reverse-class:
	mkdir -p $(PYREVERSE_DIR)
	cd $(PYREVERSE_DIR); pyreverse $(PROJECT) $(PYREVERSE_CLASS_OPT) --class $(class); dot $(PYREVERSE_DOT_OPTS) -Tsvg $(class).dot > $(class).svg

reverse:
	mkdir -p $(PYREVERSE_DIR)
	cd $(PYREVERSE_DIR); pyreverse $(PROJECT) $(PYREVERSE_OPTS) $(PYREVERSE_IGNORE); dot $(PYREVERSE_DOT_OPTS) -Tsvg classes.dot > classes.svg; dot $(PYREVERSE_DOT_OPTS) -Tsvg packages.dot > packages.svg
	

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
	rm -rvf logs surface_residue_records mutations_design_profile pockets temperal_pdb analysis screenshots
	rm -rvf tests/logs tests/surface_residue_records tests/mutations_design_profile tests/pockets tests/temperal_pdb tests/analysis/ gremlin_co_evolved_pairs/ seg_chain_resn_sel/ seg_chainA_resn_sel/ mutant_pdbs/
	git clean -ffdx