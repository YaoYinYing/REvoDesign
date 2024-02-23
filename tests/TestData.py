import os
from dataclasses import dataclass


@dataclass()
class TestData:
    # running 
    nproc_circleci: int = 4

    # setup dir
    test_data_repo: str = os.path.join(os.path.dirname(__file__), 'qttests')

    # common info
    molecule: str = '1SUO'
    chain_id: str = 'A'

    # after fetch
    post_fetch_spell: str = 'remove r. hoh;dss'

    # dataset PSSM&GREMLIN
    PSSM_GREMLIN_DATA_URL:str = 'https://github.com/YaoYinYing/REvoDesign-test-data/releases/download/1SUO/1SUO_A_PSSM_GREMLIN_results.zip'
    PSSM_GREMLIN_DATA_MD5:str = 'md5:5fc8ab8f657051ae8117a678924ac471'

    PYTHIA_DDG_CSV_URL:str = 'https://github.com/YaoYinYing/REvoDesign-test-data/releases/download/1SUO/1SUO_pred_mask.csv'
    PYTHIA_DDG_CSV_MD5: str ='md5:982eda8c8056c388d9741407dea8e750'

    
    # pocket
    substrate: str = 'CPZ'
    cofactor: str = 'HEM'

    # surface
    suface_probe: float = 30  # ONLY for faster testing!
    exclusion_prefix: str = 'pkt_hetatm_'

    # surface design
    entropy_min_score: str = '3'
    entropy_max_score: str = '20'
    entropy_score_reversed: bool = False
    entropy_design_case: str = 'pssm.ent.surf'
    entropy_reject: str = 'PC'
    entropy_accept: str = 'E:DATY K:RATY N:ATY Q:EDATY'

    mpnn_profile_type: str = 'ProteinMPNN'
    mpnn_surface_residues: str = '37,38,39,40,43,44,45,46,48'
    mpnn_num_designs: int = 5
    mpnn_temperature: float = 0.1
    mpnn_batch_designs: int = 1
    mpnn_deduplicated: bool = True
    mpnn_score_reversed: bool = True
    mpnn_design_case: str = 'mpnn.surf'
    mpnn_reject: str = 'PC'
    mpnn_accept: str = 'DDDDEENQHRKKK'

    ddg_profile_type_biolib: str = 'Pythia-ddG'
    ddg_profile_type_local: str = 'CSV'
    ddg_surface_residues: str = '37,38,39,40'
    ddg_min_score: str = '-200'
    ddg_max_score: str = '0.3'
    ddg_score_reversed: bool = True
    ddg_design_case: str = 'ddg.surf'

    # pocket design
    pocket_pssm_residues: str = '103,104,105'
    pocket_pssm_min_score: str = '-2'
    pocket_pssm_max_score: str = '0'
    pocket_pssm_score_reversed: bool = False
    pocket_pssm_design_case: str = 'pssm.pkt'
    pocket_pssm_reject: str = 'PC'
    pocket_pssm_accept: str = ''

    entropy_to_ddg_score_reversed: bool = True
    entropy_to_ddg_group_id: str = 'surf.pssm.ddg'

    EVALUATION_PSE_URL:str ='https://github.com/YaoYinYing/REvoDesign-test-data/releases/download/1SUO/1SUO.xtal.surface.ent.pssm.2.pze'
    EVALUATION_PSE_MD5:str ='md5:225128f0958ad622de9af6b485de5e86'

    @property
    def pocket_pse(self):
        return f'{self.test_data_repo}/analysis/1SUO.xtal.pocket.pze'

    @property
    def surface_pse(self):
        return f'{self.test_data_repo}/analysis/1SUO.xtal.surface.pze'

    # mutate: PSSM entropy
    @property
    def PSSM_file(self):
        return f'{self.test_data_repo}/expanded_compressed_files/pssm_msa/1SUO_A_ascii_mtx_file'

    @property
    def surface_file(self):
        return f'{self.test_data_repo}/surface_residue_records/residues_cutoff_15.0.txt'

    @property
    def entro_design_pse(self):
        return f'{self.test_data_repo}/analysis/1SUO.xtal.surface.ent.pssm.pze'

    @property
    def mpnn_design_pse(self):
        return f'{self.test_data_repo}/analysis/1SUO.xtal.surface.mpnn.pze'

    @property
    def ddg_design_pse(self):
        return f'{self.test_data_repo}/analysis/1SUO.xtal.surface.ddg.biolib.pze'

    @property
    def ddg_design_non_biolib_pse(self):
        return f'{self.test_data_repo}/analysis/1SUO.xtal.surface.ddg.local.pze'


    @property
    def pocket_design_pse(self):
        return (
            f'{self.test_data_repo}/analysis/1SUO.xtal.pocket.pssm.pze'
        )

    @property
    def entropy_best_hits(self):
        return f'{self.test_data_repo}/mutagenese/1SUO.surf.entro.mutagenesis.besthits.mut.txt'

    # visualize: PSSM entropy to ddG
    @property
    def entropy_to_ddg_pse(self):
        return f'{self.test_data_repo}/analysis/1SUO.xtal.surface.ent.pssm.hits.pze'

    @property
    def pippack_pse(self):
        return f'{self.test_data_repo}/analysis/1SUO.xtal.test_pippack.pze'

@dataclass()
class TestDataOnLocalMac(TestData):
    test_data_repo: str = (
        '/Users/yyy/Documents/protein_design/REvoDesign-test-data/'
    )


if __name__ == '__main__':
    print(TestData.test_data_repo)
    print(TestData.post_fetch_spell)
    print(TestDataOnLocalMac.test_data_repo)
    print(TestDataOnLocalMac().pocket_pse)
