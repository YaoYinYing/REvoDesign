"""
Shortcut wrappers of esm2
"""

from RosettaPy.common.mutation import RosettaPyProteinSequence

from REvoDesign.driver.ui_driver import ConfigBus
from REvoDesign.shortcuts.tools.esm2 import shortcut_esm1v
from REvoDesign.shortcuts.utils import DialogWrapperRegistry

from ...logger import ROOT_LOGGER

logging = ROOT_LOGGER.getChild(__name__)


def esm1v(**kwargs):
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

    # Initialize the ConfigBus to retrieve configuration values
    bus = ConfigBus()

    # Retrieve chain ID and designable sequences from the ConfigBus
    chain_id = bus.get_value("ui.header_panel.input.chain_id")
    designable_sequences = bus.get_value("designable_sequences", RosettaPyProteinSequence.from_dict, cfg="runtime")
    sequence: str = designable_sequences.get_sequence_by_chain(chain_id)

    # Add the retrieved sequence to kwargs
    kwargs["sequence"] = sequence

    # Execute the ESM-1v models with timing and progress tracking
    shortcut_esm1v(**kwargs)


# Register category 'esm'
registry = DialogWrapperRegistry("esm")

wrapped_esm1v = registry.register("esm1v", esm1v, use_thread=True)
