#!/usr/bin/env python3
"""Restore original layout design: side-by-side columns where the designer intended them.

Based on the original geometry (before blanket QVBoxLayout conversion), these tabs
had intentional two-column layouts:
  - tab_mutate:    full-width row + 2-col (left: 2 stacked, right: 2 stacked)
  - tab_evaluate:  full-width row + 2-col (left narrow, right wide)
  - tab_visualize: full-width row + 2-col (left narrow, right wide)
  - tab_interact:  2-col (grid left, right: 2 group boxes stacked)
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

UI_PATH = Path(__file__).resolve().parent.parent.parent / "src" / "REvoDesign" / "UI" / "REvoDesign.ui"


def _hbox(name: str, spacing: int = 12) -> ET.Element:
    """Create a QHBoxLayout with zero margins (for embedding in outer QVBoxLayout)."""
    layout = ET.Element("layout")
    layout.set("class", "QHBoxLayout")
    layout.set("name", name)
    for pname, pval in [
        ("spacing", str(spacing)),
        ("leftMargin", "0"), ("topMargin", "0"),
        ("rightMargin", "0"), ("bottomMargin", "0"),
    ]:
        prop = ET.SubElement(layout, "property")
        prop.set("name", pname)
        num = ET.SubElement(prop, "number")
        num.text = pval
    return layout


def _vbox(name: str, spacing: int = 8) -> ET.Element:
    """Create a QVBoxLayout with zero margins."""
    layout = ET.Element("layout")
    layout.set("class", "QVBoxLayout")
    layout.set("name", name)
    for pname, pval in [
        ("spacing", str(spacing)),
        ("leftMargin", "0"), ("topMargin", "0"),
        ("rightMargin", "0"), ("bottomMargin", "0"),
    ]:
        prop = ET.SubElement(layout, "property")
        prop.set("name", pname)
        num = ET.SubElement(prop, "number")
        num.text = pval
    return layout


def _item(child: ET.Element) -> ET.Element:
    """Wrap an element in <item>."""
    el = ET.Element("item")
    el.append(child)
    return el


def _extract_elements(layout: ET.Element) -> tuple[dict, object]:
    """Extract all children (widgets, nested layouts, spacers) from layout items.

    Returns (elements_dict, spacer) where elements_dict maps name→element.
    Nested layouts are keyed by their layout name.
    """
    elements = {}
    spacer = None
    for item in list(layout):
        # Check for widget child
        w = item.find("widget")
        if w is not None:
            name = w.get("name", "")
            item.remove(w)
            elements[name] = w
            continue
        # Check for nested layout child (e.g. gridLayout_interact_pairs)
        nl = item.find("layout")
        if nl is not None:
            name = nl.get("name", "")
            item.remove(nl)
            elements[name] = nl
            continue
        # Check for spacer
        sp = item.find("spacer")
        if sp is not None:
            item.remove(sp)
            spacer = sp
            continue
    return elements, spacer


def _clear_layout(layout: ET.Element) -> None:
    """Remove all items from a layout."""
    for item in list(layout):
        layout.remove(item)


def fix_tab(root: ET.Element, tab_name: str, builder) -> bool:
    """Generic: find tab, extract elements from its layout, rebuild via builder."""
    tab = root.find(f".//widget[@name='{tab_name}']")
    if tab is None:
        print(f"  {tab_name}: not found")
        return False

    layout = tab.find("layout")
    if layout is None:
        print(f"  {tab_name}: no layout")
        return False

    elements, spacer = _extract_elements(layout)
    _clear_layout(layout)

    success = builder(layout, elements, spacer)

    if success:
        print(f"  {tab_name}: rebuilt ✓")
    else:
        print(f"  {tab_name}: builder failed, restoring as vertical stack")
        for name, elem in elements.items():
            layout.append(_item(elem))
        if spacer is not None:
            layout.append(_item(spacer))

    return success


def build_mutate(layout, elements, spacer):
    """Original: full-width top + 2-column bottom.

    Row 1: [groupBox_4 (full width, Input Profile)]
    Row 2: QHBoxLayout
             Left QVBoxLayout:  [groupBox_2] [groupBox_reject_substitution]
             Right QVBoxLayout: [groupBox]    [groupBox_11]
    """
    if "groupBox_4" in elements:
        layout.append(_item(elements.pop("groupBox_4")))

    row2 = _hbox("horizontalLayout_mutate_row2")
    left = _vbox("verticalLayout_mutate_left")
    right = _vbox("verticalLayout_mutate_right")

    for name in ("groupBox_2", "groupBox_reject_substitution"):
        if name in elements:
            left.append(_item(elements.pop(name)))
    for name in ("groupBox", "groupBox_11"):
        if name in elements:
            right.append(_item(elements.pop(name)))

    row2.append(_item(left))
    row2.append(_item(right))
    layout.append(_item(row2))

    _append_remaining(layout, elements, spacer)
    return True


def build_evaluate(layout, elements, spacer):
    """Original: full-width top + 2-column bottom.

    Row 1: [groupBox_IO_2 (full width, Save & Load)]
    Row 2: QHBoxLayout
             [groupBox_design_status (left, narrower)] [groupBox_choice (right, wider)]
    """
    if "groupBox_IO_2" in elements:
        layout.append(_item(elements.pop("groupBox_IO_2")))

    row2 = _hbox("horizontalLayout_evaluate_row2")
    for name in ("groupBox_design_status", "groupBox_choice"):
        if name in elements:
            row2.append(_item(elements.pop(name)))
    layout.append(_item(row2))

    _append_remaining(layout, elements, spacer)
    return True


def build_visualize(layout, elements, spacer):
    """Original: full-width top + 2-column bottom.

    Row 1: [groupBox_20 (full width, Input & Output)]
    Row 2: QHBoxLayout
             [groupBox_21 (left, narrower)] [groupBox_10 (right, wider)]
    """
    if "groupBox_20" in elements:
        layout.append(_item(elements.pop("groupBox_20")))

    row2 = _hbox("horizontalLayout_visualize_row2")
    for name in ("groupBox_21", "groupBox_10"):
        if name in elements:
            row2.append(_item(elements.pop(name)))
    layout.append(_item(row2))

    _append_remaining(layout, elements, spacer)
    return True


def build_interact(layout, elements, spacer):
    """Original: 2-column.

    Left:  gridLayout_interact_pairs (co-evolved pairs table)
    Right: QVBoxLayout [groupBox_22 (GREMLIN profile)] [groupBox_9 (interaction settings)]
    """
    row = _hbox("horizontalLayout_interact")

    # gridLayout_interact_pairs is a <layout> element (wrapper was removed)
    if "gridLayout_interact_pairs" in elements:
        row.append(_item(elements.pop("gridLayout_interact_pairs")))

    right = _vbox("verticalLayout_interact_right")
    for name in ("groupBox_22", "groupBox_9"):
        if name in elements:
            right.append(_item(elements.pop(name)))
    row.append(_item(right))

    layout.append(_item(row))
    _append_remaining(layout, elements, spacer)
    return True


def _append_remaining(layout, elements, spacer):
    """Append any unclaimed elements and the spacer to the layout."""
    for name, elem in elements.items():
        layout.append(_item(elem))
    if spacer is not None:
        layout.append(_item(spacer))


def main():
    print("Reading UI...")
    tree = ET.parse(UI_PATH)
    root = tree.getroot()

    fix_tab(root, "tab_mutate", build_mutate)
    fix_tab(root, "tab_evaluate", build_evaluate)
    fix_tab(root, "tab_visualize", build_visualize)
    fix_tab(root, "tab_interact", build_interact)

    ET.indent(tree, space="  ")
    tree.write(UI_PATH, encoding="utf-8", xml_declaration=True)
    print("Done.")


if __name__ == "__main__":
    main()
