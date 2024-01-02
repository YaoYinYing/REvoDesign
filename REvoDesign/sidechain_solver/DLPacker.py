import os
from DLPacker.dlpacker import DLPacker
import tempfile
from Bio.Data import IUPACData

from REvoDesign.common.Mutant import Mutant


class DLPacker_worker:
    def __init__(self, pdb_file):
        self.pdb_file = pdb_file

    def reconstruct(self):
        temperal_relaxed_pdb = tempfile.mktemp(suffix=".pdb")
        self.dlpacker_worker.reconstruct_protein(
            order='sequence', output_filename=temperal_relaxed_pdb
        )
        return temperal_relaxed_pdb

    def run_mutate(
        self,
        mutant_obj: Mutant,
        reconstruct_area_radius: int = -1,
        relax_order: str = 'sequence', **kwargs
    ):
        self.dlpacker_worker = DLPacker(str_pdb=self.pdb_file)
        new_obj_name = mutant_obj.get_short_mutant_id()

        temp_dir = tempfile.mkdtemp(prefix='RD_design_dlp')
        temp_pdb_path = os.path.join(temp_dir, f"{new_obj_name}.pdb")

        for mut_info in mutant_obj.get_mutant_info():
            chain_id = mut_info['chain_id']
            position = mut_info['position']
            new_residue = mut_info['mut_res']
            wt_residue = mut_info['wt_res']

            new_residue_3 = IUPACData.protein_letters_1to3[new_residue].upper()
            wt_residue_3 = IUPACData.protein_letters_1to3[wt_residue].upper()

            self.dlpacker_worker.mutate_sequence(
                target=(position, chain_id, wt_residue_3),
                new_label=new_residue_3,
            )

        reconstruct_area = self._get_reconstruct_area(
            mutant_obj=mutant_obj,
            reconstruct_area_radius=reconstruct_area_radius,
        )
        self.dlpacker_worker.reconstruct_region(
            targets=reconstruct_area,
            order=relax_order,
            output_filename=temp_pdb_path,
        )

        return temp_pdb_path

    def _get_reconstruct_area(
        self, mutant_obj: Mutant, reconstruct_area_radius: int = -1
    ):
        
        reconstruct_area = []
        for mut_info in mutant_obj.get_mutant_info():
            chain_id = mut_info['chain_id']
            position = mut_info['position']
            new_residue = mut_info['mut_res']
            new_residue_3 = IUPACData.protein_letters_1to3[new_residue].upper()
            if reconstruct_area_radius<=0:
                print(f'Adding {(position, chain_id, new_residue_3)} for relax...')
                reconstruct_area.append(
                    (position, chain_id, new_residue_3)
                )
            else:
                _=self.dlpacker_worker.get_targets(
                        target=(position, chain_id, new_residue_3),
                        radius=reconstruct_area_radius,
                    )
                print(f'Adding {_} for relax...')
                reconstruct_area.extend(_)
        
        if reconstruct_area:
            
            reconstruct_area=list(set(reconstruct_area))

        return reconstruct_area
