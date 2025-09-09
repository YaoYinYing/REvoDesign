# Build, package, test, and clean
PROJECT=REvoDesign

PIP_EXTRAS=dlpacker,pippack,colabdesign,thermompnn,test
PIP_EXTRAS_2=rfdiffusion_cpu,esm2


TESTDIR=tmp-test-dir-with-unique-name
PYTEST_ARGS=--cov-config=../.coveragerc --cov-report=term-missing --cov=$(PROJECT) -v --pyargs --durations=0 -vv --emoji
PYTEST_CASES_PATH=../tests
PYTEST_XDIST_ARGS=-n 4 -m "not serial"
PYTEST_NON_DIST_SERIAL_ARGS=-m "serial and not very_slow" --cov-append
PYTEST_NON_DIST_SLOW_SERIAL_ARGS=-m "serial and very_slow" --cov-append

PYTEST_KW=all

PYTEST_RUN_FIRST_ARGS=$(PYTEST_ARGS) $(PYTEST_XDIST_ARGS) $(PYTEST_CASES_PATH)
PYTEST_RUN_SECOND_ARGS=$(PYTEST_ARGS) $(PYTEST_NON_DIST_SERIAL_ARGS) $(PYTEST_CASES_PATH)
PYTEST_RUN_THIRD_ARGS=$(PYTEST_ARGS) $(PYTEST_NON_DIST_SLOW_SERIAL_ARGS) $(PYTEST_CASES_PATH)
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
	@echo "  help                   Print this message and exit"
	@echo "  setup-display-gha      Setup ubuntu display for GitHub Actions and CircleCI"
	@echo "  upload-gists           Upload Gist files"
	@echo "  install                Install from pip "
	@echo "  install-no-dept        Install from pip, no dependencies"
	@echo "  install-pytorch-cpu    Install torch-cpu for ci runner image"
	@echo "  reinstall              Reinstall after code changes"
	@echo "  translate              Translate UI"
	@echo "  prepare-test           Run pip to install pytest-related packages"
	@echo "  test                   Run the UnitTest suite"
	@echo "  all-test               Run all tests"
	@echo "  fast-test              Run all fast tests"
	@echo "  kw-test                Run the Keyword Test suite"
	@echo "  kw-test-pdb            Run the Keyword Test suite with pdb"
	@echo "  macos-rosetta-test     Run UI tests versus PyMOL incentive installation (MacOS Application)"
	@echo "  memray                 Memoray profile for leakage, saved as html file"
	@echo "  memray-live            Memoray profile for leakage in live mode"
	@echo "  tag                    Bump a new tag from package version to github tag"
	@echo "  black                  Reformat the code with pre-commit hook"
	@echo "  reverse                Run pyreverse for package and methods and create SVGs"
	@echo "  license-update         License updates for all files"
	@echo "  license-check          Check license for all files"
	@echo "  clean                  Clean up build and generated files" 
	@echo ""


setup-display-gha:
	sudo apt install -y libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-xinerama0 libxcb-xfixes0 x11-utils
	/sbin/start-stop-daemon --start --quiet --pidfile /tmp/custom_xvfb_99.pid --make-pidfile --background --exec /usr/bin/Xvfb -- :99 -screen 0 1920x1200x24 -ac +extension GLX

upload-gists:
	# installer
	gh gist edit c1e8bfe0fc0b9c60bf49ea04a550a044 -f REvoDesign_PyMOL.py src/REvoDesign/tools/package_manager.py
	# installer ui
	gh gist edit c1e8bfe0fc0b9c60bf49ea04a550a044 -f REvoDesign-PyMOL-entry.ui src/REvoDesign/UI/REvoDesign-PyMOL-entry.ui
	# JSONs for installer
	gh gist edit c1e8bfe0fc0b9c60bf49ea04a550a044 -f REvoDesignExtrasTableRich.json jsons/REvoDesignExtrasTableRich.json


# only for test on runner or local machine.
install:
	python -m pip install ".[$(PIP_EXTRAS)]" -U --no-cache-dir
	python -m pip install ".[$(PIP_EXTRAS_2)]" -U --no-cache-dir

install-dgl-linux:
	python -m pip install dgl -f https://data.dgl.ai/wheels/torch-2.3/repo.html

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
	pyuic5 src/REvoDesign/UI/REvoDesign.ui -o src/REvoDesign/UI/Ui_REvoDesign.py
	# update translation file
	#lupdate  src/REvoDesign/UI/REvoDesign.ui -ts src/REvoDesign/UI/language/eng-eng.ts
	lupdate  src/REvoDesign/UI/REvoDesign.ui -ts src/REvoDesign/UI/language/eng-chs.ts

	# release translation file to binarys
	cd src/REvoDesign/UI/;lrelease liguist.pro

prepare-test:
	python -m pip install pytest pytest-cov pytest-order coverage -q --no-cache-dir  

# unit test
test:
	# Run a tmp folder to make sure the tests are run on the installed version
	mkdir -p $(TESTDIR)
	cd $(TESTDIR); python -m pytest $(PYTEST_ARGS) $(PYTEST_CASES_PATH)/UnitTests.py



# ui test with pymol
# see https://github.com/schrodinger/pymol-open-source/pull/106/files#diff-5c3fa597431eda03ac3339ae6bf7f05e1a50d6fc7333679ec38e21b337cb6721R57
# ui-test-pymol:
# 	# Run a tmp folder to make sure the tests are run on the installed version
# 	mkdir -p $(TESTDIR)
# 	cd $(TESTDIR); pymol -ckqy /Users/yyy/miniconda_py39_arm64/lib/python3.10/site-packages/REvoDesign/tests/cases/tabs/;

# all test
all-test:
	# Run a tmp folder to make sure the tests are run on the installed version
	mkdir -p $(TESTDIR)
	cd $(TESTDIR); \
	status_1=0; status_2=0; status_3=0; \
	python -m pytest $(PYTEST_RUN_FIRST_ARGS) || status_1=$$?;\
	python -m pytest $(PYTEST_RUN_SECOND_ARGS) || status_2=$$?;\
	python -m pytest $(PYTEST_RUN_THIRD_ARGS) || status_3=$$?;\
	if [ $$status_1 -eq 0 -a $$status_2 -eq 0 -a $$status_3 -eq 0 ]; then \
	  echo "All tests passed! Combining coverage."; \
	  coverage combine; \
	  cp .coverage* ..; \
	  exit 0; \
	else \
	  echo "One or more tests failed! Not combining coverage."; \
	  exit 1; \
	fi

fast-test:
	# Run a tmp folder to make sure the tests are run on the installed version
	mkdir -p $(TESTDIR)
	cd $(TESTDIR); \
	python -m pytest $(PYTEST_RUN_FIRST_ARGS)



# all test with keyword
kw-test:
	# Run a tmp folder to make sure the tests are run on the installed version
	mkdir -p $(TESTDIR)
	# https://stackoverflow.com/questions/36804181/long-running-py-test-stop-at-first-failure
	cd $(TESTDIR); python -m pytest $(PYTEST_ARGS) $(PYTEST_CASES_PATH)  -k $(PYTEST_KW) -vv -x
	cp $(TESTDIR)/.coverage* .

# all test with keyword, under pdb
kw-test-pdb:
	# Run a tmp folder to make sure the tests are run on the installed version
	mkdir -p $(TESTDIR)
	# https://stackoverflow.com/questions/36804181/long-running-py-test-stop-at-first-failure
	cd $(TESTDIR); python -m pytest -s -v --pdb $(PYTEST_CASES_PATH) -k $(PYTEST_KW)
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
	cd $(TESTDIR);PYTHONMALLOC=malloc memray run --native -m pytest  $(PYTEST_CASES_PATH);  memray flamegraph --leak --split-threads --temporal `ls memray-pytest.*.bin`  


memray-live:
	# Run a tmp folder to make sure the tests are run on the installed version
	mkdir -p $(TESTDIR)
	cd $(TESTDIR);PYTHONMALLOC=malloc memray run --live -m pytest  $(PYTEST_CASES_PATH)/;


tag:
	bash tools/release_tag.sh

black:
	pre-commit run --all-files

reverse:
	mkdir -p $(PYREVERSE_DIR)
	cd $(PYREVERSE_DIR); pyreverse $(PROJECT) $(PYREVERSE_OPTS) $(PYREVERSE_IGNORE); dot $(PYREVERSE_DOT_OPTS) -Tsvg classes.dot > classes.svg; dot $(PYREVERSE_DOT_OPTS) -Tsvg packages.dot > packages.svg
	

license-update:
	python tools/license_notice.py

license-check:
	python tools/license_notice.py --check

clean:
	find . -name "*.pyc" -exec rm -v {} \;
	find . -name "*.orig" -exec rm -v {} \;
	find . -name ".coverage.*" -exec rm -v {} \;
	find . -name ".DS_Store" -exec rm -v {} \;
	find . -name "*.fasta" -exec rm -v {} \;
	find . -name "*.cif" -exec rm -v {} \;
	rm -rvf build dist MANIFEST *.egg-info __pycache__ .coverage .cache .pytest_cache $(PROJECT)/_version.py tests/testdata/pssm/1nww_A_ascii_mtx_file.csv
	rm -rvf $(TESTDIR) dask-worker-space
	rm -rvf logs surface_residue_records mutations_design_profile pockets temperal_pdb analysis screenshots
	rm -rvf tests/logs tests/surface_residue_records tests/mutations_design_profile tests/pockets tests/temperal_pdb tests/analysis/ gremlin_co_evolved_pairs/ seg_chain_resn_sel/ seg_chainA_resn_sel/ mutant_pdbs/
	# git clean -ffdx