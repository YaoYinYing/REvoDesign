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
    post_fetch_spell: str = 'remove r. hoh;dss;set cartoon_color, gray70;set cartoon_cylindrical_helices;set cartoon_transparency, .1'

    # dataset PSSM&GREMLIN
    PSSM_GREMLIN_DATA_URL: str = 'https://github.com/YaoYinYing/REvoDesign-test-data/releases/download/1SUO/1SUO_A_PSSM_GREMLIN_results.zip'
    PSSM_GREMLIN_DATA_MD5: str = 'md5:5fc8ab8f657051ae8117a678924ac471'

    PYTHIA_DDG_CSV_URL: str = 'https://github.com/YaoYinYing/REvoDesign-test-data/releases/download/1SUO/1SUO_pred_mask.csv'
    PYTHIA_DDG_CSV_MD5: str = 'md5:982eda8c8056c388d9741407dea8e750'

    # pocket
    substrate: str = 'CPZ'
    cofactor: str = 'HEM'

    @property
    def pocket_pse(self):
        return f'{self.test_data_repo}/analysis/1SUO.xtal.pocket.pze'

    # surface
    suface_probe: float = 30  # ONLY for faster testing!
    exclusion_prefix: str = 'pkt_hetatm_'

    @property
    def surface_pse(self):
        return f'{self.test_data_repo}/analysis/1SUO.xtal.surface.pze'

    # surface design
    entropy_min_score: str = '3'
    entropy_max_score: str = '20'
    entropy_score_reversed: bool = False
    entropy_design_case: str = 'pssm.ent.surf'
    entropy_reject: str = 'PC'
    entropy_accept: str = 'E:DATY K:RATY N:ATY Q:EDATY'

    @property
    def entro_design_pse(self):
        return f'{self.test_data_repo}/analysis/1SUO.xtal.surface.ent.pssm.pze'

    mpnn_profile_type: str = 'ProteinMPNN'
    mpnn_surface_residues: str = '37,38,39,40'
    mpnn_num_designs: int = 5
    mpnn_temperature: float = 0.1
    mpnn_batch_designs: int = 1
    mpnn_deduplicated: bool = True
    mpnn_score_reversed: bool = True
    mpnn_design_case: str = 'mpnn.surf'
    mpnn_reject: str = 'PC'
    mpnn_accept: str = 'DDDDEENQHRKKK'

    @property
    def mpnn_design_pse(self):
        return f'{self.test_data_repo}/analysis/1SUO.xtal.surface.mpnn.pze'

    ddg_profile_type_biolib: str = 'Pythia-ddG'
    ddg_profile_type_local: str = 'CSV'
    ddg_surface_residues: str = '37,38,39,40'
    ddg_min_score: str = '-200'
    ddg_max_score: str = '0.3'
    ddg_score_reversed: bool = True
    ddg_design_case: str = 'ddg.surf'

    @property
    def ddg_design_pse(self):
        return (
            f'{self.test_data_repo}/analysis/1SUO.xtal.surface.ddg.biolib.pze'
        )

    @property
    def ddg_design_non_biolib_pse(self):
        return (
            f'{self.test_data_repo}/analysis/1SUO.xtal.surface.ddg.local.pze'
        )

    # pocket design
    # use dumbrack rotamer lib
    pocket_pssm_residues: str = '98+100-105+108+114-115+206+209+218+294-303+362-363+365-368+428-429+434+436-439+442+477-478'
    pocket_pssm_min_score: str = '-2'
    pocket_pssm_max_score: str = '0'
    pocket_pssm_score_reversed: bool = False
    pocket_pssm_design_case: str = 'pssm.pkt'
    pocket_pssm_reject: str = 'PC'
    pocket_pssm_accept: str = ''

    @property
    def pocket_design_pse(self):
        return f'{self.test_data_repo}/analysis/1SUO.xtal.pocket.pssm.pze'

    entropy_to_ddg_score_reversed: bool = True
    entropy_to_ddg_group_id: str = 'surf.pssm.ddg'

    EVALUATION_PSE_URL: str = 'https://github.com/YaoYinYing/REvoDesign-test-data/releases/download/1SUO/1SUO.xtal.surface.ent.pssm.2.pze'
    EVALUATION_PSE_MD5: str = 'md5:225128f0958ad622de9af6b485de5e86'

    # cluster
    cluster_num: int = 10
    cluster_batch: int = 100
    cluster_min: int = 1
    cluster_max: int = 2
    cluster_shuffle: bool = True

    # visualize
    # 1. PSSM-ddg
    # 2. PSSM-MPNN

    visualize_1_profile_type: str = 'CSV'
    visualize_1_score_reversed: bool = True
    visualize_1_design_case: str = 'pssm.ent.ddg'
    visualize_1_use_global_score: bool = True

    @property
    def visualize_1_pse(self):
        return f'{self.test_data_repo}/analysis/1SUO.xtal.{self.visualize_1_design_case}.pze'

    visualize_2_profile_type: str = 'ProteinMPNN'
    visualize_2_score_reversed: bool = True
    visualize_2_design_case: str = 'pssm.ent.mpnn'
    visualize_2_use_global_score: bool = True

    @property
    def visualize_2_pse(self):
        return f'{self.test_data_repo}/analysis/1SUO.xtal.{self.visualize_2_design_case}.pze'

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

    @property
    def multi_mut_txt(self):
        return (
            f'{self.test_data_repo}/mutagenese/1SUO.surf.entro.multi_mut.txt'
        )

    multi_design_steps = [2, 3, 6, 5, 7, 3, 4, 12]

    multi_design_scorer: str = 'ProteinMPNN'

    @property
    def multi_mut_txt_mpnn(self):
        return f'{self.test_data_repo}/mutagenese/1SUO.surf.entro.multi_mpnn_mut.txt'


@dataclass
class KeyDataDuringTests:
    pocket_files: list[str] = None
    hetatm_pocket_sele: str = None
    design_shell_file: str = None
    surface_file: str = None
    pssm_file: str = None
    gremlin_pkl_fp: str = None
    mutant_file: str = None
    minimum_mutant_file: str = None
    ddg_file: str = None
    evaluate_pse_path: str = None


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
