from RosettaPy.common.mutation import RosettaPyProteinSequence
from REvoDesign.driver.ui_driver import ConfigBus
from REvoDesign.shortcuts.tools.esm2 import shortcut_esm1v
from REvoDesign.shortcuts.utils import DialogWrapperRegistry
from ...logger import ROOT_LOGGER
logging = ROOT_LOGGER.getChild(__name__)
def esm1v(**kwargs):
    logging.info(kwargs)
    bus = ConfigBus()
    chain_id = bus.get_value("ui.header_panel.input.chain_id")
    designable_sequences: RosettaPyProteinSequence = bus.get_value(
        "designable_sequences", RosettaPyProteinSequence.from_dict)
    sequence: str = designable_sequences.get_sequence_by_chain(chain_id)
    kwargs['sequence'] = sequence
    shortcut_esm1v(**kwargs)
registry = DialogWrapperRegistry("esm")
wrapped_esm1v = registry.register(
    "esm1v",
    esm1v,
    use_thread=True
)