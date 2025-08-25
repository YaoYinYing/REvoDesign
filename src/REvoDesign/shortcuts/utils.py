import atexit
import importlib
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import yaml
from immutabledict import immutabledict
from REvoDesign import issues
from REvoDesign.common import file_extensions as Fext
from REvoDesign.tools.customized_widgets import (AskedValue, AskedValueDynamic,
                                                 dialog_wrapper)
from REvoDesign.tools.package_manager import run_worker_thread_with_progress
from REvoDesign.tools.utils import timing
from ..logger import ROOT_LOGGER
logging = ROOT_LOGGER.getChild(__name__)
asked_value_typing_dict: immutabledict[str, type] = immutabledict({
    "int": int,
    "str": str,
    "float": float,
    "dict": dict,
    "list": list,
    "bool": bool,
    "tuple": tuple,
})
REGISTRY_DIR = Path(__file__).parent / "registry"
def resolve_extension(extension: str) -> Fext.ExtColl:
    if hasattr(Fext, extension):
        return getattr(Fext, extension)
    ext_dict = {_e.lower(): f'{_e.upper()} File' for _e in extension.split(';')}
    return Fext.ExtColl.from_dict(ext_dict, prefix='Customized - ')
def resolve_dotted_function(dotted_str: str) -> Callable:
    if ":" not in dotted_str:
        raise issues.InvalidInputError(
            'dotted function expect an input string in pattern <import-path>:(<class>.)<function>',
            f'not `{dotted_str}`'
        )
    module_path, func_name = dotted_str.rsplit(":", 1)
    module = importlib.import_module(module_path)
    if "." not in func_name:
        return getattr(module, func_name)
    _class_name, _func_name = func_name.rsplit(".")
    logging.debug(f'Dotted function resolving `{_class_name}.{_func_name}` from {module}')
    _class = getattr(module, _class_name)
    return getattr(_class, _func_name)
def resolve_choice_from(input_str: str):
    if input_str.startswith('range:'):  
        try:
            return range(*map(int, input_str.removeprefix('range:').split(",")))
        except TypeError as e:
            raise issues.InvalidInputError(
                'range input expect an input string in pattern range:[<start>,]<end>[,<step>]',
                f'not `{input_str}`'
            ) from e
    elif input_str.startswith("REvoDesign."):
        resolved_callable = resolve_dotted_function(input_str)
        if not isinstance(resolved_callable, Callable):
            raise issues.ConfigurationError(f"Expected as a callable: {input_str}: {resolved_callable}")
        return resolved_callable()  
    elif input_str.startswith("CFG:"):
        from REvoDesign.driver.ui_driver import ConfigBus
        if '.' not in input_str:
            raise issues.InvalidInputError(f'Expected as a config item: {input_str}')
        return ConfigBus().get_value(input_str.removeprefix('CFG:'))
    raise issues.ConfigurationError(f"Unable to parse {input_str}")
def resolve_default_value(typing: type) -> Any:
    if typing == bool:
        return False
    if typing == int:
        return 0
    if typing == float:
        return 0.0
    if typing == str:
        return ""
def _build_asked_value(entry: dict) -> AskedValue:
    typing_func = asked_value_typing_dict.get(entry["type"], str)  
    val = entry.get("default")
    if "default_from" in entry:
        val = resolve_dotted_function(entry["default_from"])
        if isinstance(val, Callable):
            val = val()
    choices = entry.get("choices")
    if "choices_from" in entry:
        choices_from: str = entry["choices_from"]
        try:
            choices = resolve_choice_from(choices_from)
        except Exception as e:
            raise ValueError(f"Error resolving choices from {choices_from}: {e}")
    return AskedValue(
        entry["name"],
        val=val or resolve_default_value(typing_func),
        typing=typing_func,
        reason=entry.get("reason", ""),
        required=entry.get("required", False),
        choices=choices,
        source=entry.get("source", 'None'),
        ext=resolve_extension(entry.get("ext", 'Any')),
        multiple_choices=entry.get('multiple_choices', False)
    )
class DialogWrapperRegistry:
    def __init__(self, category: str):
        yaml_path = REGISTRY_DIR / f"{category}.yaml"
        logging.debug(f"Loading {category} registry from {yaml_path}")
        self.config = self._load_yaml(yaml_path)
        self.funcs: Dict[str, Callable] = {}
    def _load_yaml(self, path: Path) -> dict:
        with path.open("r") as f:
            return yaml.safe_load(f)
    def register(
        self,
        func_id: str,
        func: Callable,
        use_thread: bool = False,
        has_dynamic_values: bool = False,
        use_progressbar: bool = True,
        kwargs: Optional[Dict] = None
    ):
        logging.debug(f"Registering function {func_id}")
        if use_thread:
            self.funcs[func_id] = partial(
                run_wrapped_func_in_thread,
                func,
                use_progressbar=use_progressbar,
                **kwargs or {})
        else:
            self.funcs[func_id] = func
        def window_wrapper_dynamic_values(dynamic_values: Optional[List[AskedValueDynamic]] = None):
            self.call(func_id, dynamic_values)
        def window_wrapper(dynamic_values: Optional[List[AskedValueDynamic]] = None):
            self.call(func_id)
        if has_dynamic_values:
            func = window_wrapper_dynamic_values
            func.__doc__ = f'''
Wrapper for the function `{func_id}` to be called from the GUI.
It calls the function `{func_id}` with the given dynamic values.
Arguments:
dynamic_values (Optional[List[Any]]): Dynamic values to pass to the function.
Wrapper for the function `{func_id}` to be called from the GUI.
It calls the function `{func_id}` with the no dynamic values.
Arguments:
dynamic_values (Optional[List[Any]]): Dynamic values to pass to the function.
    Will be ignored if has_dynamic_values=False.
'''
        atexit.register(self.unregister, func_id)
        return func
    def unregister(self, func_id: str):
        logging.debug(f"Unregistering function {func_id}")
        del self.funcs[func_id]
    def call(self, func_id: str, dynamic_values: Optional[List[AskedValueDynamic]] = None):
        logging.debug(f"Calling function {func_id}")
        if func_id not in self.funcs:
            raise ValueError(f"No function registered: {func_id}")
        if func_id not in self.config:
            raise ValueError(f"No dialog config for: {func_id}")
        conf = self.config[func_id]
        asked_values = [_build_asked_value(opt) for opt in conf["options"]] if conf.get("options") else []
        logging.debug(f"Asked values: {asked_values}")
        wrapped_func = dialog_wrapper(
            title=conf.get("title", func_id),
            banner=conf.get("banner", ""),
            options=tuple(asked_values),
        )(self.funcs[func_id])
        wrapped_func(dynamic_values=dynamic_values or [])
def run_wrapped_func_in_thread(func, use_progressbar: bool = True, **kwargs):
    from REvoDesign.driver.ui_driver import ConfigBus
    with timing(f"performing {func.__name__}"):
        logging.info(kwargs)
        run_worker_thread_with_progress(
            func,
            **kwargs,
            progress_bar=ConfigBus().ui.progressBar if use_progressbar else None
        )