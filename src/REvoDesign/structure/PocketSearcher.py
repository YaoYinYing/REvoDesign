"""
This module is used to search pocket residues for a given molecule.
"""

import os

from pymol import cmd

from REvoDesign import ConfigBus
from REvoDesign.logger import ROOT_LOGGER

logging = ROOT_LOGGER.getChild(__name__)


class PocketSearcher:
    def __init__(self, input_pse, save_dir="./pockets/") -> None:
        # TODO: remove bus from instance variables, as heres no need for it
        self.bus = ConfigBus()
        self.input_pse = input_pse
        self.molecule = self.bus.get_value("ui.header_panel.input.molecule", str)
        self.chain_id = self.bus.get_value("ui.header_panel.input.chain_id", str)
        self.output_pse = self.bus.get_value("ui.prepare.input.pocket.to_pse", str)
        self.ligand = self.bus.get_value("ui.prepare.input.pocket.substrate", str, default_value="UNK")
        self.cofactor = self.bus.get_value("ui.prepare.input.pocket.cofactor", str, default_value="")
        self.ligand_radius = self.bus.get_value("ui.prepare.ligand_radius", float, default_value=7)
        self.cofactor_radius = self.bus.get_value("ui.prepare.cofactor_radius", float, default_value=6)
        self.save_dir = save_dir

    @staticmethod
    def process_multiple_resn(selection: str) -> tuple[str, str]:
        """
        Processes a selection string to generate formatted outputs.

        This function takes a string that may contain one or more comma-separated elements.
        It processes the input and returns two strings:
        - The first string is a concatenation of the elements separated by underscores.
        - The second string provides a PyMOL property selection syntax description of the elements.

        Parameters:
        - selection (str): A string containing one or more residue names, possibly separated by commas.

        Returns:
        - Tuple[str, str]: A tuple containing two strings:
            1. Elements joined by underscores.
            2. Descriptive text with residue name listed and prefixed with 'r.'.
        """

        if not selection:
            # If the input string is empty, return two empty strings.
            return "", ""

        if "," not in selection:
            # If there are no commas in the input, return the input as is and a formatted version.
            return selection, f"r. {selection}"

        # Remove spaces and split the input string by commas.
        _sele = selection.replace(" ", "").split(",")

        # Join the elements with underscores and create a descriptive string.
        return "_".join([_sel for _sel in _sele]), " or ".join([f"r. {_sel}" for _sel in _sele])

    def search_pockets(self):
        cmd.load(self.input_pse)

        ligand_label, ligand_sele = self.process_multiple_resn(self.ligand)

        hetatm_pocket_id = cmd.get_unused_name(f"pkt_hetatm_{self.ligand_radius}_")
        substrate_pocket_id = cmd.get_unused_name(f"pkt_{ligand_label}_{self.ligand_radius}_")
        design_shell_id = cmd.get_unused_name(f"design_shell_{ligand_label}_{self.ligand_radius}_")

        cmd.select(
            hetatm_pocket_id,
            f"({self.molecule} and c. {self.chain_id}) and byres hetatm around {self.ligand_radius}",
        )
        cmd.select(
            substrate_pocket_id,
            f"({self.molecule} and c. {self.chain_id}) and (byres ({ligand_sele}) around {self.ligand_radius}) and polymer.protein",
        )
        cmd.select(
            design_shell_id,
            f"({self.molecule} and c. {self.chain_id}) and polymer.protein and ({substrate_pocket_id})",
        )

        selections = [
            hetatm_pocket_id,
            substrate_pocket_id,
            design_shell_id,
        ]

        if self.cofactor and self.cofactor_radius > 0:
            cofact_label, cofact_sele = self.process_multiple_resn(self.cofactor)
            logging.debug(f"cofactor info {self.cofactor} ({cofact_label}: {cofact_sele}): {self.cofactor_radius}")
            cofactor_pocket_id = cmd.get_unused_name(f"pkt_cof_{cofact_label}_{self.cofactor_radius}_")
            logging.info(f"Setting cofactor {self.cofactor}: {cofactor_pocket_id}")

            cmd.select(
                cofactor_pocket_id,
                f"({self.molecule} and c. {self.chain_id}) and (byres ({cofact_sele}) around {self.cofactor_radius}) and polymer.protein",
            )
            cmd.select(
                design_shell_id,
                f"{design_shell_id} and not ({cofactor_pocket_id})",
            )
            selections.append(cofactor_pocket_id)

        for i in selections:
            atoms = cmd.get_model(i)
            resi = list({int(atom.resi) for atom in atoms.atom})
            resi.sort()

            # Save pocket residue records
            pocket_filename = os.path.join(self.save_dir, f"{self.molecule}_{i}_residues.txt")
            os.makedirs(os.path.dirname(pocket_filename), exist_ok=True)
            with open(pocket_filename, "w") as f:
                f.write(",".join(map(str, resi)))

        # Save the session
        cmd.save(self.output_pse)
