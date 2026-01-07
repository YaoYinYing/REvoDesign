import gc
import pickle
from REvoDesign.basic.abc_third_party_module import TorchModuleAbstract,ThirdPartyModuleAbstract
from REvoDesign.bootstrap.set_config import is_package_installed
from REvoDesign.phylogenetics.gremlin_tools import GREMLIN_Tools
from REvoDesign.tools.utils import require_installed,get_cited

@require_installed
class GremlinPytorch(TorchModuleAbstract,ThirdPartyModuleAbstract):
    name: str = "GremlinPytorch"
    installed: bool = is_package_installed("torch")

    __bibtex__=GREMLIN_Tools.__bibtex__

    def __init__(self, device: str = "cpu", **kwargs):
        super().__init__(device, **kwargs)

    @get_cited
    def run(self, fasta_file: str, mrf_file_save: str, gremlin_iter: int = 100):
        """
        Run GREMLIN on a given FASTA file and save the MRF results.

        Args:
            fasta_file (str): Path to the input FASTA file.
            mrf_file_save (str): Path to save the output MRF file (NumPy .npz format).
            gremlin_iter (int): Number of iterations for GREMLIN optimization.
        """
        # internal import to avoid circular imports and torch missing
        from REvoDesign.phylogenetics.gremlin_pytorch import GREMLIN, mk_msa, parse_fasta

        headers, seqs = parse_fasta(fasta_file)
        msa = mk_msa(seqs)
        mrf = GREMLIN(
            msa,
            opt_type="adam",
            opt_iter=gremlin_iter,
            lr=1.0,
            b1=0.9,
            b2=0.999,
            b_fix=False,
            batch_size=None,
            device=self.device,
        )
        # save mtx file
        with open(mrf_file_save, "wb") as f:
            pickle.dump(mrf, f)

def run_gremlin(fasta_file: str, mrf_file_save: str, gremlin_iter: int = 100, device: str = "cpu"):
    app=GremlinPytorch(device)
    app.run(fasta_file, mrf_file_save, gremlin_iter)
    app.cleanup()
    del app
    gc.collect()