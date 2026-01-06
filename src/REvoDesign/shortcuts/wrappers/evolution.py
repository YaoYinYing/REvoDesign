from REvoDesign.shortcuts.utils import DialogWrapperRegistry
from REvoDesign.phylogenetics.gremlin_pytorch import GREMLIN


registry = DialogWrapperRegistry("evolution")
wrapped_gremlin = registry.register("run_gremlin", GREMLIN, use_thread=True, use_progressbar=True)
