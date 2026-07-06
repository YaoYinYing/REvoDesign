#!/usr/bin/env python3
"""Transform REvoDesign.ui: absolute geometry → proper flow layouts.

Converts every tab page from hard-coded absolute widget positions to
QVBoxLayout-based flow layouts so the UI expands and breathes when resized.
Also wraps the centralwidget's top-bar group boxes in a QHBoxLayout.

Widget names, inner layouts, and all non-geometry properties are preserved.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

UI_PATH = Path(__file__).resolve().parent.parent.parent / "src" / "REvoDesign" / "UI" / "REvoDesign.ui"

TAB_RENAMES = {
    "tab_mutate": "Design",
    "tab_interact": "Co-evolution",
}


def _make_q_vbox_layout(name: str, spacing: int = 12, margin: int = 16) -> ET.Element:
    """Create a QVBoxLayout element with spacing and margins set."""
    layout = ET.Element("layout")
    layout.set("class", "QVBoxLayout")
    layout.set("name", name)

    sp = ET.SubElement(layout, "property")
    sp.set("name", "spacing")
    n = ET.SubElement(sp, "number")
    n.text = str(spacing)

    for mname in ("leftMargin", "topMargin", "rightMargin", "bottomMargin"):
        mp = ET.SubElement(layout, "property")
        mp.set("name", mname)
        mn = ET.SubElement(mp, "number")
        mn.text = str(margin)

    return layout


def _make_q_hbox_layout(name: str, spacing: int = 8) -> ET.Element:
    """Create a QHBoxLayout element."""
    layout = ET.Element("layout")
    layout.set("class", "QHBoxLayout")
    layout.set("name", name)

    sp = ET.SubElement(layout, "property")
    sp.set("name", "spacing")
    n = ET.SubElement(sp, "number")
    n.text = str(spacing)

    return layout


def _make_spacer_item(name: str) -> ET.Element:
    """Create a QSpacerItem that pushes content upward."""
    item = ET.Element("item")
    spacer = ET.SubElement(item, "spacer")
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

    return item


def _remove_geometry(widget: ET.Element) -> None:
    """Remove the <property name='geometry'> from a widget element."""
    for prop in list(widget):
        if prop.tag == "property" and prop.get("name") == "geometry":
            widget.remove(prop)
            return


def _extract_direct_child_widgets(parent: ET.Element) -> list[ET.Element]:
    """Find and remove all direct-child <widget> elements from parent.

    Returns the removed elements so they can be re-parented into a layout.
    """
    widgets = []
    for child in list(parent):
        if child.tag == "widget":
            widgets.append(child)
            parent.remove(child)
    return widgets


def _set_widget_property(widget: ET.Element, prop_name: str, value: str) -> None:
    """Set a simple string property on a widget."""
    for prop in widget.findall("property"):
        if prop.get("name") == prop_name:
            for child in list(prop):
                prop.remove(child)
            st = ET.SubElement(prop, "string")
            st.text = value
            return
    # Property doesn't exist — create it
    prop = ET.SubElement(widget, "property")
    prop.set("name", prop_name)
    st = ET.SubElement(prop, "string")
    st.text = value


def _set_geometry_rect(geom_element: ET.Element, x: int, y: int, w: int, h: int) -> None:
    """Update a <property name='geometry'> rect values."""
    for rect in geom_element.findall("rect"):
        for child in rect:
            if child.tag == "x":
                child.text = str(x)
            elif child.tag == "y":
                child.text = str(y)
            elif child.tag == "width":
                child.text = str(w)
            elif child.tag == "height":
                child.text = str(h)


def _find_geometry_prop(widget: ET.Element) -> ET.Element | None:
    """Find the geometry property element, or None."""
    for prop in widget:
        if prop.tag == "property" and prop.get("name") == "geometry":
            return prop
    return None


def transform_tab_pages(root: ET.Element) -> int:
    """Add QVBoxLayout to every tab_* QWidget page."""
    count = 0
    for widget in root.iter("widget"):
        name = widget.get("name", "")
        if not name.startswith("tab_"):
            continue

        child_widgets = _extract_direct_child_widgets(widget)
        if not child_widgets:
            continue

        # Remove geometry from each extracted widget
        for cw in child_widgets:
            _remove_geometry(cw)

        # Create layout with all child widgets
        layout = _make_q_vbox_layout(f"verticalLayout_{name}")
        for cw in child_widgets:
            item = ET.SubElement(layout, "item")
            item.append(cw)

        # Add bottom spacer so content doesn't stretch
        spacer = _make_spacer_item(f"verticalSpacer_{name}")
        layout.append(spacer)

        widget.append(layout)
        count += 1

    return count


def transform_central_widget(root: ET.Element) -> bool:
    """Wrap centralwidget children in QVBoxLayout + top-bar QHBoxLayout."""
    central = root.find(".//widget[@name='centralwidget']")
    if central is None:
        return False

    # Identify the top-row group boxes and the main tabWidget
    top_groups = []
    tab_widget = None
    progress_bar = None
    other_widgets = []

    for child in list(central):
        if child.tag != "widget":
            continue
        cname = child.get("name", "")
        if cname in ("groupBox_6", "groupBox_7", "groupBox_8"):
            top_groups.append(child)
            central.remove(child)
        elif cname == "tabWidget":
            tab_widget = child
            central.remove(child)
        elif cname == "progressBar":
            progress_bar = child
            central.remove(child)
        else:
            other_widgets.append(child)
            central.remove(child)

    if tab_widget is None:
        # Restore everything and bail
        for w in top_groups + other_widgets + ([progress_bar] if progress_bar else []):
            central.append(w)
        if tab_widget:
            central.append(tab_widget)
        return False

    # Create outer QVBoxLayout for centralwidget
    outer = _make_q_vbox_layout("verticalLayout_central", spacing=8, margin=10)

    # 1. Top bar: QHBoxLayout with groupBox_6, groupBox_7, groupBox_8
    top_bar_item = ET.SubElement(outer, "item")
    top_bar_layout = _make_q_hbox_layout("horizontalLayout_topbar", spacing=8)
    # Stretch factors: groupBox_6 gets more space, 7 and 8 are compact
    for gb in top_groups:
        _remove_geometry(gb)
        item = ET.SubElement(top_bar_layout, "item")
        item.append(gb)

    top_bar_item.append(top_bar_layout)

    # 2. Main tab widget (stretches to fill)
    tab_item = ET.SubElement(outer, "item")
    _remove_geometry(tab_widget)
    tab_item.append(tab_widget)

    # 3. Progress bar
    if progress_bar:
        prog_item = ET.SubElement(outer, "item")
        _remove_geometry(progress_bar)
        prog_item.append(progress_bar)

    # 4. Any other widgets
    for w in other_widgets:
        item = ET.SubElement(outer, "item")
        _remove_geometry(w)
        item.append(w)

    central.append(outer)
    return True


def rename_tabs(root: ET.Element) -> int:
    """Rename tab titles for clarity."""
    count = 0
    for widget in root.iter("widget"):
        name = widget.get("name", "")
        if name in TAB_RENAMES:
            for attr in widget.findall("attribute"):
                if attr.get("name") == "title":
                    for string in attr.findall("string"):
                        string.text = TAB_RENAMES[name]
                        count += 1
    return count


def update_window_size(root: ET.Element) -> bool:
    """Set default window to 900×650, minimum to 720×500."""
    main_window = root.find(".//widget[@name='REvoDesignPyMOL_UI']")
    if main_window is None:
        return False

    # Update geometry (initial size)
    geom = _find_geometry_prop(main_window)
    if geom is not None:
        _set_geometry_rect(geom, 0, 0, 900, 650)

    # Update minimumSize
    for prop in main_window.findall("property"):
        if prop.get("name") == "minimumSize":
            for size in prop.findall("size"):
                for child in size:
                    if child.tag == "width":
                        child.text = "720"
                    elif child.tag == "height":
                        child.text = "500"
            break

    # Update sizeIncrement to match
    for prop in main_window.findall("property"):
        if prop.get("name") == "sizeIncrement":
            for size in prop.findall("size"):
                for child in size:
                    if child.tag == "width":
                        child.text = "720"
            break

    # Update menubar geometry width
    menubar = root.find(".//widget[@name='menubar']")
    if menubar is not None:
        menubar_geom = _find_geometry_prop(menubar)
        if menubar_geom is not None:
            _set_geometry_rect(menubar_geom, 0, 0, 900, 37)

    return True


def main():
    print(f"Reading {UI_PATH} ...")
    tree = ET.parse(UI_PATH)
    root = tree.getroot()

    # 1. Transform tab pages
    n_tabs = transform_tab_pages(root)
    print(f"  → Added QVBoxLayout to {n_tabs} tab pages")

    # 2. Transform central widget
    ok = transform_central_widget(root)
    print(f"  → Central widget layout: {'OK' if ok else 'SKIPPED'}")

    # 3. Rename tab titles
    n_renames = rename_tabs(root)
    print(f"  → Renamed {n_renames} tab titles")

    # 4. Update window geometry
    ok = update_window_size(root)
    print(f"  → Window size 900×650: {'OK' if ok else 'SKIPPED'}")

    # Write
    ET.indent(tree, space="  ")
    tree.write(UI_PATH, encoding="utf-8", xml_declaration=True)
    print(f"Wrote {UI_PATH}")


if __name__ == "__main__":
    main()
