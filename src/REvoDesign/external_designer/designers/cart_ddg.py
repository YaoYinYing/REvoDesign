import os

from RosettaPy.analyser.ddg import RosettaCartesianddGAnalyser
from RosettaPy.app.cart_ddg import CartesianDDG
from RosettaPy.node import Native, NodeHintT, node_picker

from .. import ExternalDesignerAbstract


class ddg(ExternalDesignerAbstract):

    def __init__(self, molecule: str, node_hint: NodeHintT = 'native', **kwargs):

        self.pdb_filename = None
        self.initialized = False
        self.molecule = molecule
        self.reload = False

        self.node_hint = node_hint
        self.node_config = kwargs.get('node_config', {})

    def initialize(self):
        from REvoDesign.tools.pymol_utils import make_temperal_input_pdb

        self.ddg_runner = CartesianDDG(
            pdb=make_temperal_input_pdb(
                molecule=self.molecule,
                reload=self.reload),
            save_dir='cart_ddg_results',
            job_id=os.path.basename(
                self.pdb_filename)[
                :-4],
            node=node_picker(
                self.node_hint,
                **self.node_config))
        self.pdb_filename = self.ddg_runner.relax()
