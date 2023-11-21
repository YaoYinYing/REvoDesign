import os


# Designer wrapper to ColabDesign MPNN
class ColabDesigner_MPNN:
    def __init__(self, molecule):
        self.pdb_filename = None
        self.mpnn_model = None
        self.initialized = False
        self.molecule = molecule
        self.reload = False

    # initializing take time so it should be sent to run_worker_thread_with_progress so UI will not be frozen.
    def initialize(self, *args, **kwargs):
        from colabdesign.mpnn import mk_mpnn_model
        from REvoDesign.tools.pymol_utils import make_temperal_input_pdb

        self.pdb_filename = make_temperal_input_pdb(molecule=self.molecule,reload=self.reload)
        self.mpnn_model = mk_mpnn_model()
        assert os.path.exists(self.pdb_filename)
        self.mpnn_model.prep_inputs(pdb_filename=self.pdb_filename, *args, **kwargs)
        self.initialized = True

    def preffer_substitutions(self, aa=''):
        from colabdesign.mpnn.model import aa_order

        for k in aa:
            self.mpnn_model._inputs["bias"][:, aa_order[k]] += 0.5

    def scorer(self, sequence):
        # scorer must return a float score value given a mutant sequence.
        # lower score is better.
        # https://github.com/dauparas/ProteinMPNN/issues/44#issuecomment-1475522598
        return self.mpnn_model.score(seq=sequence)['score']

    def designer(self, *args, **kwargs):
        # designer must return a dict containing `'seq'` and `'score'` iterables.
        design_results=self.mpnn_model.sample(*args, **kwargs)
        return design_results
