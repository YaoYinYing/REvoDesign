from pymol import cmd
import os
from REvoDesign.tools.logger import logging as logger

logging = logger.getChild(__name__)


class PocketSearcher:
    def __init__(self, input_file, output_file, molecule, ligand):
        self.input_file = input_file
        self.output_file = output_file

        self.molecule = molecule
        self.chain_id = 'A'

        self.save_dir = ''
        self.ligand = ligand
        self.ligand_radius = 6
        self.cofactor = ''
        self.cofactor_radius = 7

    def search_pockets(self):
        cmd.load(self.input_file)

        hetatm_pocket_id = cmd.get_unused_name(
            f'pkt_hetatm_{self.ligand_radius}_'
        )
        substrate_pocket_id = cmd.get_unused_name(
            f'pkt_{self.ligand}_{self.ligand_radius}_'
        )
        design_shell_id = cmd.get_unused_name(
            f'design_shell_{self.ligand}_{self.ligand_radius}_'
        )

        cmd.select(
            hetatm_pocket_id,
            f'({self.molecule} and c. {self.chain_id}) and byres hetatm around {self.ligand_radius}',
        )
        cmd.select(
            substrate_pocket_id,
            f'({self.molecule} and c. {self.chain_id}) and (byres resn {self.ligand} around {self.ligand_radius}) and polymer.protein',
        )
        cmd.select(
            design_shell_id,
            f'({self.molecule} and c. {self.chain_id}) and polymer.protein and ({substrate_pocket_id})',
        )

        selections = [
            hetatm_pocket_id,
            substrate_pocket_id,
            design_shell_id,
        ]

        logging.debug(f'cofactor info {self.cofactor}: {self.cofactor_radius}')
        if self.cofactor and self.cofactor_radius > 0:
            cofactor_pocket_id = cmd.get_unused_name(
                f'pkt_cof_{self.cofactor}_{self.cofactor_radius}_'
            )
            logging.info(
                f'Setting cofactor {self.cofactor}: {cofactor_pocket_id}'
            )

            cmd.select(
                cofactor_pocket_id,
                f'({self.molecule} and c. {self.chain_id}) and (byres resn {self.cofactor} around {self.cofactor_radius}) and polymer.protein',
            )
            cmd.select(
                design_shell_id,
                f'{design_shell_id} and not ({cofactor_pocket_id})',
            )
            selections.append(cofactor_pocket_id)

        for i in selections:
            atoms = cmd.get_model(i)
            resi = list(set([int(atom.resi) for atom in atoms.atom]))
            resi.sort()

            # Save pocket residue records
            pocket_filename = os.path.join(self.save_dir, f"{i}_residues.txt")
            os.makedirs(os.path.dirname(pocket_filename), exist_ok=True)
            with open(pocket_filename, 'w') as f:
                f.write(','.join(map(str, resi)))

        # Save the session
        cmd.save(self.output_file)
