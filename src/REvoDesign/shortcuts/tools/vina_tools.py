'''

GetBox Plugin.py --  Draws a box surrounding a selection and gets box information

'''
from dataclasses import dataclass
from random import randint
from typing import Dict, Literal, Optional, Tuple, Union, overload

import numpy as np
from chempy import cpv
from pymol import cgo, cmd
from pymol.vfont import plain

from REvoDesign.logger import ROOT_LOGGER
from REvoDesign.Qt import QtCore, QtGui, QtWidgets

from ...tools.cgo_utils import Cone, Cube, Cylinder, GraphicObject
from ...tools.cgo_utils import GraphicObjectCollection as GOC
from ...tools.cgo_utils import LineVertex, Point, PolyLines, Sphere

logging = ROOT_LOGGER.getChild(__name__)
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
class CgoAxes(GraphicObject):
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

    def rebuild(self):
        """
        Post-initialization processing.
        If an object with the same name already exists, it is deleted.
        Ensures the data types of attributes are as expected.
        """

        # Ensure attributes are of the correct type
        self.w = float(self.w)
        self.l = float(self.l)
        self.h = float(self.h)
        self.always_left_corner = bool(self.always_left_corner)

        self._data = []
        for (idxa, axis), (idxc, colorname) in zip(enumerate('xyz'), enumerate('rgb')):
            p2_kwargs = {i: 0.0 for i in 'xyz' if i != axis}
            self._data.extend(
                Cylinder(
                    Point(0.0, 0.0, 0.0),  # p1
                    Point(**p2_kwargs, **{axis: self.l}),  # p2
                    self.w,
                    colorname, colorname
                ).data,
            )
            self._data.extend(
                Cone(
                    base_center=Point(**p2_kwargs, **{axis: self.l}),
                    tip=Point(**p2_kwargs, **{axis: self.l + self.h}),
                    radius_tip=0, radius_base=self.d,
                    caps=(1, 1), color_base=colorname, color_tip=colorname
                ).data,
            )

    @property
    def d(self):
        """
        Calculates and returns the diameter of the cone base.

        Returns:
            float: The diameter of the cone base.
        """
        return self.w * 1.618  # cone base diameter

    def set_label(self):
        """
        Sets labels on the axes if show_labels is True.
        """
        obj = self.data
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
        cmd.load_cgo(self.data, self.name)


def showaxes():
    axes = CgoAxes()
    axes.show()

# ref: https://github.com/MengwuXiao/GetBox-PyMOL-Plugin/blob/master/GetBox%20Plugin.py


# Problem: the class draw the box with edges align to axes
@dataclass
class CgoBox(GraphicObject):
    """
    Represents a box object for visualization in PyMOL, with properties for size, center, and colored lines.

    """
    name: str

    p1: Point
    p2: Point
    linewidth: float = 5.0

    color_x: str = 'red'
    color_y: str = 'green'
    color_z: str = 'blue'

    def rebuild(self):
        """
        Post-initialization processing. Deletes existing objects with the same name and ensures all coordinates are floats.
        """

        self.delta_xyz = tuple(abs(x) for x in self.p1.delta_xyz(self.p2))
        self.center_xyz = self.p1.center_xyz(self.p2)

        self.cube = Cube(
            p1=self.p1,
            p2=self.p2,
            color_x=self.color_x,
            color_y=self.color_y,
            color_z=self.color_z,
            wire_frame=True,
            linewidth=self.linewidth
        )
        self._data = self.cube.data

    @property
    def to_vina(self):
        """
        Generates a string of parameters for configuring a binding site in AutoDock Vina.
        """
        return f"""--center_x {self.center_xyz[0]:.1f} --center_y {self.center_xyz[1]:.1f} --center_z {self.center_xyz[2]:.1f} --size_x {self.delta_xyz[0]:.1f} --size_y {self.delta_xyz[1]:.1f} --size_z {self.delta_xyz[2]:.1f}"""

    @property
    def to_autogrid(self):
        """
        Generates a string of parameters for configuring a grid in AutoGrid.
        """
        return f""""npts {self.delta_xyz[0] / 0.375} {self.delta_xyz[1] / 0.375} {self.delta_xyz[2] / 0.375} # num. grid points in xyz
spacing 0.375 # spacing (A)
gridcenter {self.center_xyz[0]:.3f} {self.center_xyz[1]:.3f} {self.center_xyz[2]:.3f} # xyz-coordinates or auto"""

    @property
    def to_ledock(self):
        """
        Generates a string of parameters for specifying a binding pocket in LeDock.
        """
        return f"""Binding pocket
{self.p1.x:.1f} {self.p2.x:.1f}
{self.p1.y:.1f} {self.p2.y:.1f}
{self.p1.z:.1f} {self.p2.z:.1f}
"""

    def load_to_pymol(self):
        """
        Loads the CGO object into PyMOL for visualization.
        """

        self.cube.load_as(self.name)

    def __repr__(self) -> str:
        """
        Provides a string representation of the box, including its coordinates, size, and center.
        """
        return f"""CgoBox `{self.name}`:
Coordinates: {self.p1.x:.3f} - {self.p2.x:.3f}; {self.p1.y:.3f} - {self.p2.y:.3f}, {self.p1.z:.3f} - {self.p2.z:.3f}
Size: {self.delta_xyz[0]:.3f} * {self.delta_xyz[1]:.3f} * {self.delta_xyz[2]:.3f} = {self.delta_xyz[0] * self.delta_xyz[1] * self.delta_xyz[2]:.3f}
Center: {self.center_xyz[0]:.3f}, {self.center_xyz[1]:.3f}, {self.center_xyz[2]:.3f}"""

    @classmethod
    def from_selection(
            cls,
            selection: str = "(sele)",
            box_name: Optional[str] = None,
            extending: float = 5.0,
            offset: Tuple[float, float, float] = (0, 0, 0)):
        """
        Creates a box object from a PyMOL selection, with optional name, extension, and offset.

        Arguments:
        selection (str): PyMOL selection string.
        box_name (str, optional): Name of the box. Defaults to None.
        extending (float, optional): Padding distance out of the selection. Defaults to 5.0.
        offset (Tuple[float, float, float], optional): Offset of the box. Defaults to (0, 0, 0).

        Returns:
        Box: Box object.

        Example:
            1. to create a box from a PyMOL selection with 5.0 extension/padding:
                ```python
                box = CgoBox.from_selection("(sele)", "box", 5.0)
                box.load_to_pymol()
                ```
            2. to regenerate a moved for an existing box:
                ```python
                new_box = CgoBox.from_selection("box", "box", 0, (1, 0, 0)) # move the box on the x axis by 1 Angstrom
                new_box.load_to_pymol()
                ```
            3. to increase or decrease the box size:
                ```python
                newbox = CgoBox.from_selection("box", "box", 0)
                # increase the box size by 10 Angstrom on the x axis without changing the center of the box
                newbox.p1=newbox.p1.move(x=newbox.p1.x+x_offset)

                # regenerate the box
                new_box.rebuild()
                new_box.load_to_pymol()


        """
        if not box_name:
            boxName = "box_" + str(randint(0, 10000))
            while boxName in cmd.get_names():
                boxName = "box_" + str(randint(0, 10000))
        else:
            boxName = box_name

        ([minX, minY, minZ], [maxX, maxY, maxZ]) = cmd.get_extent(selection)
        p1 = Point(
            minX - extending + offset[0],
            minY - extending + offset[1],
            minZ - extending + offset[2]

        )
        p2 = Point(
            maxX + extending + offset[0],
            maxY + extending + offset[1],
            maxZ + extending + offset[2]

        )

        box = cls(
            name=boxName,
            p1=p1,
            p2=p2,
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

) -> CgoBox: ...


@overload
def showbox(box: CgoBox,
            minX: Optional[Union[float, str]] = None,
            maxX: Optional[Union[float, str]] = None,
            minY: Optional[Union[float, str]] = None,
            maxY: Optional[Union[float, str]] = None,
            minZ: Optional[Union[float, str]] = None,
            maxZ: Optional[Union[float, str]] = None) -> CgoBox: ...


def showbox(
        box: Union[str, CgoBox],
        minX: Optional[Union[float, str]] = None,
        maxX: Optional[Union[float, str]] = None,
        minY: Optional[Union[float, str]] = None,
        maxY: Optional[Union[float, str]] = None,
        minZ: Optional[Union[float, str]] = None,
        maxZ: Optional[Union[float, str]] = None) -> CgoBox:
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
            raise ValueError(
                "To make a box, you must specify minX, maxX, minY, maxY, minZ, maxZ as valid floats or float-like strings."
            )
        # Create a new CgoBox object from provided parameters
        box = CgoBox(
            name=box,
            p1=Point(
                float(minX),
                float(minY),
                float(minZ)),
            p2=Point(
                float(maxX),
                float(maxY),
                float(maxZ)
            )
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
    new_box = CgoBox.from_selection(
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
    new_box = CgoBox.from_selection(
        selection=box_name,
        box_name=box_name,
        extending=0)

    # Modify the box dimensions based on the specified amounts

    new_box.p1 = new_box.p1.move(
        new_box.p1.x - float(x) / 2 if x is not None else None,
        new_box.p1.y - float(y) / 2 if y is not None else None,
        new_box.p1.z - float(z) / 2 if z is not None else None,
    )

    new_box.p2 = new_box.p2.move(
        new_box.p2.x + float(x) / 2 if x is not None else None,
        new_box.p2.y + float(y) / 2 if y is not None else None,
        new_box.p2.z + float(z) / 2 if z is not None else None,
    )

    # a rebuild calling is necessary for changes taking effects.
    new_box.rebuild()
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
    box = CgoBox.from_selection(selection=selection, box_name=new_box_name, extending=extending)

    # Display the box
    showbox(box)

    boxName = box.name
    print(f'{boxName=}')
    cmd.zoom(boxName)
    return

# remove ions


def removeions():
    """
    Remove specified ions from the molecular model.

    This function selects and removes ions such as PO4, SO4, ZN, CA, MG, and CL from the molecular model in the PyMOL environment.
    """
    cmd.select("Ions", "((resn PO4) | (resn SO4) | (resn ZN) | (resn CA) | (resn MG) | (resn CL)) & hetatm")
    cmd.remove("Ions")
    cmd.delete("Ions")
    return


def rmhet():
    """
    Remove all heteroatoms (HETATM) from the molecular structure.

    Parameters:
    extending (float): This parameter is not used in the current implementation.

    Returns:
    None
    """
    # Select all heteroatoms in the molecular structure
    cmd.select("rmhet", "hetatm")

    # Remove the selected heteroatoms
    cmd.remove("rmhet")
    return

# getbox from cavity residues that reported in papers


def get_oriented_bounding_box(selection, padding=5.0):
    """
    Computes the oriented bounding box for all atoms in 'selection'
    using PCA to align the coordinate system with the data's spread.
    A padding is added (in Å) to each face of the box.

    Returns:
        A numpy array (8x3) of vertex coordinates of the bounding box.
    """
    # 1. Collect coordinates from the selection using get_model.
    model = cmd.get_model(selection)
    coords = np.array([atom.coord for atom in model.atom])

    # 2. Compute the centroid and center the coordinates.
    centroid = np.mean(coords, axis=0)
    centered = coords - centroid

    # 3. Perform PCA: compute the covariance matrix and its eigenvectors.
    cov = np.cov(centered, rowvar=False)
    eigvals, eigvecs = np.linalg.eigh(cov)
    # The columns of eigvecs are the principal axes.

    # 4. Transform coordinates into the PCA (rotated) space.
    transformed = centered.dot(eigvecs)

    # 5. Find the minimum and maximum along each principal axis.
    min_vals = np.min(transformed, axis=0)
    max_vals = np.max(transformed, axis=0)

    # 6. Apply padding in the PCA space.
    min_vals -= padding
    max_vals += padding

    # 7. Generate all 8 corners of the box in PCA space.
    vertices = []
    for i in [0, 1]:
        for j in [0, 1]:
            for k in [0, 1]:
                vertex = np.array([
                    min_vals[0] if i == 0 else max_vals[0],
                    min_vals[1] if j == 0 else max_vals[1],
                    min_vals[2] if k == 0 else max_vals[2]
                ])
                vertices.append(vertex)
    vertices = np.array(vertices)

    # 8. Transform the vertices back to the original coordinate system.
    orig_vertices = vertices.dot(eigvecs.T) + centroid

    # PolyLines(
    #     2.0, 'white',
    #     [*LineVertex.from_points(orig_vertices)],
    #     line_type='TRIANGLE_FAN'
    # ).load_as('white_square')

    return orig_vertices


def plot_pca_box(orig_vertices, new_box_name: str = 'pca_box'):
    """
    Plot a box based on PCA (Principal Component Analysis) results.

    This function takes the original vertices of a box and plots it using a PolyLines object for each face,
    with the option to also plot the edges along the PCA axes. The box is then loaded into the GOC object
    with the specified name.

    Parameters:
    - orig_vertices: List of original vertices of the box.
    - new_box_name: The name to load the plotted box as. Defaults to 'pca_box'.
    """

    # Define each face of the box using vertex indices
    faces = [
        # Front face (PCA1 min)
        [0, 1, 3, 2],
        # Back face (PCA1 max)
        [4, 5, 7, 6],
        # Top face (PCA3 max)
        [1, 3, 7, 5],
        # Bottom face (PCA3 min)
        [0, 2, 6, 4],
        # Left face (PCA2 min)
        [0, 4, 5, 1],
        # Right face (PCA2 max)
        [2, 6, 7, 3]
    ]
    goc = GOC([])

    # Create a PolyLines object for each face
    for i, face_indices in enumerate(faces):
        face_vertices = [orig_vertices[idx] for idx in face_indices]
        goc.objects.append(PolyLines(
            width=2.0,
            color='cyan',
            points=LineVertex.from_points(face_vertices),
            line_type='LINE_LOOP'
        ))

    # Optional: Create edges along PCA axes
    for _idx, axis_edges in enumerate([[0, 4], [1, 5], [2, 6], [3, 7]]):  # PCA1 axis connections
        edge_vertices = [orig_vertices[idx] for idx in axis_edges]

        PolyLines(
            width=1.5,
            color='yellow',
            points=LineVertex.from_points(edge_vertices),
            line_type='LINE_STRIP'
        ).load_as(f'pca_axes_{_idx}')

    # Plot each vertex as a sphere
    for i, v in enumerate(orig_vertices):
        goc.objects.append(Sphere(Point(*v), radius=1))

    # Rebuild the GOC object and load the new box
    goc.rebuild()
    goc.load_as(new_box_name)


def get_pca_box(selection="(sele)", new_box_name: Optional[str] = None, extending=5.0):
    """
    Generates a PCA box for the given selection.

    Parameters:
    - selection: A string defining the selection range for which the PCA box is generated. Defaults to "(sele)".
    - new_box_name: An optional string specifying the name of the new box. If not provided, a unique name will be generated.
    - extending: A float value representing the padding to be added to the oriented bounding box. Defaults to 5.0.

    Returns:
    - None
    """
    if not new_box_name:
        # Generate a unique box name if none is provided
        boxName = "pca_box_" + str(randint(0, 10000))
        while boxName in cmd.get_names():
            # Ensure the generated box name is unique
            boxName = "pca_box_" + str(randint(0, 10000))
    else:
        # Use the provided box name
        boxName = new_box_name

    # Get the oriented bounding box with the specified padding
    orig_vertices = get_oriented_bounding_box(
        selection=selection,
        padding=extending,
    )
    # Plot the PCA box using the calculated vertices and the box name
    plot_pca_box(
        orig_vertices=orig_vertices,
        new_box_name=boxName
    )


def box_helper(box_name: str):
    """
    Create a PyQt window to either move or resize a 3D box object by specifying
    a direction (X, Y, or Z) and a distance value. Users can switch between
    "Move Box" and "Resize Box" actions, adjust distance via a spin box, and
    apply the transformation via arrow keys (or WASD).

    :param box_name: The name or identifier of the box to move/resize.
    """
    from REvoDesign import ConfigBus
    bus = ConfigBus()
    ui = bus.ui

    # Default direction is set to 'x', with a default distance of 1.0.
    direction: Literal['x', 'y', 'z'] = 'x'
    delta_distance: float = 1.0

    # Default action is 'move_coords' with its corresponding method.
    action: Literal['move_coords', 'change_size'] = 'move_coords'
    action_method = movebox

    class MyDoubleSpinBox(QtWidgets.QDoubleSpinBox):
        """
        A QDoubleSpinBox subclass that ignores arrow keys, allowing the
        main window to handle them instead (e.g., for moving/resizing the box).
        """

        def keyPressEvent(self, event):
            """
            If the user presses any arrow key, ignore it here so that the
            event can bubble up to the main window's keyPressEvent handler.
            Otherwise, proceed with normal QDoubleSpinBox behavior.
            """
            if event.key() in (QtCore.Qt.Key_Left, QtCore.Qt.Key_A,
                               QtCore.Qt.Key_Down, QtCore.Qt.Key_S, QtCore.Qt.Key_Right, QtCore.Qt.Key_D,
                               QtCore.Qt.Key_Up, QtCore.Qt.Key_W):
                event.ignore()  # Let the parent widget handle the arrow keys.
            else:
                super().keyPressEvent(event)

    def set_action(new_action: Literal['move_coords', 'change_size']):
        """
        Switch the current action between moving the box and resizing the box.
        Updates the window title and banner text accordingly.

        :param new_action: Either 'move_coords' or 'change_size'.
        """
        nonlocal action
        nonlocal window
        nonlocal banner_label
        nonlocal action_method
        action = new_action

        if action == 'move_coords':
            action_method = movebox
            window_title = f'Move Box Coordinates: {box_name}'
            banner_text = (
                f'''Moving box {box_name} coordinates by picking X, Y, or Z direction and setting
the distance to move in Angstroms for each time.
PressUp/Right/A/W or Down/Left/S/D  to change the values.'''
            )
        else:
            action_method = enlargebox
            window_title = f'Change Box Size: {box_name}'
            banner_text = (
                f'''Change box {box_name} size by picking X, Y, or Z direction and setting
the delta distance to change in Angstroms for each time. Center of the box stays the same.
Press Up/Right/A/W or Down/Left/S/D to change the values.'''
            )
        window.setWindowTitle(window_title)
        banner_label.setText(banner_text)

    def set_distance_delta(distance: float):
        """
        Update the global delta_distance value whenever the spin box value changes.

        :param distance: The new distance (float) set in the spin box.
        """
        nonlocal delta_distance
        logging.debug(f'Set distance delta to {distance}')
        delta_distance = float(distance)

    def set_direction(direction_str: str):
        """
        Update the current direction for the transformation (X, Y, or Z).

        :param direction_str: The string representing the direction (X, Y, or Z).
        :raises ValueError: If the provided direction is invalid.
        """
        nonlocal direction
        _direction = direction_str.lower()
        if _direction not in ['x', 'y', 'z']:
            raise ValueError(f'Invalid direction: {direction_str}')
        logging.debug(f'Set direction to {direction_str}')
        direction = _direction

    def set_box_info_to_banner():
        """
        Query the current box's info (using CgoBox) and display it in the info banner.
        This provides details such as the box coordinates, size, and AutoDock parameters.
        """
        nonlocal banner_info
        box = CgoBox.from_selection(box_name, '_select_box', 0, (0, 0, 0))
        banner_info.setText(
            f"""Box {box_name} info:\n{repr(box)}\n\nAutoDock Vina:\n{box.to_vina}\n\nAutoGrid:\n{box.to_autogrid}"""
        )

    def action_wrapper(params: Dict[str, float]):
        """
        Calls the current action method (movebox or enlargebox) with the specified parameters.
        After performing the action, refresh the box info in the banner.

        :param params: A dictionary containing the direction key (e.g. 'x') and its float value.
        """
        logging.info(f'{params=}')
        action_method(box_name=box_name, **params)
        set_box_info_to_banner()

    def keyboard_event_handler(event):
        """
        A custom keyboard event handler that checks for arrow keys or WASD keys.
        Depending on which key is pressed, it applies a positive or negative
        transformation in the currently selected direction.

        :param event: The QKeyEvent from the window.
        """
        if event.key() in (QtCore.Qt.Key_Left, QtCore.Qt.Key_A,
                           QtCore.Qt.Key_Down, QtCore.Qt.Key_S):
            action_wrapper({direction: -delta_distance})
        elif event.key() in (QtCore.Qt.Key_Right, QtCore.Qt.Key_D,
                             QtCore.Qt.Key_Up, QtCore.Qt.Key_W):
            action_wrapper({direction: delta_distance})
        else:
            print('Ignored')

    # Create a new standalone widget as the main window.
    window = QtWidgets.QWidget()
    window.setObjectName("MoveOrChangeBox")

    main_layout = QtWidgets.QVBoxLayout(window)

    # A label to display the current instructions or banner text.
    banner_label = QtWidgets.QLabel('Pick action to start')
    banner_label.setWordWrap(True)
    banner_label.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
    banner_label.setStyleSheet(
        """
        font-size: 14px;
        font-weight: bold;
        color: #333;
        padding: 10px;
        background-color: #f9f9f9;
        border: 1px solid #ccc;
        border-radius: 5px;
        """
    )
    main_layout.addWidget(banner_label)

    # Layout for the distance label and spin box.
    distance_layout = QtWidgets.QHBoxLayout()
    distance_label = QtWidgets.QLabel("Distance to alter: ")
    distance_layout.addWidget(distance_label)

    # Use our custom spin box that ignores arrow keys.
    distance_spinbox = MyDoubleSpinBox()
    distance_spinbox.setRange(0, 10)
    distance_spinbox.setValue(1.0)
    distance_spinbox.setSingleStep(0.1)
    distance_spinbox.valueChanged.connect(set_distance_delta)
    distance_layout.addWidget(distance_spinbox)

    main_layout.addLayout(distance_layout)

    # A group box to select the action (move or resize).
    action_group_box = QtWidgets.QGroupBox("Actions to take")
    action_layout = QtWidgets.QHBoxLayout()

    move_action_radio_button = QtWidgets.QRadioButton("Move Box")
    move_action_radio_button.toggled.connect(lambda: set_action('move_coords'))
    move_action_radio_button.setChecked(True)  # Default action
    action_layout.addWidget(move_action_radio_button)

    resize_action_radio_button = QtWidgets.QRadioButton("Resize Box")
    resize_action_radio_button.toggled.connect(lambda: set_action('change_size'))
    action_layout.addWidget(resize_action_radio_button)

    action_group_box.setLayout(action_layout)
    main_layout.addWidget(action_group_box)

    # A group box to select direction (X, Y, or Z).
    group_box = QtWidgets.QGroupBox("Select the direction to alter the box")
    group_layout = QtWidgets.QHBoxLayout()

    x_radio_button = QtWidgets.QRadioButton("X axis")
    x_radio_button.pressed.connect(lambda: set_direction("X"))
    group_layout.addWidget(x_radio_button)

    y_radio_button = QtWidgets.QRadioButton("Y axis")
    y_radio_button.pressed.connect(lambda: set_direction("Y"))
    group_layout.addWidget(y_radio_button)

    z_radio_button = QtWidgets.QRadioButton("Z axis")
    z_radio_button.pressed.connect(lambda: set_direction("Z"))
    group_layout.addWidget(z_radio_button)

    group_box.setLayout(group_layout)
    main_layout.addWidget(group_box)

    # A text area to display current box information (coordinates, size, etc.).
    banner_info = QtWidgets.QTextEdit("")
    banner_info.setStyleSheet(
        """
        font-size: 14px;
        font-weight: bold;
        color: #333;
        padding: 10px;
        background-color: #f9f9f9;
        border: 1px solid #ccc;
        border-radius: 5px;
        """
    )
    banner_info.setReadOnly(True)
    main_layout.addWidget(banner_info)

    # Bind our custom keyboard event handler to the window.
    window.keyPressEvent = keyboard_event_handler

    # Keep track of open windows in ui, so we can properly clean them up.
    if not hasattr(ui, 'open_windows'):
        ui.open_windows = []
    ui.open_windows.append(window)

    def cleanup_window():
        """
        Remove the current window from ui.open_windows when destroyed.
        If no windows remain, delete the open_windows attribute from ui.
        """
        if hasattr(ui, 'open_windows') and window in ui.open_windows:
            ui.open_windows.remove(window)
        if isinstance(ui.open_windows, list) and len(ui.open_windows) == 0:
            delattr(ui, 'open_windows')
        print("Window destroyed and cleaned up.")

    window.destroyed.connect(cleanup_window)
    window.show()
