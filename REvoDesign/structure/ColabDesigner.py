import os


# Designer API to ColabDesign MPNN
class ColabDesigner_MPNN:
    def __init__(self, molecule, *args, **kwargs):
        from colabdesign.mpnn import mk_mpnn_model
        from REvoDesign.tools.utils import make_temperal_input_pdb

        self.pdb_filename = make_temperal_input_pdb(molecule=molecule)
        self.mpnn_model = mk_mpnn_model()
        assert os.path.exists(self.pdb_filename)
        self.mpnn_model.prep_inputs(
            pdb_filename=self.pdb_filename, *args, **kwargs
        )

    def scorer(self, sequence):
        return self.mpnn_model.score(seq=sequence)['score']

    def designer(self, *args, **kwargs):
        return self.mpnn_model.sample(*args, **kwargs)
