from REvoDesign.shortcuts.utils import DialogWrapperRegistry
from REvoDesign.phylogenetics.gremlin_pytorch import run_gremlin


registry = DialogWrapperRegistry("evolution")
wrapped_gremlin = registry.register("run_gremlin", run_gremlin, use_thread=True, use_progressbar=True)
