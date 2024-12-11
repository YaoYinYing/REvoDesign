from unittest.mock import MagicMock
import pytest

from REvoDesign.basic.designer import ExternalDesignerAbstract



# Concrete subclass for testing
class TestDesigner(ExternalDesignerAbstract):
    def initialize(self, *args, **kwargs):
        self.initialized = True

    def scorer(self, mutant, **kwargs):
        return mutant.mock_score  # Mock scoring


def test_initialization():
    molecule = MagicMock()  # Mock molecule object
    designer = TestDesigner(molecule)

    assert designer.pdb_filename is None
    assert designer.initialized is False
    assert designer.molecule == molecule
    assert designer.reload is False


def test_initialize_method():
    molecule = MagicMock()
    designer = TestDesigner(molecule)

    designer.initialize()
    assert designer.initialized is True


def test_scorer_method():
    molecule = MagicMock()
    designer = TestDesigner(molecule)

    mutant = MagicMock()
    mutant.mock_score = 42.0

    score = designer.scorer(mutant)
    assert score == 42.0


def test_parallel_scorer():
    molecule = MagicMock()
    designer = TestDesigner(molecule)

    mutant1 = MagicMock()
    mutant1.empty = False
    mutant1.mock_score = 10.0

    mutant2 = MagicMock()
    mutant2.empty = False
    mutant2.mock_score = 20.0

    mutants = [mutant1, mutant2]

    scored_mutants = designer.parallel_scorer(mutants, nproc=2)

    assert len(scored_mutants) == 2
    assert scored_mutants[0].mutant_score == 10.0
    assert scored_mutants[1].mutant_score == 20.0


def test_score_mutant_mapping():
    mutant1 = MagicMock()
    mutant2 = MagicMock()

    mutants = [mutant1, mutant2]
    scores = [1.0, 2.0]

    result = ExternalDesignerAbstract.score_mutant_mapping(mutants, scores)

    assert len(result) == 2
    assert result[0].mutant_score == 1.0
    assert result[1].mutant_score == 2.0
