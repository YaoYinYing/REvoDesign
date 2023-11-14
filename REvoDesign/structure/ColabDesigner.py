import os


# Designer API to ColabDesign MPNN
class ColabDesigner_MPNN:
    def __init__(self, molecule, *args, **kwargs):
        from colabdesign.mpnn import mk_mpnn_model
        from REvoDesign.tools.pymol_utils import make_temperal_input_pdb

        self.pdb_filename = make_temperal_input_pdb(molecule=molecule)
        self.mpnn_model = mk_mpnn_model()
        assert os.path.exists(self.pdb_filename)
        self.mpnn_model.prep_inputs(
            pdb_filename=self.pdb_filename, *args, **kwargs
        )

    def preffer_substitutions(self, aa=''):
        from colabdesign.mpnn.model import aa_order
        for k in aa:
            self.mpnn_model._inputs["bias"][:,aa_order[k]] += 2

    def scorer(self, sequence):
        # lower score is better.
        # https://github.com/dauparas/ProteinMPNN/issues/44#issuecomment-1475522598
        return self.mpnn_model.score(seq=sequence)['score']

    def designer(self, *args, **kwargs):
        return self.mpnn_model.sample(*args, **kwargs)
    
