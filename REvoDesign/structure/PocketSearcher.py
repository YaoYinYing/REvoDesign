from pymol import cmd
import os
from attrs import define, field
from REvoDesign.common.RunnerConfig import REvoDesignRunnerConfig
from REvoDesign.tools.logger import logging as logger

logging = logger.getChild(__name__)


@define(kw_only=True)
class PocketSearcherConfig(REvoDesignRunnerConfig):
    save_dir: str = field(converter=str, default='.')
    ligand: str = field(converter=str, default='UNK')
    ligand_radius: float = field(converter=float, default=6)
    cofactor: str = field(converter=str, default='')
    cofactor_radius: float = field(converter=float, default=7)


@define(kw_only=True)
class PocketSearcher(PocketSearcherConfig):
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
