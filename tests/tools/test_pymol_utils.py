import pymol
import pytest
from pymol import cmd

from REvoDesign.tools.pymol_utils import renumber_protein_chain


@pytest.mark.parametrize(
    "molecule, chain, offset, expected_residues",
    [
        ("test_protein", "A", 0, [str(i) for i in range(1, 21)]),
        ("test_protein", "A", 10, [str(i) for i in range(11, 31)]),
        ("test_protein", None, 5, [str(i) for i in range(6, 26)]),
    ]
)
def test_renumber_protein_chain(molecule, chain, offset, expected_residues):
    """
    Test renumber_protein_chain function with different input parameters.

    This test mocks PyMOL commands and verifies if residue renumbering
    is performed correctly.
    """
    pymol.finish_launching(["pymol", "-qc"])
    cmd.reinitialize()

    cmd.fab("ACDEFGHIKLMNPQRSTVWY", molecule, chain=chain)  # Generate a peptide chain
    renumber_protein_chain(molecule, chain, offset)

    resi_list = sorted({atom.resi for atom in cmd.get_model(
        f"{molecule} and chain {chain}" if chain else molecule).atom}, key=int)

    assert resi_list == expected_residues, f"Expected {expected_residues}, but got {resi_list}"

    cmd.delete(molecule)
