# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import pandas as pd

from REvoDesign.Qt import QtCore, QtGui, QtWidgets
from REvoDesign.tools.customized_widgets import MatrixIndex, QButtonMatrixGremlin


def _build_gremlin_widget(qtbot):
    df = pd.DataFrame(
        [[-1.0, -0.2, 0.4], [0.1, 0.7, -0.6], [0.9, -0.4, 0.2]],
        index=list("ARN"),
        columns=list("ARN"),
    )
    widget = QButtonMatrixGremlin(df_matrix=df, sequence="ARND", pair_i=0, pair_j=1)
    widget.alphabet_row = list("ARN")
    widget.alphabet_col = list("ARN")
    widget.init_ui()
    widget.resize(220, 220)
    qtbot.addWidget(widget)
    widget.show()
    qtbot.wait(50)
    return widget, df


def _leave_event():
    event_type = QtCore.QEvent.Type.Leave if hasattr(QtCore.QEvent, "Type") else QtCore.QEvent.Leave
    return QtCore.QEvent(event_type)


def _make_mouse_move_event(pos: QtCore.QPointF | QtCore.QPoint) -> QtGui.QMouseEvent:
    """Create a platform-independent MouseMove event."""
    return QtGui.QMouseEvent(
        QtCore.QEvent.MouseMove,
        QtCore.QPointF(pos) if hasattr(QtCore, "QPointF") else pos,
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )


def test_button_matrix_hover_clears(qtbot):
    widget, _ = _build_gremlin_widget(qtbot)

    idx = MatrixIndex(1, 1)
    center = widget._cell_rect(idx).center()
    outside = widget._matrix_rect().topLeft() - QtCore.QPoint(2, 2)
    outside = QtCore.QPoint(max(0, outside.x()), max(0, outside.y()))

    QtWidgets.QApplication.sendEvent(widget, _make_mouse_move_event(center))
    assert widget._hover_index == idx

    QtWidgets.QApplication.sendEvent(widget, _make_mouse_move_event(outside))
    assert widget._hover_index is None

    QtWidgets.QApplication.sendEvent(widget, _leave_event())
    assert widget._hover_index is None


def test_button_matrix_click_does_not_mutate_base_heatmap(qtbot):
    widget, original_df = _build_gremlin_widget(qtbot)

    original_base = widget._base_matrix.copy(deep=True)
    idx = MatrixIndex(2, 0)
    center = widget._cell_rect(idx).center()

    qtbot.mouseClick(widget, QtCore.Qt.MouseButton.LeftButton, pos=center)
    qtbot.wait(20)

    assert widget._selected_index == idx
    assert widget.df_matrix.equals(original_df)
    assert widget._base_matrix.equals(original_base)
    assert widget._busy_index == idx

    qtbot.wait(650)
    assert widget._busy_index is None


def test_button_matrix_paint_smoke(qtbot):
    widget, _ = _build_gremlin_widget(qtbot)

    widget.set_review_annotation(MatrixIndex(0, 0), True)
    widget.set_review_annotation(MatrixIndex(0, 2), False)
    widget._set_selected_index(MatrixIndex(1, 1))
    widget._set_hover_index(MatrixIndex(1, 2))
    widget.begin_busy(MatrixIndex(2, 1))
    widget._tick_busy_animation()

    pixmap = QtGui.QPixmap(widget.size())
    widget.render(pixmap)

    assert not pixmap.isNull()
    widget.end_busy()
