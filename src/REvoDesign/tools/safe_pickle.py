# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

import importlib
import io
import pickle
from collections import OrderedDict, defaultdict, deque
from typing import BinaryIO, Iterable

SAFE_BUILTINS = {
    "bool": bool,
    "bytearray": bytearray,
    "bytes": bytes,
    "complex": complex,
    "dict": dict,
    "float": float,
    "frozenset": frozenset,
    "int": int,
    "list": list,
    "range": range,
    "set": set,
    "slice": slice,
    "str": str,
    "tuple": tuple,
}

SAFE_COLLECTIONS = {
    "OrderedDict": OrderedDict,
    "defaultdict": defaultdict,
    "deque": deque,
}

DEFAULT_ALLOWED_MODULE_PREFIXES: tuple[str, ...] = (
    "REvoDesign",
    "RosettaPy",
    "numpy",
)


def _module_is_allowed(module_name: str, allowed_module_prefixes: Iterable[str]) -> bool:
    for prefix in allowed_module_prefixes:
        if module_name == prefix or module_name.startswith(f"{prefix}."):
            return True
    return False


class _RestrictedUnpickler(pickle.Unpickler):
    def __init__(self, fp: BinaryIO, allowed_module_prefixes: Iterable[str]):
        super().__init__(fp)
        self.allowed_module_prefixes = tuple(allowed_module_prefixes)

    def find_class(self, module: str, name: str):
        if module == "builtins":
            if name in SAFE_BUILTINS:
                return SAFE_BUILTINS[name]
            raise pickle.UnpicklingError(f"Unsafe builtin in pickle payload: {name}")

        if module == "collections":
            if name in SAFE_COLLECTIONS:
                return SAFE_COLLECTIONS[name]
            raise pickle.UnpicklingError(f"Unsafe collections type in pickle payload: {name}")

        if module == "copyreg" and name == "_reconstructor":
            return importlib.import_module(module)._reconstructor

        if not _module_is_allowed(module, self.allowed_module_prefixes):
            raise pickle.UnpicklingError(f"Disallowed module in pickle payload: {module}.{name}")

        imported_module = importlib.import_module(module)
        try:
            return getattr(imported_module, name)
        except AttributeError as exc:
            raise pickle.UnpicklingError(f"Missing attribute in pickle payload: {module}.{name}") from exc


def restricted_loads(data: bytes, allowed_module_prefixes: Iterable[str] = DEFAULT_ALLOWED_MODULE_PREFIXES):
    return _RestrictedUnpickler(io.BytesIO(data), allowed_module_prefixes=allowed_module_prefixes).load()


def restricted_load(fp: BinaryIO, allowed_module_prefixes: Iterable[str] = DEFAULT_ALLOWED_MODULE_PREFIXES):
    return _RestrictedUnpickler(fp, allowed_module_prefixes=allowed_module_prefixes).load()
