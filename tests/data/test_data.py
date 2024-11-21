import os
from dataclasses import dataclass
from typing import Optional, Tuple

import pytest


@dataclass
class TestData:
    # running
    nproc_circleci: int = 4

    # setup dir
    test_data_repo: str = os.path.join(os.path.dirname(__file__), "qttests")

    # common info
    molecule: str = "1SUO"
    chain_id: str = "A"

    # after fetch
    post_fetch_spell: str = (
        "remove r. hoh;dss;set cartoon_color, gray70;set cartoon_cylindrical_helices;set cartoon_transparency, .1"
    )

    # dataset PSSM&GREMLIN
    PSSM_GREMLIN_DATA_URL: str = (
        "https://github.com/YaoYinYing/REvoDesign-test-data/releases/download/1SUO/1SUO_A_PSSM_GREMLIN_results.zip"
    )
    PSSM_GREMLIN_DATA_MD5: str = "md5:5fc8ab8f657051ae8117a678924ac471"

    PYTHIA_DDG_CSV_URL: str = (
        "https://github.com/YaoYinYing/REvoDesign-test-data/releases/download/1SUO/1SUO_pred_mask.csv"
    )
    PYTHIA_DDG_CSV_MD5: str = "md5:982eda8c8056c388d9741407dea8e750"

    # pocket
    substrate: str = "CPZ"
    cofactor: str = "HEM"

    @property
    def pocket_pse(self):
        return f"{self.test_data_repo}/analysis/1SUO.xtal.pocket.pze"

    # surface
    suface_probe: float = 30  # ONLY for faster testing!
    exclusion_prefix: str = "pkt_hetatm_"

    @property
    def surface_pse(self):
        return f"{self.test_data_repo}/analysis/1SUO.xtal.surface.pze"

    # surface design
    entropy_min_score: str = "3"
    entropy_max_score: str = "20"
    entropy_score_reversed: bool = False
    entropy_design_case: str = "pssm.ent.surf"
    entropy_reject: str = "PC"
    entropy_accept: str = "E:DATY K:RATY N:ATY Q:EDATY"

    @property
    def entro_design_pse(self):
        return f"{self.test_data_repo}/analysis/1SUO.xtal.surface.ent.pssm.pze"

    mpnn_profile_type: str = "ProteinMPNN"
    mpnn_surface_residues: str = "37,38,39,40"
    mpnn_num_designs: int = 5
    mpnn_temperature: float = 0.1
    mpnn_batch_designs: int = 1
    mpnn_deduplicated: bool = True
    mpnn_score_reversed: bool = True
    mpnn_design_case: str = "mpnn.surf"
    mpnn_reject: str = "PC"
    mpnn_accept: str = "DDDDEENQHRKKK"

    @property
    def mpnn_design_pse(self):
        return f"{self.test_data_repo}/analysis/1SUO.xtal.surface.mpnn.pze"

    ddg_profile_type_biolib: str = "Pythia-ddG"
    ddg_profile_type_local: str = "CSV"
    ddg_surface_residues: str = "37,38,39,40"
    ddg_min_score: str = "-200"
    ddg_max_score: str = "0.3"
    ddg_score_reversed: bool = True
    ddg_design_case: str = "ddg.surf"

    @property
    def ddg_design_pse(self):
        return (
            f"{self.test_data_repo}/analysis/1SUO.xtal.surface.ddg.biolib.pze"
        )

    @property
    def ddg_design_non_biolib_pse(self):
        return (
            f"{self.test_data_repo}/analysis/1SUO.xtal.surface.ddg.local.pze"
        )

    # pocket design
    # use dumbrack rotamer lib
    pocket_pssm_residues: str = (
        "98+100-105+108+114-115+206+209+218+294-303+362-363+365-368+428-429+434+436-439+442+477-478"
    )
    pocket_pssm_min_score: str = "-2"
    pocket_pssm_max_score: str = "0"
    pocket_pssm_score_reversed: bool = False
    pocket_pssm_design_case: str = "pssm.pkt"
    pocket_pssm_reject: str = "PC"
    pocket_pssm_accept: str = ""

    @property
    def pocket_design_pse(self):
        return f"{self.test_data_repo}/analysis/1SUO.xtal.pocket.pssm.pze"

    entropy_to_ddg_score_reversed: bool = True
    entropy_to_ddg_group_id: str = "surf.pssm.ddg"

    EVALUATION_PSE_URL: str = (
        "https://github.com/YaoYinYing/REvoDesign-test-data/releases/download/1SUO/1SUO.xtal.surface.ent.pssm.2.pze"
    )
    EVALUATION_PSE_MD5: str = "md5:225128f0958ad622de9af6b485de5e86"

    # cluster
    cluster_num: int = 10
    cluster_batch: int = 100
    cluster_min: int = 1
    cluster_max: int = 2
    cluster_shuffle: bool = True

    # visualize
    # 1. PSSM-ddg
    # 2. PSSM-MPNN

    visualize_1_profile_type: str = "CSV"
    visualize_1_score_reversed: bool = True
    visualize_1_design_case: str = "pssm.ent.ddg"
    visualize_1_use_global_score: bool = True

    @property
    def visualize_1_pse(self):
        return f"{self.test_data_repo}/analysis/1SUO.xtal.{self.visualize_1_design_case}.pze"

    visualize_2_profile_type: str = "ProteinMPNN"
    visualize_2_score_reversed: bool = True
    visualize_2_design_case: str = "pssm.ent.mpnn"
    visualize_2_use_global_score: bool = True

    @property
    def visualize_2_pse(self):
        return f"{self.test_data_repo}/analysis/1SUO.xtal.{self.visualize_2_design_case}.pze"

    @property
    def entropy_best_hits(self):
        return f"{self.test_data_repo}/mutagenese/1SUO.surf.entro.mutagenesis.besthits.mut.txt"

    # visualize: PSSM entropy to ddG
    @property
    def entropy_to_ddg_pse(self):
        return f"{self.test_data_repo}/analysis/1SUO.xtal.surface.ent.pssm.hits.pze"

    @property
    def pippack_pse(self):
        return f"{self.test_data_repo}/analysis/1SUO.xtal.test_pippack.pze"

    @property
    def sidechain_solver_fallback_pse(self):
        return f"{self.test_data_repo}/analysis/1SUO.xtal.test_sc_fallback.pze"

    @property
    def multi_mut_txt(self):
        return (
            f"{self.test_data_repo}/mutagenese/1SUO.surf.entro.multi_mut.txt"
        )

    multi_design_steps = [2, 3, 5, 3, 4]

    multi_design_scorer: str = "ProteinMPNN"

    @property
    def multi_mut_txt_mpnn(self):
        return f"{self.test_data_repo}/mutagenese/1SUO.surf.entro.multi_mpnn_mut.txt"

    gremlin_monomer_clicks_a2a: Tuple = (
        2,
        (
            6,
            1,
        ),
        (3, 13),
        2,
        -7,
    )
    gremlin_monomer_clicks_o2a: Tuple = (
        1,
        (
            0,
            19,
        ),
        (9, 0),
        2,
        -7,
    )

    @property
    def gremlin_monomer_pse(self):
        return f"{self.test_data_repo}/analysis/{self.molecule}.{self.chain_id}.xtal.test_gremlin_monomer.pze"

    gremlin_topN: int = 35
    gremlin_homomer_molecule: str = "4MB8"
    gremlin_homomer_chain: str = "A"
    gremlin_homomer_o2a_pos: int = 196
    gremlin_homomer_postfetch_spell: str = (
        "remove r. hoh;set cartoon_cylindrical_helices;spectrum chain, blue_white_red, 4MB8"
    )
    gremlin_homomer_profile_url: str = (
        "https://github.com/YaoYinYing/REvoDesign-test-data/releases/download/4MB8/4MB8_A_PSSM_GREMLIN_results.zip"
    )
    gremlin_homomer_profile_md5: str = "md5:999af75bd166b15594ed0435066b4e2d"

    gremlin_homomer_chains: str = "ABCD"

    gremlin_homomer_clicks_a2a: Tuple = (
        2,
        (1, 6),
        14,
        (0, 1),
        2,
        (3, 11),
    )

    gremlin_homomer_clicks_o2a: Tuple = (
        2,
        (15, 15),
        1,
        (6, 1),
        7,
        -20,
    )

    @property
    def gremlin_homomer_o2a_sele(self) -> str:
        return f"{self.gremlin_homomer_molecule} and c. {self.gremlin_homomer_chain} and i. {self.gremlin_homomer_o2a_pos}"

    @property
    def gremlin_homomer_a2a_pse(self):
        return f"{self.test_data_repo}/analysis/{self.gremlin_homomer_molecule}.{self.gremlin_homomer_chains}.xtal.test_gremlin_homomer.a2a.pze"

    @property
    def gremlin_homomer_o2a_pse(self):
        return f"{self.test_data_repo}/analysis/{self.gremlin_homomer_molecule}.{self.gremlin_homomer_chains}.xtal.test_gremlin_homomer.o2a.pze"

    @property
    def used_molecules(self):
        return tuple([self.molecule, self.gremlin_homomer_molecule])


@dataclass
class KeyData:
    hetatm_pocket_sele: str= 'pkt_hetatm_8.0_01'
    design_shell_file: str='../tests/data/pockets/1SUO_design_shell_CPZ_8.0_01_residues.txt'
    surface_file: str='../tests/data/surface_residue_records/1SUO_residues_cutoff_30.0.txt'
    pssm_file: str=None  # type: ignore
    gremlin_pkl_fp: Optional[str]=None
    mutant_file: str='../tests/data/mutagenese/evaluate_pssm_ent_surf.besthits.mut.txt'
    minimum_mutant_file: str='../tests/data/mutagenese/evaluate_pssm_ent_surf.mannual.mut.txt'
    ddg_file: str='../tests/data/pytia_ddg/1SUO_pred_mask.csv'
    evaluate_pse_path: str=None # type: ignore
    gremlin_pkl_fp_homomer: str=None # type: ignore


    DOWNLOAD_DIR = os.path.abspath("../tests/downloaded")
    EXPANDED_DIR = os.path.abspath(
            "../tests/expanded_compressed_files"
        )


    def ensure_evaluate_pse_path(self):
        pse_path = self.download_file(
            url=TestData.EVALUATION_PSE_URL,
            md5=TestData.EVALUATION_PSE_MD5,
        )
        
        self.evaluate_pse_path = pse_path

    def ensure_pssm(self):
        expected_downloaded_file = self.download_file(
            url=TestData.PSSM_GREMLIN_DATA_URL,
            md5=TestData.PSSM_GREMLIN_DATA_MD5,
        )

        dist_dir, expanded_files = self.expand_zip(
            compressed_file=expected_downloaded_file
        )

        assert expanded_files
        pssm_file = os.path.join(
            dist_dir,
            "pssm_msa",
            f"{TestData.molecule}_{TestData.chain_id}_ascii_mtx_file",
        )
        assert os.path.exists(pssm_file)

        self.pssm_file = pssm_file


    def ensure_gremlin_monomer_data(self):
        gremlin_pkl_fp = os.path.join(
            self.EXPANDED_DIR,
            f"{TestData.molecule}_{TestData.chain_id}_PSSM_GREMLIN_results",
            "gremlin_res",
            f"{TestData.molecule}_{TestData.chain_id}.i90c75_aln.GREMLIN.mrf.pkl",
        )

        
        self.gremlin_pkl_fp = gremlin_pkl_fp

    def ensure_gremlin_homomer_data(self):
        zipped = self.download_file(
            url=TestData.gremlin_homomer_profile_url,
            md5=TestData.gremlin_homomer_profile_md5,
        )

        dist_dir, extracted_files = self.expand_zip(
            compressed_file=zipped
        )

        gremlin_pkl_fp = os.path.join(
            dist_dir,
            "gremlin_res",
            f"{TestData.gremlin_homomer_molecule}_{TestData.gremlin_homomer_chain}.i90c75_aln.GREMLIN.mrf.pkl",
        )

    
        self.gremlin_pkl_fp_homomer = gremlin_pkl_fp


    def __post_init__(self):
        self.ensure_pssm()
        self.ensure_gremlin_homomer_data()
        self.ensure_gremlin_monomer_data()
        self.ensure_evaluate_pse_path()


    def download_file(self, url: str, md5: str):
        expected_downloaded_file = os.path.join(
            self.DOWNLOAD_DIR, os.path.basename(url)
        )
        import pooch

        if not os.path.exists(expected_downloaded_file):
            pooch.retrieve(
                url=url,
                known_hash=md5,
                progressbar=True,
                path=self.DOWNLOAD_DIR,
                fname=os.path.basename(url),
            )

            assert os.path.exists(expected_downloaded_file)
        return expected_downloaded_file

    def expand_zip(self, compressed_file: str):
        sub_dirname = os.path.basename(compressed_file).split(".")[0]
        dist_dir = os.path.join(self.EXPANDED_DIR, sub_dirname)
        os.makedirs(dist_dir, exist_ok=True)

        expanded_dirs = os.listdir(dist_dir)
        if not expanded_dirs:
            import zipfile

            with zipfile.ZipFile(compressed_file, mode="r") as z:
                z.extractall(path=dist_dir)

        extracted_files = os.listdir(dist_dir)
        return dist_dir, extracted_files




@dataclass()
class TestDataOnLocalMac(TestData):
    test_data_repo: str = (
        "/Users/yyy/Documents/protein_design/REvoDesign-test-data/"
    )


if __name__ == "__main__":
    print(TestData.test_data_repo)
    print(TestData.post_fetch_spell)
    print(TestDataOnLocalMac.test_data_repo)
    print(TestDataOnLocalMac().pocket_pse)
