# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Launching / splash page for REvoDesign bootstrap."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from REvoDesign.Qt import QtCore, QtGui, QtWidgets

if TYPE_CHECKING:
    from REvoDesign.Qt.ui_runtime_loader import RuntimeUiProxy

_tr = QtCore.QCoreApplication.translate

# Dark theme (default) — stylesheet matching launching.ui design-time values.
_STYLESHEET_DARK = """
    QDialog#LaunchingPage { background-color: #1a1f2e; }
    QLabel#labelTitle { color: #e8e8ec; font-size: 20pt; font-weight: bold; }
    QLabel#labelStatus { color: #8b95a8; font-size: 13pt; }
    QLabel#labelDot { color: #4ecdc4; font-size: 10pt; }
    QLabel#labelInfoLeft, QLabel#labelInfoRight { color: #5a6578; font-size: 9pt; }
    QProgressBar#progressBar { background-color: #232a3a; border: none; border-radius: 2px;
        min-height: 3px; max-height: 3px; }
    QProgressBar#progressBar::chunk { background-color: #4ecdc4; border-radius: 2px; }
"""

# Light theme — warm off-white background, same structure, softer accent.
_STYLESHEET_LIGHT = """
    QDialog#LaunchingPage { background-color: #f5f3ef; }
    QLabel#labelTitle { color: #1a1f2e; font-size: 20pt; font-weight: bold; }
    QLabel#labelStatus { color: #5a6578; font-size: 13pt; }
    QLabel#labelDot { color: #3db8b0; font-size: 10pt; }
    QLabel#labelInfoLeft, QLabel#labelInfoRight { color: #8b95a8; font-size: 9pt; }
    QProgressBar#progressBar { background-color: #dfdcd6; border: none; border-radius: 2px;
        min-height: 3px; max-height: 3px; }
    QProgressBar#progressBar::chunk { background-color: #3db8b0; border-radius: 2px; }
"""

_step: int = 0
_total_steps: int = 0
_start_time: float = 0.0
_timer: QtCore.QTimer | None = None


def init(total_steps: int) -> None:
    """Reset the step counter and elapsed-time clock before a bootstrap sequence."""
    global _step, _total_steps, _start_time
    _step = 0
    _total_steps = total_steps
    _start_time = time.monotonic()


def stylesheet() -> str:
    """Return the dark or light stylesheet depending on the system palette."""
    sample = QtWidgets.QApplication.palette().color(QtGui.QPalette.ColorRole.Window)
    # pylint: disable-next=invalid-name
    L = 0.299 * sample.red() + 0.587 * sample.green() + 0.114 * sample.blue()
    if L >= 128:
        return _STYLESHEET_LIGHT
    return _STYLESHEET_DARK


def update_status(splash_proxy: RuntimeUiProxy | None, message: str) -> None:
    """Update the launching page subtitle and advance the progress bar.

    On first call, starts a 100 ms QTimer that refreshes the elapsed-time
    display in ``labelInfoRight``.  The timer is stopped when the caller
    invokes :func:`stop_elapsed_timer` after the splash is closed.
    """
    if splash_proxy is None:
        return
    global _step, _timer
    if _timer is None:
        # Capture splash_proxy in a closure so the timer callback can
        # update labelInfoRight without a module-level proxy global.
        def _tick() -> None:
            elapsed = time.monotonic() - _start_time
            current = splash_proxy.labelInfoRight.text()
            # Replace the previous " · N.Ns" suffix if present, else append.
            base = current.split("  ·  ")[0] if "  ·  " in current else current
            splash_proxy.labelInfoRight.setText(f"{base}  ·  {elapsed:.1f}s")

        _timer = QtCore.QTimer()
        _timer.timeout.connect(_tick)
        _timer.start(100)  # ponytail: single global timer; per-splash QTimer if concurrency needed
    _step += 1
    splash_proxy.labelStatus.setText(_tr("LaunchingPage", message))
    splash_proxy.progressBar.setRange(0, _total_steps)
    splash_proxy.progressBar.setValue(_step)
    QtWidgets.QApplication.processEvents()


def stop_elapsed_timer() -> None:
    """Stop the elapsed-time timer. Call after the splash screen is closed."""
    global _timer
    if _timer is not None:
        _timer.stop()
        _timer = None
