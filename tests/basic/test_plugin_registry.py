# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from REvoDesign.basic.plugin_registry import PluginRegistry


def _write(path: Path, content: str):
    path.write_text(content, encoding="utf-8")


def _cleanup_modules(prefix: str):
    for module_name in list(sys.modules):
        if module_name == prefix or module_name.startswith(f"{prefix}."):
            sys.modules.pop(module_name, None)


def _make_pkg(tmp_path: Path, monkeypatch, pkg_name: str, files: dict[str, str]):
    package_dir = tmp_path / pkg_name
    package_dir.mkdir()
    _write(package_dir / "__init__.py", "")
    for filename, content in files.items():
        _write(package_dir / filename, content)
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()
    _cleanup_modules(pkg_name)


def test_plugin_registry_discovers_and_sorts(monkeypatch, tmp_path):
    pkg_name = "tmp_plugin_pkg_a"
    _make_pkg(
        tmp_path,
        monkeypatch,
        pkg_name,
        {
            "base.py": "class BasePlugin:\n    name = ''\n    installed = False\n",
            "alpha.py": "from .base import BasePlugin\nclass Alpha(BasePlugin):\n    name='B'\n    installed=True\n",
            "beta.py": "from .base import BasePlugin\nclass Beta(BasePlugin):\n    name='A'\n    installed=False\n",
            "other.py": "class NotAPlugin:\n    name='X'\n",
        },
    )

    base_mod = importlib.import_module(f"{pkg_name}.base")
    registry = PluginRegistry(base_class=base_mod.BasePlugin, package=pkg_name)

    assert [cls.name for cls in registry.all_classes] == ["A", "B"]
    assert registry.installed_names == ["B"]
    assert registry.get("A").__class__.__name__ == "Beta"


def test_plugin_registry_duplicate_name_fails(monkeypatch, tmp_path):
    pkg_name = "tmp_plugin_pkg_dup"
    _make_pkg(
        tmp_path,
        monkeypatch,
        pkg_name,
        {
            "base.py": "class BasePlugin:\n    name = ''\n    installed = False\n",
            "a.py": "from .base import BasePlugin\nclass PluginA(BasePlugin):\n    name='dup'\n",
            "b.py": "from .base import BasePlugin\nclass PluginB(BasePlugin):\n    name='dup'\n",
        },
    )

    base_mod = importlib.import_module(f"{pkg_name}.base")
    with pytest.raises(ValueError, match="Duplicate plugin name 'dup'"):
        PluginRegistry(base_class=base_mod.BasePlugin, package=pkg_name)

