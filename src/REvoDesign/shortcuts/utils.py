'''
Dialog wrapper registry
'''
import atexit
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

import yaml
from immutabledict import immutabledict

from REvoDesign import issues
from REvoDesign.basic.data_structure import FloatRange
from REvoDesign.basic.extensions import resolve_extension
from REvoDesign.tools.customized_widgets import (AskedValue, AskedValueDynamic,
                                                 dialog_wrapper)
from REvoDesign.tools.package_manager import run_worker_thread_with_progress
from REvoDesign.tools.utils import resolve_dotted_function, timing

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


def resolve_choice_from(range_str: str):
    """
    Interprets an input string and dynamically returns a corresponding value based on its prefix.

    The function supports three types of input:

    1. **Range Parsing**:
       - If the input starts with `'range:'`, it parses the rest of the string as integers to create a `range()` object.
       - Accepts formats like `range:1,10` or `range:1,10,2`.
       - Raises InvalidInputError if parsing fails.

    2. **Callable Resolution**:
       - If the input starts with `"REvoDesign."`, it resolves a callable using resolve_dotted_function.
       - Invokes and returns the result of the resolved callable.

    3. **Configuration Value Retrieval**:
       - If the input starts with `"CFG:"`, it retrieves a configuration value via `ConfigBus().get_value(...)`.

    If none of the prefixes match, it raises a [ConfigurationError].

    Args:
        input_str (str): The input string that determines what value or object to return.

    Returns:
        range | Any | Callable:
            - A `range()` object if input starts with `'range:'`.
            - The result of a resolved callable if input starts with `"REvoDesign."`.
            - A configuration value if input starts with `"CFG:"`.

    Raises:
        issues.InvalidInputError: If the input format for 'range:' or 'CFG:' is invalid.
        issues.ConfigurationError: If the input doesn't match any known pattern or expected type.
    """
    if range_str.startswith(('range:', 'FloatRange:')):  # range:1,10 or range:1,10,2 or FloatRange:1,10
        try:
            range_type, range_str = range_str.split(":", 1)
            if range_type == 'range':
                return range(*map(int, range_str.split(",")))
            else:
                return FloatRange.from_str(range_str)
        except TypeError as e:
            raise issues.InvalidInputError(
                'range input expect an input string in pattern range:[<start>,]<end>[,<step>]',
                f'not `{range_str}`'
            ) from e
    elif range_str.startswith("REvoDesign."):
        resolved_callable = resolve_dotted_function(range_str)
        if not isinstance(resolved_callable, Callable):
            raise issues.ConfigurationError(f"Expected as a callable: {range_str}: {resolved_callable}")
        return resolved_callable()  # Get callable dynamically
    elif range_str.startswith("CFG:"):
        from REvoDesign.driver.ui_driver import ConfigBus

        if '.' not in range_str:
            raise issues.InvalidInputError(f'Expected as a config item: {range_str}')
        return ConfigBus().get_value(range_str.removeprefix('CFG:'))

    raise issues.ConfigurationError(f"Unable to parse {range_str}")


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
    Constructs an `AskedValue` object from a configuration dictionary entry.

    This function processes various fields in the input dictionary to create a structured `AskedValue` object,
    which represents a user input field in a dialog interface. It handles:

    - Type resolution based on predefined types.
    - Default value handling, optionally resolved from a callable.
    - Dynamic choice population using either static values or a dynamic resolver.
    - File extension handling for file selection inputs.

    Args:
        entry (dict): A dictionary containing configuration for a single `AskedValue`.
                      Expected keys include:
                      - `"name"` (required): The identifier of the value.
                      - `"type"`: The data type (e.g., "int", "str").
                      - `"default"`: Static default value.
                      - `"default_from"`: Dotted path to a callable returning the default value.
                      - `"choices"` or `"choices_from"`: Static or dynamically resolved list of options.
                      - `"ext"`: File extension filter for file dialogs.
                      - `"reason"`, `"required"`, `"source"`, `"multiple_choices"`: Additional metadata.

    Returns:
        AskedValue: A fully constructed `AskedValue` object ready for use in a dialog.

    Raises:
        ValueError: If there's an error resolving dynamic choices via [resolve_choice_from](file:///Users/yyy/Documents/protein_design/REvoDesign/src/REvoDesign/shortcuts/utils.py#L106-L159).
        Any exceptions raised during callable execution will propagate up.
    """
    # Get type
    typing_func = asked_value_typing_dict.get(entry["type"], str)  # Default to `str` if no match

    # Handle default value from a callable (e.g., using a function name from dotted string)
    val = entry.get("default")
    if "default_from" in entry:
        val = resolve_dotted_function(entry["default_from"])
        if isinstance(val, Callable):
            val = val()

    # Handle choices dynamically
    choices: Any = entry.get("choices")
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

# TODO: skip registry if headless


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
        self.funcs: dict[str, Callable] = {}

    def _load_yaml(self, path: Path) -> dict:
        '''
        Load YAML file.

        Args:
            path (Path): Path to the YAML file.

        Returns:
            dict: The YAML content as a dictionary.
        '''
        with path.open("r") as f:
            return yaml.safe_load(f)

    def register(
        self,
        func_id: str,
        func: Callable,
        use_thread: bool = False,
        has_dynamic_values: bool = False,
        use_progressbar: bool = True,
        kwargs: dict | None = None
    ) -> Callable:
        """
        Register the raw Python function under a given ID.

        Arguments:
        func_id (str): The ID to register the function under.
        func (Callable): The function to register.
        use_thread (bool): Whether to run the function in a separate thread.
        has_dynamic_values (bool): Whether the function accepts dynamic values.
        use_progressbar (bool): Whether to use a progress bar.
        kwargs (Optional[Dict]): Additional keyword arguments to pass to the function.

        Returns either:
        - A callable accepting dynamic values (if has_dynamic_values=True)
        - A callable with no arguments (if has_dynamic_values=False)
        """
        logging.debug(f"Registering function {func_id}")
        if use_thread:
            self.funcs[func_id] = partial(
                run_wrapped_func_in_thread,
                func,
                use_progressbar=use_progressbar,
                **kwargs or {})
        else:
            self.funcs[func_id] = func

        def window_wrapper_dynamic_values(dynamic_values: list[AskedValueDynamic] | None = None):

            self.call(func_id, dynamic_values)

        def window_wrapper(dynamic_values: list[AskedValueDynamic] | None = None):
            self.call(func_id)

        if has_dynamic_values:
            func = window_wrapper_dynamic_values
            func.__doc__ = f'''
Wrapper for the function `{func_id}` to be called from the GUI.
It calls the function `{func_id}` with the given dynamic values.

Arguments:
dynamic_values (Optional[List[Any]]): Dynamic values to pass to the function.
'''
        else:
            func = window_wrapper
            func.__doc__ = f'''
Wrapper for the function `{func_id}` to be called from the GUI.
It calls the function `{func_id}` with the no dynamic values.

Arguments:
dynamic_values (Optional[List[Any]]): Dynamic values to pass to the function.
    Will be ignored if has_dynamic_values=False.
'''

        atexit.register(self.unregister, func_id)
        return func

    def unregister(self, func_id: str):
        """
        Unregister the function with the given ID.

        Args:
            func_id (str): The ID of the function to unregister.
        """
        # logging.debug(f"Unregistering function {func_id}")
        del self.funcs[func_id]

    def call(self, func_id: str, dynamic_values: list[AskedValueDynamic] | None = None):
        """
        Wrap and call the function with a dialog built from YAML config.

        Args:
            func_id (str): The ID of the function to call.
            dynamic_values (Optional[List[dict]]): Dynamic values to pass to the function.

        Returns:
            Any: The result of the function call.
        Raises:
            ValueError: If the function ID is not registered.
            ValueError: If the function ID is not found in the YAML config.
        """
        logging.debug(f"Calling function {func_id}")
        if func_id not in self.funcs:
            raise ValueError(f"No function registered: {func_id}")
        if func_id not in self.config:
            raise ValueError(f"No dialog config for: {func_id}")

        conf: dict[str, Any] = self.config[func_id]
        asked_values = [_build_asked_value(opt) for opt in conf["options"]] if conf.get("options") else []
        logging.debug(f"Asked values: {asked_values}")
        logging.debug(f"Preparing dialog for {func_id}")
        wrapped_func_window = dialog_wrapper(
            title=conf.get("title", func_id),
            banner=conf.get("banner", ""),
            allow_real_time_update=conf.get('real_time', False),
            options=tuple(asked_values),
        )(self.funcs[func_id])
        logging.debug(f"Dialog is ready: {wrapped_func_window}")

        wrapped_func_window(dynamic_values=dynamic_values or [])


def run_wrapped_func_in_thread(func, use_progressbar: bool = True, **kwargs):
    """
    Runs the wrapped process with parameters collected from the dialog.

    Args:
        func: The wrapped process to run.
        **kwargs: Parameters collected from the dialog.
    """
    from REvoDesign.driver.ui_driver import ConfigBus

    with timing(f"performing {func.__name__}"):
        logging.info(kwargs)
        run_worker_thread_with_progress(
            func,
            **kwargs,
            progress_bar=ConfigBus().ui.progressBar if use_progressbar else None
        )
