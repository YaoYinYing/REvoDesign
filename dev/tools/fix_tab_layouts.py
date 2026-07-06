#!/usr/bin/env python3
"""Fix tabs that need side-by-side layouts (not blanket vertical stacking).

Cluster tab: QToolBox (left) || stackedWidget + Run button (right)
Socket tab: Two-column layout with full-width header
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

UI_PATH = Path(__file__).resolve().parent.parent.parent / "src" / "REvoDesign" / "UI" / "REvoDesign.ui"


def _make_layout_item(child: ET.Element) -> ET.Element:
    """Wrap an element in <item>...</item>."""
    item = ET.Element("item")
    item.append(child)
    return item


def _make_vbox_layout(name: str, spacing: int = 10, margins: tuple = (0, 0, 0, 0)) -> ET.Element:
    """Create a QVBoxLayout with spacing and margins."""
    layout = ET.Element("layout")
    layout.set("class", "QVBoxLayout")
    layout.set("name", name)
    for pname, pval in [
        ("spacing", str(spacing)),
        ("leftMargin", str(margins[0])),
        ("topMargin", str(margins[1])),
        ("rightMargin", str(margins[2])),
        ("bottomMargin", str(margins[3])),
    ]:
        prop = ET.SubElement(layout, "property")
        prop.set("name", pname)
        num = ET.SubElement(prop, "number")
        num.text = pval
    return layout


def _make_hbox_layout(name: str, spacing: int = 12, margins: tuple = (16, 16, 16, 16)) -> ET.Element:
    """Create a QHBoxLayout with spacing and margins."""
    layout = ET.Element("layout")
    layout.set("class", "QHBoxLayout")
    layout.set("name", name)
    for pname, pval in [
        ("spacing", str(spacing)),
        ("leftMargin", str(margins[0])),
        ("topMargin", str(margins[1])),
        ("rightMargin", str(margins[2])),
        ("bottomMargin", str(margins[3])),
    ]:
        prop = ET.SubElement(layout, "property")
        prop.set("name", pname)
        num = ET.SubElement(prop, "number")
        num.text = pval
    return layout


def _make_spacer(name: str) -> ET.Element:
    """Create a vertical spacer."""
    spacer = ET.Element("spacer")
    spacer.set("name", name)
    orient = ET.SubElement(spacer, "property")
    orient.set("name", "orientation")
    enum = ET.SubElement(orient, "enum")
    enum.text = "Qt::Vertical"
    hint = ET.SubElement(spacer, "property")
    hint.set("name", "sizeHint")
    hint.set("stdset", "0")
    sz = ET.SubElement(hint, "size")
    w = ET.SubElement(sz, "width")
    w.text = "20"
    h = ET.SubElement(sz, "height")
    h.text = "40"
    return spacer


def fix_cluster_tab(root: ET.Element) -> bool:
    """Convert cluster tab from vertical stack to side-by-side layout.

    Before: QVBoxLayout
      ├─ QToolBox (toolBox)
      ├─ QWidget wrapper (name="") → verticalLayout_5 → stackedWidget + Run
      └─ spacer

    After: QHBoxLayout
      ├─ QToolBox (toolBox)
      └─ QVBoxLayout (right panel)
           ├─ stackedWidget
           ├─ Run button
           └─ spacer
    """
    tc = root.find(".//widget[@name='tab_cluster']")
    if tc is None:
        print("  tab_cluster not found")
        return False

    old_layout = tc.find("layout")
    if old_layout is None:
        print("  tab_cluster has no layout")
        return False

    # Extract items from the old vertical layout
    items = list(old_layout.findall("item"))
    if len(items) < 2:
        print("  tab_cluster has too few items")
        return False

    # 1st item: QToolBox
    toolbox_item = items[0]
    toolbox_widget = toolbox_item.find("widget")
    if toolbox_widget is None or toolbox_widget.get("name") != "toolBox":
        print(f"  expected toolBox, got: {toolbox_widget.get('name') if toolbox_widget is not None else 'none'}")
        return False

    # 2nd item: empty-name QWidget wrapper containing verticalLayout_5
    wrapper_item = items[1]
    wrapper = wrapper_item.find("widget")
    if wrapper is None or wrapper.get("name") != "":
        print(f"  expected empty-name wrapper, got: {wrapper.get('name') if wrapper is not None else 'none'}")
        # Try to handle anyway
        right_content = list(wrapper_item)
    else:
        # Extract the inner layout from the wrapper
        inner_layout = wrapper.find("layout")
        if inner_layout is None:
            print("  wrapper has no inner layout")
            return False
        # Detach inner layout from wrapper
        wrapper.remove(inner_layout)
        right_content = [inner_layout]

    # Remove all items from old layout
    for item in items:
        old_layout.remove(item)

    # Remove the old layout from tab_cluster
    tc.remove(old_layout)

    # Build new QHBoxLayout
    new_layout = _make_hbox_layout(
        "horizontalLayout_tab_cluster",
        spacing=12,
        margins=(16, 16, 16, 16),
    )

    # Left: QToolBox
    left_item = ET.SubElement(new_layout, "item")
    left_item.append(toolbox_widget)

    # Right: QVBoxLayout (stackedWidget + Run + spacer)
    right_layout = _make_vbox_layout("verticalLayout_cluster_right", spacing=10)
    for child in right_content:
        right_layout.append(_make_layout_item(child))
    right_layout.append(_make_layout_item(_make_spacer("verticalSpacer_cluster_right")))

    right_item = ET.SubElement(new_layout, "item")
    right_item.append(right_layout)

    tc.append(new_layout)
    print(f"  Cluster tab: QVBoxLayout → QHBoxLayout (QToolBox || right panel)")
    return True


def fix_socket_tab(root: ET.Element) -> bool:
    """Restructure socket tab from simple vertical stack to two-column grid.

    Original layout (before blanket QVBoxLayout):
      [Team role (full width)]
      [Host options] [Client options]  (side by side)
      [Peer tree (full width)]
      [Broadcast] [Receive]  (side by side)

    Current: Everything vertically stacked. Fix by wrapping in a structure
    that alternates full-width rows with side-by-side pairs.
    """
    ts = root.find(".//widget[@name='tab_socket']")
    if ts is None:
        print("  tab_socket not found")
        return False

    layout = ts.find("layout")
    if layout is None:
        print("  tab_socket has no layout")
        return False

    items = list(layout.findall("item"))
    # Current order (vertically stacked):
    # groupBox_ws_server_settings, groupBox_ws_client_settings, groupBox_13,
    # treeWidget_ws_peers, groupBox_5, groupBox_12, spacer
    if len(items) < 6:
        print(f"  tab_socket has {len(items)} items, expected 6+")
        return False

    # Identify each widget
    def _get_widget(item):
        w = item.find("widget")
        return w.get("name") if w is not None else None

    widget_names = [_get_widget(it) for it in items]
    print(f"  Socket tab current order: {widget_names}")

    # Build a map: name → extracted widget element (detached from its item)
    widgets = {}
    for item in items:
        w = item.find("widget")
        if w is not None:
            name = w.get("name", "")
            # Detach from item
            item.remove(w)
            widgets[name] = w

    spacer_elem = None
    for item in items:
        sp = item.find("spacer")
        if sp is not None:
            item.remove(sp)
            spacer_elem = sp
            break

    # Remove all items from layout
    for item in items:
        layout.remove(item)

    # Now rebuild the socket tab layout:
    # Row 1 (full width): Team role (groupBox_13)
    # Row 2 (2 columns): groupBox_ws_server_settings | groupBox_ws_client_settings
    # Row 3 (full width): treeWidget_ws_peers
    # Row 4 (2 columns): groupBox_5 (Broadcast) | groupBox_12 (Receive)
    # Row 5: spacer

    # Row 1: Team role
    if "groupBox_13" in widgets:
        item1 = ET.SubElement(layout, "item")
        item1.append(widgets.pop("groupBox_13"))

    # Row 2: two columns
    row2 = ET.SubElement(layout, "item")
    row2_layout = _make_hbox_layout(
        "horizontalLayout_socket_row2", spacing=12, margins=(0, 0, 0, 0)
    )
    for name in ("groupBox_ws_server_settings", "groupBox_ws_client_settings"):
        if name in widgets:
            ri = ET.SubElement(row2_layout, "item")
            ri.append(widgets.pop(name))
    row2.append(row2_layout)

    # Row 3: Peer tree
    if "treeWidget_ws_peers" in widgets:
        item3 = ET.SubElement(layout, "item")
        item3.append(widgets.pop("treeWidget_ws_peers"))

    # Row 4: two columns
    row4 = ET.SubElement(layout, "item")
    row4_layout = _make_hbox_layout(
        "horizontalLayout_socket_row4", spacing=12, margins=(0, 0, 0, 0)
    )
    for name in ("groupBox_5", "groupBox_12"):
        if name in widgets:
            ri = ET.SubElement(row4_layout, "item")
            ri.append(widgets.pop(name))
    row4.append(row4_layout)

    # Any remaining widgets (shouldn't be any)
    for name, w in widgets.items():
        print(f"  WARNING: orphaned widget: {name}")
        item = ET.SubElement(layout, "item")
        item.append(w)

    # Spacer
    if spacer_elem is not None:
        sp_item = ET.SubElement(layout, "item")
        sp_item.append(spacer_elem)

    print(f"  Socket tab: rebuilt with 2 full-width + 2 two-column rows")
    return True


def fix_set_no_constraint(root: ET.Element) -> bool:
    """Remove SetNoConstraint from gridLayout_interact_pairs.

    This was needed when the layout was inside a fixed-geometry QWidget wrapper.
    Now that the wrapper is gone, the default constraint should apply.
    """
    for layout in root.iter("layout"):
        name = layout.get("name", "")
        if name == "gridLayout_interact_pairs":
            for prop in list(layout):
                if prop.tag == "property" and prop.get("name") == "sizeConstraint":
                    layout.remove(prop)
                    print(f"  Removed SetNoConstraint from {name}")
                    return True
    return False


def fix_geometry_in_toolbox_pages(root: ET.Element) -> int:
    """Remove geometry from widgets inside QToolBox pages (they're managed by QToolBox)."""
    count = 0
    for w in root.iter("widget"):
        name = w.get("name", "")
        if name.startswith("page_"):
            for child in list(w):
                if child.tag == "widget":
                    for prop in list(child):
                        if prop.tag == "property" and prop.get("name") == "geometry":
                            child.remove(prop)
                            count += 1
                            print(f"  Removed geometry from {child.get('name')} inside {name}")
    return count


def main():
    print("Reading UI...")
    tree = ET.parse(UI_PATH)
    root = tree.getroot()

    # 1. Fix cluster tab
    ok = fix_cluster_tab(root)
    print(f"  Cluster tab: {'OK' if ok else 'FAILED'}")

    # 2. Fix socket tab
    ok = fix_socket_tab(root)
    print(f"  Socket tab: {'OK' if ok else 'FAILED'}")

    # 3. Fix SetNoConstraint
    ok = fix_set_no_constraint(root)
    print(f"  SetNoConstraint fix: {'applied' if ok else 'not found'}")

    # 4. Remove geometry from QToolBox page children
    n = fix_geometry_in_toolbox_pages(root)
    print(f"  Toolbox page geometries removed: {n}")

    ET.indent(tree, space="  ")
    tree.write(UI_PATH, encoding="utf-8", xml_declaration=True)
    print("Done.")


if __name__ == "__main__":
    main()
