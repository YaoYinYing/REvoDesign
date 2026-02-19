# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


from pymol import cmd

from REvoDesign.shortcuts.tools.vina_tools import (
    enlargebox,
    get_oriented_bounding_box,
    get_pca_box,
    getbox,
    movebox,
    rmhet,
    showaxes,
)


def test_rmhet():
    cmd.reinitialize()

    cmd.fetch("1SUO")
    assert cmd.get_names() == ["1SUO"], "1SUO should be loaded"
    rmhet()

    het_removed = cmd.get_model("1SUO and hetatm").atom
    assert het_removed == [], "All hetatm should be removed"

    cmd.reinitialize()


def test_box_tools():
    cmd.reinitialize()
    cmd.fetch("1SUO")
    rmhet()
    cmd.select("sele", "resi 130+355+447")
    assert "sele" in cmd.get_names(type="selections"), "selection should be created"

    getbox()
    box_names = [b for b in cmd.get_names() if b.startswith("box_")]
    assert len(box_names) == 1, "Only one box should be created"

    box_names[0]

    cmd.reinitialize()


def test_movebox():
    cmd.reinitialize()
    cmd.fetch("1SUO")
    rmhet()
    cmd.select("sele", "resi 130+355+447")

    getbox()
    box_names = [b for b in cmd.get_names() if b.startswith("box_")]
    assert len(box_names) == 1, "Only one box should be created"

    box_name = box_names[0]

    box_coords = cmd.get_extent(box_name)

    movebox(box_name, x=1, y=2, z=3)
    box_names = [b for b in cmd.get_names() if b.startswith("box_")]
    assert len(box_names) == 1, "Only one box should be created"

    box_name_moved = box_names[0]
    assert box_name_moved == box_name, "Box name should not change"

    box_coords_move = cmd.get_extent(box_name_moved)

    assert box_coords != box_coords_move, "Box coordinates should change"

    cmd.reinitialize()


def test_enlargebox():
    cmd.reinitialize()
    cmd.fetch("1SUO")
    rmhet()
    cmd.select("sele", "resi 130+355+447")

    getbox()
    box_names = [b for b in cmd.get_names() if b.startswith("box_")]
    assert len(box_names) == 1, "Only one box should be created"

    box_name = box_names[0]

    box_coords = cmd.get_extent(box_name)

    enlargebox(box_name, x=1, y=2, z=3)
    box_names = [b for b in cmd.get_names() if b.startswith("box_")]
    assert len(box_names) == 1, "Only one box should be created"

    box_name_moved = box_names[0]
    assert box_name_moved == box_name, "Box name should not change"

    box_coords_move = cmd.get_extent(box_name_moved)

    assert box_coords != box_coords_move, "Box coordinates should change"

    cmd.reinitialize()


def test_get_pca_box():
    cmd.reinitialize()

    cmd.fetch("1SUO")
    rmhet()
    cmd.select("sele", "resi 130+355+447")

    get_pca_box(selection="sele", new_box_name="pca_box_test", extending=5.0)
    box_names = [b for b in cmd.get_names() if b.startswith("pca_box_")]
    assert len(box_names) == 1, "Only one box should be created"

    box_name = box_names[0]
    assert box_name == "pca_box_test", 'Box name should be exactly "pca_box_test"'

    cmd.reinitialize()


def test_showaxes():
    cmd.reinitialize()

    cmd.fetch("1SUO")

    showaxes()

    axes_names = [b for b in cmd.get_names() if b.startswith("axes")]

    box_name = axes_names[0]
    assert box_name == "axes", 'Axes name should be exactly "axes"'

    cmd.reinitialize()
