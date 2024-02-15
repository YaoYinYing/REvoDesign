from dataclasses import dataclass

from overrides import override


@dataclass()
class TestData:
    # setup dir
    test_data_repo: str = ''

    # common info
    molecule: str = '1SUO'
    chain_id: str = 'A'

    # after fetch
    post_fetch_spell: str = 'remove r. hoh'

    # dataset PSSM&GREMLIN
    PSSM_GREMLIN_DATA_URL = 'https://github.com/YaoYinYing/REvoDesign-test-data/archive/refs/tags/1SUO.zip'

    # pocket
    substrate: str = 'CPZ'
    cofactor: str = 'HEM'

    # surface
    exclusion_prefix: str = 'pkt_hetatm_'

    entropy_min_score: str = '-2'
    entropy_max_score: str = '20'
    entropy_score_reversed: bool = False
    entropy_design_case: str = 'pssm.ent.surf'
    entropy_reject: str = 'PC'
    entropy_accept: str = 'E:DATY K:RATY N:ATY Q:EDATY'

    entropy_to_ddg_score_reversed: bool = True
    entropy_to_ddg_group_id: str = 'surf.pssm.ddg'

    @property
    def pocket_pse(self):
        return f'{self.test_data_repo}P450/analysis/1SUO.xtal.pocket.pze'

    @property
    def surface_pse(self):
        return f'{self.test_data_repo}P450/analysis/1SUO.xtal.surface.pze'

    # mutate: PSSM entropy
    @property
    def PSSM_file(self):
        return f'{self.test_data_repo}expanded_compressed_files/1SUO_A_PSSM_GREMLIN_results.zip/pssm_msa/1SUO_A_ascii_mtx_file'

    @property
    def surface_file(self):
        return f'{self.test_data_repo}surface_residue_records/residues_cutoff_15.0.txt'

    @property
    def entro_design_pse(self):
        return f'{self.test_data_repo}P450/analysis/1SUO.xtal.surface.ent.pssm.2.pze'

    @property
    def entropy_best_hits(self):
        return f'{self.test_data_repo}P450/mutagenese/1SUO.surf.entro.mutagenesis.besthits.mut.txt'

    # visualize: PSSM entropy to ddG
    @property
    def entropy_to_ddg_pse(self):
        return f'{self.test_data_repo}P450/analysis/1SUO.xtal.surface.ent.pssm.hits.pze'


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
