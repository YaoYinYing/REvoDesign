#!/usr/bin/env python3
"""Remove Qt Designer QWidget wrappers — move layouts directly onto parent group boxes.

The old pattern (Qt 4 era):
  QGroupBox → QWidget wrapper (fixed geometry) → QLayout → content

The new pattern:
  QGroupBox → QLayout → content

This makes inner content expand with the group box instead of being locked
at a fixed width/height.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

UI_PATH = Path(__file__).resolve().parent.parent.parent / "src" / "REvoDesign" / "UI" / "REvoDesign.ui"

WRAPPER_PREFIXES = (
    "verticalLayoutWidget",
    "horizontalLayoutWidget",
    "gridLayoutWidget",
    "layoutWidget",
)


def _find_wrapper_parent(root: ET.Element, wrapper: ET.Element) -> ET.Element | None:
    """Find the element (widget, item, or layout) that directly contains this wrapper."""
    # Check widget parents first (group boxes, pages)
    for parent in root.iter("widget"):
        for child in parent:
            if child is wrapper:
                return parent
    # Check layout items (wrappers inside QVBoxLayout/QHBoxLayout items)
    for parent in root.iter("item"):
        for child in parent:
            if child is wrapper:
                return parent
    return None


def transform():
    tree = ET.parse(UI_PATH)
    root = tree.getroot()

    wrappers = []
    for w in root.iter("widget"):
        name = w.get("name", "")
        if any(name.startswith(p) for p in WRAPPER_PREFIXES):
            wrappers.append(w)

    print(f"Found {len(wrappers)} layout wrapper widgets")

    count = 0
    removed_names = []

    for wrapper in wrappers:
        # Find the layout inside this wrapper
        layout = wrapper.find("layout")
        if layout is None:
            print(f"  SKIP {wrapper.get('name')}: no layout inside")
            continue

        # Find parent
        parent = _find_wrapper_parent(root, wrapper)
        if parent is None:
            print(f"  SKIP {wrapper.get('name')}: parent not found")
            continue

        layout_name = layout.get("name", "unnamed")
        wrapper_name = wrapper.get("name", "unnamed")
        parent_name = parent.get("name", "unnamed")

        # Remove wrapper from parent
        parent.remove(wrapper)

        # Add layout directly to parent
        parent.append(layout)

        removed_names.append(wrapper_name)
        count += 1
        print(f"  {parent_name}: {wrapper_name} → {layout_name}")

    if count > 0:
        ET.indent(tree, space="  ")
        tree.write(UI_PATH, encoding="utf-8", xml_declaration=True)
        print(f"\nRemoved {count} wrapper widgets, layouts moved to parents")
        print(f"Removed names: {', '.join(removed_names)}")
    else:
        print("No changes made")


if __name__ == "__main__":
    transform()
