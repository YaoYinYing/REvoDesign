from pymol import cmd
import os
from REvoDesign import ConfigBus, root_logger

logging = root_logger.getChild(__name__)


class PocketSearcher:
    def __init__(self, input_pse, save_dir=f'./pockets/') -> None:
        self.bus = ConfigBus()
        self.input_pse = input_pse
        self.molecule = self.bus.get_value(
            'ui.header_panel.input.molecule', str
        )
        self.chain_id = self.bus.get_value(
            'ui.header_panel.input.chain_id', str
        )
        self.output_pse = self.bus.get_value(
            'ui.prepare.input.pocket.to_pse', str
        )
        self.ligand = self.bus.get_value(
            'ui.prepare.input.pocket.substrate', str, default_value='UNK'
        )
        self.cofactor = self.bus.get_value(
            'ui.prepare.input.pocket.cofactor', str, default_value=''
        )
        self.ligand_radius = self.bus.get_value(
            'ui.prepare.ligand_radius', float, default_value=7
        )
        self.cofactor_radius = self.bus.get_value(
            'ui.prepare.cofactor_radius', float, default_value=6
        )
        self.save_dir = save_dir

    def search_pockets(self):
        cmd.load(self.input_pse)

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
            pocket_filename = os.path.join(
                self.save_dir, f"{self.molecule}_{i}_residues.txt"
            )
            os.makedirs(os.path.dirname(pocket_filename), exist_ok=True)
            with open(pocket_filename, 'w') as f:
                f.write(','.join(map(str, resi)))

        # Save the session
        cmd.save(self.output_pse)
