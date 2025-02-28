'''

GetBox Plugin.py --  Draws a box surrounding a selection and gets box information
get latest plugin and tutorials at https://github.com/MengwuXiao/Getbox-PyMOL-Plugin

Usages:
this plugin is a simple tool to get box information for LeDock and Autodock Vina or other molecular docking soft. Using the following functions to get box is recommended.

* getbox [selection = (sele), [extending = 5.0]]
    this function creates a box that around the selected objects (residues or ligands or HOH or others). Selecting ligands or residues in the active cavity reported in papers is recommended
    e.g. getbox
    e.g. getbox (sele), 6.0

* showbox [minX, maxX, minY, maxY, minZ, maxZ]
    this function creates a box based on the input axis, used to visualize box or amend box coordinate
    e.g. showbox 2,3,4,5,6,7

 * rmhet
 	remove HETATM, remove all HETATM in the screen

Notes:
* If you have any questions or advice, please do not hesitate to contact me (mwxiao AT hnu DOT edu DOT cn), thank you!


'''
from dataclasses import dataclass
from functools import cached_property
from random import randint
from typing import Optional, Tuple, Union, overload

from chempy import cpv
from pymol import cgo, cmd
from pymol.vfont import plain

##############################################################################
# GetBox Plugin.py --  Draws a box surrounding a selection and gets box information
# This script is used to get box information for LeDock, Autodock Vina and AutoDock Vina.
# Copyright (C) 2014 by Mengwu Xiao (Hunan University)
#
# USAGES:  See function GetBoxHelp()
# REFERENCE:  drawBoundingBox.py  written by  Jason Vertrees
# EMAIL: mwxiao AT hnu DOT edu DOT cn
# Changes:
# 2014-07-30 first version was uploaded to BioMS http://bioms.org/forum.php?mod=viewthread&tid=1234
# 2018-02-04 uploaded to GitHub https://github.com/MengwuXiao/Getbox-PyMOL-Plugin
#            fixed some bugs: python 2/3 and PyMOL 1.x are supported;
#            added support to AutoDock;
#            added tutorials in English;
# NOTES:
# This program is free software; you can redistribute it and/or modify it under the terms of the GNU
# General Public License as published by the Free Software Foundation version 3 of the License.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
# even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See
# the GNU General Public License for more details.
##############################################################################

# ref: https://pymolwiki.org/index.php/Axes


class PutCenterCallback:
    """
    A class to dynamically adjust the position of an object in PyMOL to keep it centered in the view.

    Attributes:
    - prev_v: Stores the previous view matrix to detect changes in the view.
    """

    prev_v = None

    def __init__(self, name, corner=0):
        """
        Initializes the PutCenterCallback instance.

        Parameters:
        - name (str): The name of the object to be centered.
        - corner (int, optional): Specifies the corner for offset adjustments. Defaults to 0.
        """
        self.name = name
        self.corner = corner
        self.cb_name = cmd.get_unused_name('_cb')

    def load(self):
        """
        Loads the callback into PyMOL.
        """
        cmd.load_callback(self, self.cb_name)

    def __call__(self):
        """
        Executes the callback logic when called.

        This method ensures that the specified object remains centered in the view. If the object is deleted,
        it removes the callback. It also applies an offset based on the specified corner.
        """
        if self.name not in cmd.get_names('objects'):
            # Remove the callback if the object no longer exists
            import threading
            threading.Thread(None, cmd.delete, args=(self.cb_name,)).start()
            return

        v = cmd.get_view()
        if v == self.prev_v:
            return
        self.prev_v = v

        t = v[12:15]

        if self.corner:
            # Calculate offset based on the viewport and corner
            vp = cmd.get_viewport()
            R_mc = [v[0:3], v[3:6], v[6:9]]
            off_c = [0.15 * v[11] * vp[0] / vp[1], 0.15 * v[11], 0.0]
            if self.corner in [2, 3]:
                off_c[0] *= -1
            if self.corner in [3, 4]:
                off_c[1] *= -1
            off_m = cpv.transform(R_mc, off_c)
            t = cpv.add(t, off_m)

        z = -v[11] / 30.0
        m = [z, 0, 0, 0, 0, z, 0, 0, 0, 0, z, 0, t[0] / z, t[1] / z, t[2] / z, 1]
        cmd.set_object_ttt(self.name, m)

# ref: https://pymolwiki.org/index.php/Axes


@dataclass
class CgoAxes:
    """
    A class for creating and displaying a set of axes in a 3D visualization environment.

    Attributes:
        name (str): The name of the axes object.
        w (float): The width of the cylinder.
        l (float): The length of the cylinder.
        h (float): The height of the cone.
        always_left_corner (bool): Determines if the axes should always be displayed in the corner.
        show_labels (bool): Determines if labels should be displayed on the axes.
        label_weight (float): The thickness of the labels.
        label_size (float): The size of the labels.
    """

    # Default attribute values
    name: str = "axes"
    w: float = 0.06  # cylinder width
    l: float = 0.75  # cylinder length
    h: float = 0.25  # cone hight

    always_left_corner: bool = True
    show_labels: bool = True
    label_weight: float = 0.05
    label_size: float = 0.5

    def __post_init__(self):
        """
        Post-initialization processing.
        If an object with the same name already exists, it is deleted.
        Ensures the data types of attributes are as expected.
        """
        # Delete existing object with the same name to avoid conflicts
        if self.name in cmd.get_names("objects"):
            cmd.delete(self.name)

        # Ensure attributes are of the correct type
        self.w = float(self.w)
        self.l = float(self.l)
        self.h = float(self.h)
        self.always_left_corner = bool(self.always_left_corner)

    @cached_property
    def d(self):
        """
        Calculates and returns the diameter of the cone base.

        Returns:
            float: The diameter of the cone base.
        """
        return self.w * 1.618  # cone base diameter

    @cached_property
    def as_cgo_obj(self):
        """
        Generates and returns a CGO object representing the axes.

        Returns:
            list: A list of CGO commands to draw the axes.
        """
        return [
            cgo.CYLINDER, 0.0, 0.0, 0.0, self.l, 0.0, 0.0, self.w, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0,
            cgo.CYLINDER, 0.0, 0.0, 0.0, 0.0, self.l, 0.0, self.w, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0,
            cgo.CYLINDER, 0.0, 0.0, 0.0, 0.0, 0.0, self.l, self.w, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0,
            cgo.CONE, self.l, 0.0, 0.0, self.h + self.l, 0.0, 0.0, self.d, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0,
            cgo.CONE, 0.0, self.l, 0.0, 0.0, self.h + self.l, 0.0, self.d, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 1.0, 1.0,
            cgo.CONE, 0.0, 0.0, self.l, 0.0, 0.0, self.h + self.l, self.d, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 1.0
        ]

    def set_label(self):
        """
        Sets labels on the axes if show_labels is True.
        """
        obj = self.as_cgo_obj
        label_axis = [[self.label_size, 0, 0], [0, self.label_size, 0], [0, 0, self.label_size]]
        # Add labels to the axes
        cgo.cyl_text(obj, plain, [self.l + self.h, 0, - self.w], 'X', self.label_weight, axes=label_axis)
        cgo.cyl_text(obj, plain, [-self.w, self.l + self.h, 0], 'Y', self.label_weight, axes=label_axis)
        cgo.cyl_text(obj, plain, [-self.w, 0, self.l + self.h], 'Z', self.label_weight, axes=label_axis)

    def show(self):
        """
        Displays the axes in the visualization environment.
        Adjusts settings based on the values of always_left_corner and show_labels.
        """
        # Disable auto zoom to maintain a fixed view
        cmd.set('auto_zoom', 0)
        # Position the axes in the corner if always_left_corner is True
        if self.always_left_corner:
            PutCenterCallback(self.name, 1).load()
        # Display labels if show_labels is True
        if self.show_labels:
            self.set_label()
        # Load the CGO object into the visualization environment
        cmd.load_cgo(self.as_cgo_obj, self.name)


def showaxes():
    axes = CgoAxes()
    axes.show()

# ref: https://github.com/MengwuXiao/GetBox-PyMOL-Plugin/blob/master/GetBox%20Plugin.py


@dataclass
class CgoBox:
    """
    Represents a box object for visualization in PyMOL, with properties for size, center, and colored lines.

    Attributes:
        name (str): The name of the box object.
        minX (float): The minimum X coordinate of the box.
        maxX (float): The maximum X coordinate of the box.
        minY (float): The minimum Y coordinate of the box.
        maxY (float): The maximum Y coordinate of the box.
        minZ (float): The minimum Z coordinate of the box.
        maxZ (float): The maximum Z coordinate of the box.

        linewidth (float): The width of the box.

        colorX (Tuple[float, float, float]): The color of the box in RGB format on X axis.
        colorY( Tuple[float, float, float]): The color of the box in RGB format on Y axis.
        colorZ (Tuple[float, float, float]): The color of the box in RGB format on Z axis.


    """
    name: str

    minX: float
    maxX: float

    minY: float
    maxY: float

    minZ: float
    maxZ: float
    linewidth: float = 5.0

    colorX: Tuple[float, float, float] = (1.0, 0.0, 0.0,)
    colorY: Tuple[float, float, float] = (0.0, 1.0, 0.0,)
    colorZ: Tuple[float, float, float] = (0.0, 0.0, 1.0,)

    def __post_init__(self):
        """
        Post-initialization processing. Deletes existing objects with the same name and ensures all coordinates are floats.
        """
        if self.name in cmd.get_names():
            cmd.delete(self.name)
        self.minX = float(self.minX)
        self.maxX = float(self.maxX)
        self.minY = float(self.minY)
        self.maxY = float(self.maxY)
        self.minZ = float(self.minZ)
        self.maxZ = float(self.maxZ)
        self.linewidth = float(self.linewidth)

    @cached_property
    def SizeX(self):
        """
        Calculates the size of the box along the X-axis.
        """
        return self.maxX - self.minX

    @cached_property
    def SizeY(self):
        """
        Calculates the size of the box along the Y-axis.
        """
        return self.maxY - self.minY

    @cached_property
    def SizeZ(self):
        """
        Calculates the size of the box along the Z-axis.
        """
        return self.maxZ - self.minZ

    @cached_property
    def CenterX(self):
        """
        Calculates the center point of the box along the X-axis.
        """
        return (self.maxX + self.minX) / 2

    @cached_property
    def CenterY(self):
        """
        Calculates the center point of the box along the Y-axis.
        """
        return (self.maxY + self.minY) / 2

    @cached_property
    def CenterZ(self):
        """
        Calculates the center point of the box along the Z-axis.
        """
        return (self.maxZ + self.minZ) / 2

    @cached_property
    def x_cgo_lines(self):
        """
        Generates the CGO line commands for the X-axis lines of the box.
        """
        return [
            cgo.COLOR, *self.colorX,
            cgo.VERTEX, self.minX, self.minY, self.minZ,  # 1
            cgo.VERTEX, self.maxX, self.minY, self.minZ,  # 5

            cgo.VERTEX, self.minX, self.maxY, self.minZ,  # 3
            cgo.VERTEX, self.maxX, self.maxY, self.minZ,  # 7

            cgo.VERTEX, self.minX, self.maxY, self.maxZ,  # 4
            cgo.VERTEX, self.maxX, self.maxY, self.maxZ,  # 8

            cgo.VERTEX, self.minX, self.minY, self.maxZ,  # 2
            cgo.VERTEX, self.maxX, self.minY, self.maxZ,  # 6
        ]

    @cached_property
    def y_cgo_lines(self):
        """
        Generates the CGO line commands for the Y-axis lines of the box.
        """
        return [
            cgo.COLOR, *self.colorY,  # green
            cgo.VERTEX, self.minX, self.minY, self.minZ,  # 1
            cgo.VERTEX, self.minX, self.maxY, self.minZ,  # 3

            cgo.VERTEX, self.maxX, self.minY, self.minZ,  # 5
            cgo.VERTEX, self.maxX, self.maxY, self.minZ,  # 7

            cgo.VERTEX, self.minX, self.minY, self.maxZ,  # 2
            cgo.VERTEX, self.minX, self.maxY, self.maxZ,  # 4

            cgo.VERTEX, self.maxX, self.minY, self.maxZ,  # 6
            cgo.VERTEX, self.maxX, self.maxY, self.maxZ,  # 8
        ]

    @cached_property
    def z_cgo_lines(self):
        """
        Generates the CGO line commands for the Z-axis lines of the box.
        """
        return [
            cgo.COLOR, *self.colorZ,  # blue
            cgo.VERTEX, self.minX, self.minY, self.minZ,  # 1
            cgo.VERTEX, self.minX, self.minY, self.maxZ,  # 2

            cgo.VERTEX, self.minX, self.maxY, self.minZ,  # 3
            cgo.VERTEX, self.minX, self.maxY, self.maxZ,  # 4

            cgo.VERTEX, self.maxX, self.minY, self.minZ,  # 5
            cgo.VERTEX, self.maxX, self.minY, self.maxZ,  # 6

            cgo.VERTEX, self.maxX, self.maxY, self.minZ,  # 7
            cgo.VERTEX, self.maxX, self.maxY, self.maxZ,  # 8
        ]

    @cached_property
    def as_cgo_obj(self):
        """
        Combines all CGO line commands into a single list to represent the entire box object.
        """
        # who on earth makes this shit???
        return [
            cgo.LINEWIDTH, float(self.linewidth),
            cgo.BEGIN, cgo.LINES,
            *self.x_cgo_lines,
            *self.y_cgo_lines,
            *self.z_cgo_lines,
            cgo.END,
        ]

    @property
    def to_vina(self):
        """
        Generates a string of parameters for configuring a binding site in AutoDock Vina.
        """
        return f"""--center_x {self.CenterX:.1f} --center_y {self.CenterY:.1f} --center_z {self.CenterZ:.1f} --size_x {self.SizeX:.1f} --size_y {self.SizeY:.1f} --size_z {self.CenterZ:.1f}"""

    @property
    def to_autogrid(self):
        """
        Generates a string of parameters for configuring a grid in AutoGrid.
        """
        return f""""npts {self.SizeX / 0.375} {self. SizeY / 0.375} {self.SizeZ / 0.375} # num. grid points in xyz
spacing 0.375 # spacing (A)
gridcenter {self.CenterX:.3f} {self.CenterY:.3f} {self.CenterZ:.3f} # xyz-coordinates or auto"""

    @property
    def to_ledock(self):
        """
        Generates a string of parameters for specifying a binding pocket in LeDock.
        """
        return f"""Binding pocket
{self.minX:.1f} {self.maxX:.1f}
{self.minY:.1f} {self.maxY:.1f}
{self.minZ:.1f} {self.maxZ:.1f}
"""

    def load_to_pymol(self):
        """
        Loads the CGO object into PyMOL for visualization.
        """
        cmd.load_cgo(self.as_cgo_obj, self.name, quiet=0)

    def __repr__(self) -> str:
        """
        Provides a string representation of the box, including its coordinates, size, and center.
        """
        return f"""CgoBox `{self.name}`:
Coordinates: {self.minX:.3f} - {self.maxX:.3f}; {self.minY:.3f} - {self.maxY:.3f}, {self.minZ:.3f} - {self.maxZ:.3f}
Size: {self.SizeX:.3f} * {self.SizeY:.3f} * {self.SizeZ:.3f} = {self.SizeX * self.SizeY * self.SizeZ:.3f}
Center: {self.CenterX:.3f}, {self.CenterY:.3f}, {self.CenterZ:.3f}"""

    @classmethod
    def from_selecion(
            cls,
            selection: str = "(sele)",
            box_name: Optional[str] = None,
            extending: float = 5.0,
            offset: Tuple[float, float, float] = (0, 0, 0)):
        """
        Creates a box object from a PyMOL selection, with optional name, extension, and offset.
        """
        if not box_name:
            boxName = "box_" + str(randint(0, 10000))
            while boxName in cmd.get_names():
                boxName = "box_" + str(randint(0, 10000))
        else:
            boxName = box_name

        ([minX, minY, minZ], [maxX, maxY, maxZ]) = cmd.get_extent(selection)

        minX = minX - extending + offset[0]
        minY = minY - extending + offset[1]
        minZ = minZ - extending + offset[2]

        maxX = maxX + extending + offset[0]
        maxY = maxY + extending + offset[1]
        maxZ = maxZ + extending + offset[2]

        box = cls(
            name=boxName,
            minX=minX,
            minY=minY,
            minZ=minZ,
            maxX=maxX,
            maxY=maxY,
            maxZ=maxZ,
        )
        print(repr(box))
        return box


@overload
def showbox(
    box: str,
    minX: float,
    maxX: float,
    minY: float,
    maxY: float,
    minZ: float,
    maxZ: float

): ...


@overload
def showbox(box: CgoBox,
            minX: Optional[float] = None,
            maxX: Optional[float] = None,
            minY: Optional[float] = None,
            maxY: Optional[float] = None,
            minZ: Optional[float] = None,
            maxZ: Optional[float] = None): ...


def showbox(
        box: Union[str, CgoBox],
        minX: Optional[float] = None,
        maxX: Optional[float] = None,
        minY: Optional[float] = None,
        maxY: Optional[float] = None,
        minZ: Optional[float] = None,
        maxZ: Optional[float] = None):
    """
    Displays box information and loads it into PyMOL.

    Args:
        box (Union[str, CgoBox]): Either a string representing the name of the box or a CgoBox object.
        minX (Optional[float], optional): Minimum X coordinate. Defaults to None.
        maxX (Optional[float], optional): Maximum X coordinate. Defaults to None.
        minY (Optional[float], optional): Minimum Y coordinate. Defaults to None.
        maxY (Optional[float], optional): Maximum Y coordinate. Defaults to None.
        minZ (Optional[float], optional): Minimum Z coordinate. Defaults to None.
        maxZ (Optional[float], optional): Maximum Z coordinate. Defaults to None.

    Raises:
        ValueError: If `box` is a string and any of the coordinates are not provided.

    Returns:
        CgoBox: The created or modified CgoBox object.
    """
    # Display axes in PyMOL
    showaxes()

    if isinstance(box, str):
        # Validate that all required coordinates are provided when box is a string
        if any(x is None for x in [minX, maxX, minY, maxY, minZ, maxZ]):
            raise ValueError("To make a box, you must specify minX, maxX, minY, maxY, minZ, maxZ as valid floats.")
        # Create a new CgoBox object from provided parameters
        box = CgoBox(
            name=box,
            minX=minX,
            minY=minY,
            minZ=minZ,
            maxX=maxX,
            maxY=maxY,
            maxZ=maxZ,
        )

    # Print box details in different formats
    print('*' * 45, 'AutoDock Vina', '*' * 45, '\n', box.to_vina, '\n\n')
    print('*' * 45, 'AutoGrid', '*' * 45, '\n', box.to_autogrid, '\n\n')
    print('*' * 45, 'LeDock', '*' * 45, '\n', box.to_ledock, '\n\n')

    # Load the box into PyMOL
    box.load_to_pymol()
    return box


def movebox(box_name: str, x: float = 0, y: float = 0, z: float = 0):
    """
    Moves an existing box by specified offsets in the X, Y, and Z directions.

    Args:
        box_name (str): The name of the box to be moved.
        x (float, optional): Offset in the X direction. Defaults to 0.
        y (float, optional): Offset in the Y direction. Defaults to 0.
        z (float, optional): Offset in the Z direction. Defaults to 0.
    """
    if all(i == 0 for i in [x, y, z]):
        print("No movement specified")
        return

    # Create a new box with the specified offsets
    new_box = CgoBox.from_selecion(
        selection=box_name,
        box_name=box_name,
        extending=0,
        offset=(float(x), float(y), float(z)))

    # Load the new box into PyMOL
    new_box.load_to_pymol()


def enlargebox(box_name: str, x: float = 0, y: float = 0, z: float = 0):
    """
    Enlarges or truncates an existing box by specified amounts in the X, Y, and Z directions.

    Args:
        box_name (str): The name of the box to be enlarged or truncated.
        x (float, optional): Amount to enlarge/truncate in the X direction. Defaults to 0.
        y (float, optional): Amount to enlarge/truncate in the Y direction. Defaults to 0.
        z (float, optional): Amount to enlarge/truncate in the Z direction. Defaults to 0.
    """
    if all(i == 0 for i in [x, y, z]):
        print("No enlargement/truncation specified")
        return

    # Create a new box without extending
    new_box = CgoBox.from_selecion(
        selection=box_name,
        box_name=box_name,
        extending=0)

    # Modify the box dimensions based on the specified amounts
    if x:
        x = float(x)
        new_box.minX = new_box.minX - x / 2
        new_box.maxX = new_box.maxX + x / 2
    if y:
        y = float(y)
        new_box.minY = new_box.minY - y / 2
        new_box.maxY = new_box.maxY + y / 2
    if z:
        z = float(z)
        new_box.minZ = new_box.minZ - z / 2
        new_box.maxZ = new_box.maxZ + z / 2

    # Load the modified box into PyMOL
    new_box.load_to_pymol()


def getbox(selection="(sele)", new_box_name: Optional[str] = None, extending=5.0):
    """
    Creates a box based on a selection and displays it in PyMOL.

    Args:
        selection (str, optional): The selection criteria for creating the box. Defaults to "(sele)".
        new_box_name (Optional[str], optional): The name of the new box. Defaults to None.
        extending (float, optional): The amount to extend the box beyond the selection. Defaults to 5.0.
    """
    cmd.hide("spheres")
    cmd.show("spheres", selection)
    showaxes()

    # Create a new box from the selection
    box = CgoBox.from_selecion(selection=selection, box_name=new_box_name, extending=extending)

    # Display the box
    showbox(box)

    boxName = box.name
    print(f'{boxName=}')
    cmd.zoom(boxName)
    return

# remove ions


def removeions():
    cmd.select("Ions", "((resn PO4) | (resn SO4) | (resn ZN) | (resn CA) | (resn MG) | (resn CL)) & hetatm")
    cmd.remove("Ions")
    cmd.delete("Ions")
    return


def rmhet(extending=5.0):
    cmd.select("rmhet", "hetatm")
    cmd.remove("rmhet")
    return

# getbox from cavity residues that reported in papers
