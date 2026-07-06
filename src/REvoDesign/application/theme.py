# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Centralized theme manager for REvoDesign Qt GUI."""

from __future__ import annotations

import os
from pathlib import Path


class ThemeManager:
    """Load and apply the REvoDesign QSS theme.

    Reads ``theme.qss`` from the UI directory and applies it to the
    QApplication instance.  Optionally reads ``appearence.yaml`` for
    font-family and font-size-scale overrides.
    """

    def __init__(self, bus=None):
        self._bus = bus
        self._qss_path = Path(__file__).resolve().parent.parent / "UI" / "theme.qss"
        self._qss: str | None = None

    def _read_qss(self) -> str:
        if self._qss is None:
            if self._qss_path.exists():
                self._qss = self._qss_path.read_text(encoding="utf-8")
            else:
                self._qss = ""
        return self._qss

    def apply(self) -> None:
        """Apply the QSS theme to the running QApplication."""
        from REvoDesign.Qt import QtWidgets

        app = QtWidgets.QApplication.instance()
        if app is None:
            return

        qss = self._read_qss()
        if qss:
            app.setStyleSheet(qss)

        self._apply_font_scale()

    def reload(self) -> None:
        """Clear cached QSS and re-apply.  Use after editing theme.qss at runtime."""
        # ponytail: invalidate cache, reload from disk
        self._qss = None
        self.apply()

    def _apply_font_scale(self) -> None:
        """Apply font scaling from appearence.yaml if configured."""
        if self._bus is None:
            return

        try:
            cfg = self._bus.cfg_group.get("appearence")
            if cfg is None:
                cfg = self._bus.cfg_group.get("appearance")
            if cfg is None:
                return

            scale = getattr(cfg, "font_size_scale", None) or cfg.get("font_size_scale", None) or 1.0
            family = getattr(cfg, "font_family", None) or cfg.get("font_family", None) or ""

            if scale == 1.0 and not family:
                return

            from REvoDesign.Qt import QtWidgets

            app = QtWidgets.QApplication.instance()
            if app is None:
                return

            font = app.font()
            if family:
                font.setFamily(family)
            if scale != 1.0:
                size = font.pointSizeF()
                if size > 0:
                    font.setPointSizeF(size * scale)

            app.setFont(font)
        except Exception:
            pass  # ponytail: font scaling is cosmetic, never block startup

    # ---------------------------------------------------------------
    # Convenience: apply without a ConfigBus reference
    # ---------------------------------------------------------------
    @staticmethod
    def quick_apply() -> None:
        """Apply the theme stylesheet without any config-driven overrides."""
        ThemeManager().apply()
