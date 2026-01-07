from REvoDesign.shortcuts.tools.evolution import run_gremlin
from REvoDesign.shortcuts.utils import DialogWrapperRegistry

registry = DialogWrapperRegistry("evolution")
wrapped_gremlin = registry.register("run_gremlin", run_gremlin, use_thread=True, use_progressbar=True)
