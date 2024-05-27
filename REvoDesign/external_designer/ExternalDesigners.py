import os
from abc import ABC, abstractmethod
from REvoDesign.citations import CitableModules

class ExternalDesignerAbstract(ABC, CitableModules):
    """
    Abstract class for external design, providing a framework for designing molecules. 
    This class is abstract and must be inherited and implemented by concrete design classes.
    
    Attributes:
        pdb_filename (str): Name of the PDB file, initially set to None, indicating not specified.
        initialized (bool): Flag to indicate whether initialization has been performed, defaults to False.
        molecule: The molecule object, storing the molecule to be designed.
        reload (bool): A flag indicating whether to reload the design, defaults to False.
    
    """
    
    def __init__(self, molecule):
        """
        Initialize the External Designer with a given molecule.
        
        Parameters:
            molecule: The molecular structure or data on which the design operations will be based.
        """
        self.pdb_filename = None
        self.initialized = False
        self.molecule = molecule
        self.reload = False
    
    def get_weights(self):
        """
        Retrieve the weights used in the design process. 
        The implementation should define how these weights are calculated or retrieved.
        """
        ...
    
    @abstractmethod
    def initialize(self, *args, **kwargs):
        """
        Abstract method to initialize the design process.
        Must be implemented by subclasses to perform necessary setup steps.
        
        Parameters:
            *args, **kwargs: Flexible arguments that can be passed to perform specific initialization tasks.
        """
        ...

    @abstractmethod
    def designer(self, *args, **kwargs):
        """
        Abstract method to execute the design algorithm.
        Subclasses must provide the actual design logic.
        
        Parameters:
            *args, **kwargs: Additional parameters that can be used during the design process.
        """
        ...
    

    @abstractmethod
    def scorer(self, sequence, *args, **kwargs):
        """
        Abstract method to evaluate or score a given sequence design.
        Determines the quality or fitness of the designed sequence.
        
        Parameters:
            sequence: The molecular sequence being evaluated.
            *args, **kwargs: Additional parameters for scoring, if required.
        """
        ...


# Designer wrapper to ColabDesign MPNN
class ColabDesigner_MPNN(CitableModules):
    def __init__(self, molecule):
        self.pdb_filename = None
        self.mpnn_model = None
        self.initialized = False
        self.molecule = molecule
        self.reload = False

    # initializing takes time so it should be sent to run_worker_thread_with_progress so UI will not be frozen.
    def initialize(self, *args, **kwargs):
        """
        Initialize the ColabDesigner_MPNN class.

        Args:
        - molecule: Molecule for design.

        Notes:
        - Initializes attributes required for the ColabDesigner_MPNN class.
        """
        from colabdesign.mpnn import mk_mpnn_model
        from REvoDesign.tools.pymol_utils import make_temperal_input_pdb

        self.pdb_filename = make_temperal_input_pdb(
            molecule=self.molecule, reload=self.reload
        )

        self.mpnn_model = mk_mpnn_model()
        assert os.path.exists(self.pdb_filename)
        self.mpnn_model.prep_inputs(
            pdb_filename=self.pdb_filename,
            *args,
            **kwargs,
        )
        self.initialized = True
        self.cite()

    def preffer_substitutions(self, aa=''):
        """
        Set preferred substitutions for the model.

        Args:
        - aa: Amino acids for preferred substitutions.

        Notes:
        - Modifies model inputs to set preferred substitutions.
        """
        from colabdesign.mpnn.model import aa_order

        for k in aa:
            self.mpnn_model._inputs["bias"][:, aa_order[k]] += 0.5

    def scorer(self, sequence):
        """
        Compute the score for a given sequence.

        Args:
        - sequence: Mutant sequence.

        Returns:
        - float: Score value for the given mutant sequence.

        Notes:
        - Computes the score using the MPNN model.
        """
        # scorer must return a float score value given a mutant sequence.
        # lower score is better.
        # https://github.com/dauparas/ProteinMPNN/issues/44#issuecomment-1475522598
        return self.mpnn_model.score(seq=sequence)['score']

    def designer(self, *args, **kwargs):
        """
        Run the designer to obtain design results.

        Args:
        - *args: Variable length argument list.
        - **kwargs: Arbitrary keyword arguments.

        Returns:
        - dict: Dictionary containing sequences and scores.

        Notes:
        - Executes the designer to obtain sequence and score iterables.
        """
        # designer must return a dict containing `'seq'` and `'score'` iterables.
        design_results = self.mpnn_model.sample(*args, **kwargs)
        return design_results

    @property
    def __bibtex__(self):
        return {
            'ProteinMPNN': """@article{
doi:10.1126/science.add2187,
author = {J. Dauparas  and I. Anishchenko  and N. Bennett  and H. Bai  and R. J. Ragotte  and L. F. Milles  and B. I. M. Wicky  and A. Courbet  and R. J. de Haas  and N. Bethel  and P. J. Y. Leung  and T. F. Huddy  and S. Pellock  and D. Tischer  and F. Chan  and B. Koepnick  and H. Nguyen  and A. Kang  and B. Sankaran  and A. K. Bera  and N. P. King  and D. Baker },
title = {Robust deep learning–based protein sequence design using ProteinMPNN},
journal = {Science},
volume = {378},
number = {6615},
pages = {49-56},
year = {2022},
doi = {10.1126/science.add2187},
URL = {https://www.science.org/doi/abs/10.1126/science.add2187},
eprint = {https://www.science.org/doi/pdf/10.1126/science.add2187},
abstract = {Although deep learning has revolutionized protein structure prediction, almost all experimentally characterized de novo protein designs have been generated using physically based approaches such as Rosetta. Here, we describe a deep learning–based protein sequence design method, ProteinMPNN, that has outstanding performance in both in silico and experimental tests. On native protein backbones, ProteinMPNN has a sequence recovery of 52.4\% compared with 32.9\% for Rosetta. The amino acid sequence at different positions can be coupled between single or multiple chains, enabling application to a wide range of current protein design challenges. We demonstrate the broad utility and high accuracy of ProteinMPNN using x-ray crystallography, cryo–electron microscopy, and functional studies by rescuing previously failed designs, which were made using Rosetta or AlphaFold, of protein monomers, cyclic homo-oligomers, tetrahedral nanoparticles, and target-binding proteins. Deep learning approaches such as Alphafold and Rosettafold have made reliable protein structure prediction broadly accessible. For the inverse problem, finding a sequence that folds to a desired structure, most approaches remain based on energy optimization. In two papers, a range of protein design problems were addressed through deep learning methods. Dauparas et al. built on recent deep learning protein design approaches to develop a method called ProteinMPNN. They validated designs experimentally and showed that ProteinMPNN can rescue previously failed designs made using Rosetta or Alphafold. Wicky et al. started from a random sequence and used Monte Carlo sequence search coupled with structure prediction by Alphafold to design cyclic homo-oligomers. Although the designs were generated to achieve stable expression, the sequences had to be regenerated using ProteinMPNN. This approach allowed for the design of a range of experimentally validated cyclic oligomers and paves the way for the design of increasingly complex assemblies. —VV A network-based protein design enables the generation of cyclic homo-oligomers across the nanoscopic scale.}}

"""
        }
