'''
Shortcut wrappers of esm2
'''

from Bio import SeqIO
from RosettaPy.common.mutation import RosettaPyProteinSequence

from REvoDesign.common import file_extensions as FExt
from REvoDesign.driver.ui_driver import ConfigBus
from REvoDesign.shortcuts.tools.esm2 import ESM1V_MODEL_DICT as EMD
from REvoDesign.shortcuts.tools.esm2 import (
    list_all_esm_variant_predict_model_names, shortcut_esm1v)
from REvoDesign.tools.customized_widgets import AskedValue, dialog_wrapper
from REvoDesign.tools.package_manager import run_worker_thread_with_progress
from REvoDesign.tools.utils import device_picker, timing

from ...logger import ROOT_LOGGER

logging = ROOT_LOGGER.getChild(__name__)


@dialog_wrapper(
    title="ESM1v",
    banner="Run ESM1v/ESM2/MSA1b Variant Predictions (At least 32 GB RAM/GPU-RAM is recommended)",
    options=(
        AskedValue(
            "model_alias",
            typing=list,
            reason="model used to generate predictions.",
            choices=list_all_esm_variant_predict_model_names,
            required=True
        ),
        AskedValue(
            "checkpoint_dir",
            "",
            typing=str,
            reason="Checkpoint directory for the model. If not set, it will be downloaded from the internet.",
            source='Directory',
        ),
        AskedValue(
            "dms_output",
            "",
            typing=str,
            reason="Save the DMS results to a file.",
            source='FileO',
            ext=FExt.CSV,
            required=True,
        ),
        AskedValue(
            "skip_wt",
            False,
            typing=bool,
            reason="Skip the wildtype mutation.",
        ),

        AskedValue(
            "mutation_col",
            "mutation",
            typing=str,
            reason="Mutation column name. Default is 'mutation'.",
        ),

        AskedValue(
            "offset_idx",
            1,
            typing=int,
            reason="Offset index of the sequence. Default is 1.",
            choices=range(-10, 10)
        ),

        AskedValue(
            "scoring_strategy",
            typing=str,
            reason="Scoring strategy. Default is 'wt-marginals'.",
            choices=["wt-marginals", "pseudo-ppl", "masked-marginals"]
        ),

        AskedValue(
            "msa_path",
            "",
            typing=str,
            reason="MSA File Path to run MSA-1b. Default is None.",
            source='FileO',
            ext=FExt.A3M,
        ),
        AskedValue(
            "msa_samples",
            400,
            typing=int,
            reason="Number of samples from MSA to run MSA-1b. Default is 400.",

        ),
        AskedValue(
            "device",
            typing=str,
            reason="Device for the run. Default is 'cpu'. MPS may not work with better performance.",
            choices=device_picker,

        ),
    )
)
def wrapped_esm1v(**kwargs):
    """
    Wrapper function to execute ESM-1v models.

    This function executes the ESM-1v models specified by model aliases and configuration parameters.
    It retrieves necessary inputs from the ConfigBus, prepares the sequence data, and runs the models
    with progress tracking.

    Args:
        **kwargs: Arbitrary keyword arguments. Must include 'model_alias' which specifies the model aliases to use.

    Returns:
        None
    """

    # Log the provided keyword arguments for debugging purposes
    logging.info(kwargs)

    # Extract the model alias from kwargs and map it to actual model names using EMD dictionary
    model_alias = kwargs.pop("model_alias")
    kwargs['model_names'] = [EMD[x] for x in model_alias if x in EMD]

    # Initialize the ConfigBus to retrieve configuration values
    bus = ConfigBus()

    # Retrieve chain ID and designable sequences from the ConfigBus
    chain_id = bus.get_value("ui.header_panel.input.chain_id")
    designable_sequences: RosettaPyProteinSequence = bus.get_value(
        "designable_sequences", RosettaPyProteinSequence.from_dict)
    sequence: str = designable_sequences.get_sequence_by_chain(chain_id)

    # Add the retrieved sequence to kwargs
    kwargs['sequence'] = sequence

    # Execute the ESM-1v models with timing and progress tracking
    with timing(f"running ESM: {', '.join(model_alias)}"):
        logging.info(kwargs)
        run_worker_thread_with_progress(
            shortcut_esm1v,
            **kwargs,
            progress_bar=ConfigBus().ui.progressBar
        )
