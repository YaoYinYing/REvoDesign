'''
Dialog wrapper registry
'''
import atexit
import importlib
import json
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

import yaml
from immutabledict import immutabledict

from REvoDesign import issues
from REvoDesign.common import file_extensions as Fext
from REvoDesign.tools.customized_widgets import AskedValue, dialog_wrapper
from REvoDesign.tools.package_manager import run_worker_thread_with_progress
from REvoDesign.tools.utils import timing

from ..logger import ROOT_LOGGER

logging = ROOT_LOGGER.getChild(__name__)

# Typing selection dictionary for safe type handling
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
    """
    Resolves a dotted string to a callable function.

    Args:
        dotted_str (str): The dotted path to a function, e.g., "module.submodule:function_name".

    Returns:
        Callable: The resolved function.
    """
    module_path, func_name = dotted_str.rsplit(":", 1) if ":" in dotted_str else dotted_str.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, func_name)


def resolve_choice_from(input_str: str) -> Iterable[Any]:
    if input_str.startswith('range:'):  # range:1,10 or range:1,10,2
        return range(*map(int, input_str.removeprefix('range:').split(",")))
    elif input_str.startswith("REvoDesign."):
        resolved_callable = resolve_dotted_function(input_str)
        if isinstance(resolved_callable, Callable):
            return resolved_callable()  # Get callable dynamically
        raise issues.ConfigurationError(f"Expected as a callable:  {resolved_callable}")

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
    """
    Builds an AskedValue object from configuration entry.

    Args:
        entry (dict): A dictionary describing an AskedValue.

    Returns:
        AskedValue: The constructed AskedValue object.
    """
    # Get type
    typing_func = asked_value_typing_dict.get(entry["type"], str)  # Default to `str` if no match

    # Handle default value from a callable (e.g., using a function name from dotted string)
    val = entry.get("default")
    if "default_from" in entry:
        val = resolve_dotted_function(entry["default_from"])()  # Get callable dynamically

    # Handle choices dynamically
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
    """
    Loads YAML config and dynamically builds & calls dialog-wrapped functions.
    """

    def __init__(self, category: str):
        """
        Args:
            category (str): Functional category matching a YAML in registry/.
        """
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
        kwargs: Optional[Dict] = None
    ):
        """
        Register the raw Python function under a given ID.
        Returns either:
        - A callable accepting dynamic values (if has_dynamic_values=True)
        - A callable with no arguments (if has_dynamic_values=False)
        """
        logging.debug(f"Registering function {func_id}")
        if use_thread:
            self.funcs[func_id] = partial(run_wrapped_func_in_thread, func, **kwargs or {})
        else:
            self.funcs[func_id] = func

        def window_wrapper_dynamic_values(dynamic_values: Optional[List[Any]] = None):
            f'''
            Wrapper for the function `{func_id}` to be called from the GUI.
            It calls the function `{func_id}` with the given dynamic values.
            '''
            self.call(func_id, dynamic_values)

        def window_wrapper(dynamic_values: Optional[List[Any]] = None):
            f'''
            Wrapper for the function `{func_id}` to be called from the GUI.
            It calls the function `{func_id}` with the no dynamic values.
            '''
            self.call(func_id)

        atexit.register(self.unregister, func_id)
        return window_wrapper_dynamic_values if has_dynamic_values else window_wrapper

    def unregister(self, func_id: str):
        """
        Unregister the function with the given ID.
        """
        logging.debug(f"Unregistering function {func_id}")
        del self.funcs[func_id]

    def call(self, func_id: str, dynamic_values: Optional[List[dict]] = None):
        """
        Wrap and call the function with a dialog built from YAML config.
        """
        logging.debug(f"Calling function {func_id}")
        if func_id not in self.funcs:
            raise ValueError(f"No function registered: {func_id}")
        if func_id not in self.config:
            raise ValueError(f"No dialog config for: {func_id}")

        conf = self.config[func_id]
        asked_values = [_build_asked_value(opt) for opt in conf["options"]]
        logging.debug(f"Asked values: {asked_values}")
        wrapped_func = dialog_wrapper(
            title=conf.get("title", func_id),
            banner=conf.get("banner", ""),
            options=tuple(asked_values),
        )(self.funcs[func_id])

        wrapped_func(dynamic_values=dynamic_values or [])


def run_wrapped_func_in_thread(func, **kwargs):
    """
    Runs the wrapped process with parameters collected from the dialog.

    Args:
        func: The wrapped process to run.
        **kwargs: Parameters collected from the dialog.
    """
    from REvoDesign.driver.ui_driver import ConfigBus

    with timing(f"Doing {func.__name__}"):
        logging.info(kwargs)
        run_worker_thread_with_progress(
            func,
            **kwargs,
            progress_bar=ConfigBus().ui.progressBar
        )
