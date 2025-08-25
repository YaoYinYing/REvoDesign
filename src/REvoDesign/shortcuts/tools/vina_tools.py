from dataclasses import dataclass
from random import randint
from typing import Dict, Literal, Optional, Tuple, Union, overload
import numpy as np
from chempy import cpv
from pymol import cgo, cmd
from pymol.vfont import plain
from REvoDesign.logger import ROOT_LOGGER
from REvoDesign.Qt import QtCore, QtGui, QtWidgets
from REvoDesign.tools.customized_widgets import REvoDesignWidget
from ...tools.cgo_utils import Cone, Cube, Cylinder, GraphicObject
from ...tools.cgo_utils import GraphicObjectCollection as GOC
from ...tools.cgo_utils import LineVertex, Point, PolyLines, Sphere
logging = ROOT_LOGGER.getChild(__name__)
class PutCenterCallback:
    prev_v = None
    def __init__(self, name, corner=0):
        self.name = name
        self.corner = corner
        self.cb_name = cmd.get_unused_name('_cb')
    def load(self):
        cmd.load_callback(self, self.cb_name)
    def __call__(self):
        if self.name not in cmd.get_names('objects'):
            import threading
            threading.Thread(None, cmd.delete, args=(self.cb_name,)).start()
            return
        v = cmd.get_view()
        if v == self.prev_v:
            return
        self.prev_v = v
        t = v[12:15]
        if self.corner:
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
@dataclass
class CgoAxes(GraphicObject):
    name: str = "axes"
    w: float = 0.06  
    l: float = 0.75  
    h: float = 0.25  
    always_left_corner: bool = True
    show_labels: bool = True
    label_weight: float = 0.05
    label_size: float = 0.5
    def rebuild(self):
        self.w = float(self.w)
        self.l = float(self.l)
        self.h = float(self.h)
        self.always_left_corner = bool(self.always_left_corner)
        self._data = []
        for (idxa, axis), (idxc, colorname) in zip(enumerate('xyz'), enumerate('rgb')):
            p2_kwargs = {i: 0.0 for i in 'xyz' if i != axis}
            self._data.extend(
                Cylinder(
                    Point(0.0, 0.0, 0.0),  
                    Point(**p2_kwargs, **{axis: self.l}),  
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
        return self.w * 1.618  
    def set_label(self):
        obj = self.data
        label_axis = [[self.label_size, 0, 0], [0, self.label_size, 0], [0, 0, self.label_size]]
        cgo.cyl_text(obj, plain, [self.l + self.h, 0, - self.w], 'X', self.label_weight, axes=label_axis)
        cgo.cyl_text(obj, plain, [-self.w, self.l + self.h, 0], 'Y', self.label_weight, axes=label_axis)
        cgo.cyl_text(obj, plain, [-self.w, 0, self.l + self.h], 'Z', self.label_weight, axes=label_axis)
    def show(self):
        cmd.set('auto_zoom', 0)
        if self.always_left_corner:
            PutCenterCallback(self.name, 1).load()
        if self.show_labels:
            self.set_label()
        cmd.load_cgo(self.data, self.name)
def showaxes():
    axes = CgoAxes()
    axes.show()
@dataclass
class CgoBox(GraphicObject):
    name: str
    p1: Point
    p2: Point
    linewidth: float = 5.0
    color_x: str = 'red'
    color_y: str = 'green'
    color_z: str = 'blue'
    def rebuild(self):
        self.size_xyz = tuple(abs(x) for x in self.p1.delta_xyz(self.p2))
        self.cen_xyz = self.p1.center_xyz(self.p2)
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
        center = f"--center_x {self.cen_xyz[0]:.1f} --center_y {self.cen_xyz[1]:.1f} --center_z {self.cen_xyz[2]:.1f}"
        size = f"--size_x {self.size_xyz[0]:.1f} --size_y {self.size_xyz[1]:.1f} --size_z {self.size_xyz[2]:.1f}"
        return f"{center} {size}"
    @property
    def to_autogrid(self):
        npts_xyz = np.array(self.size_xyz) / 0.375
        npts = f"npts {npts_xyz[0]} {npts_xyz[1]} {npts_xyz[2]} 
        spacing = 'spacing 0.375 
        center = f"gridcenter {self.cen_xyz[0]:.3f} {self.cen_xyz[1]:.3f} {self.cen_xyz[2]:.3f} 
        return f"{npts}\n{spacing}\n{center}"
    @property
    def to_ledock(self):
        return f"""Binding pocket
{self.p1.x:.1f} {self.p2.x:.1f}
{self.p1.y:.1f} {self.p2.y:.1f}
{self.p1.z:.1f} {self.p2.z:.1f}
        Loads the CGO object into PyMOL for visualization.
        Provides a string representation of the box, including its coordinates, size, and center.
    @classmethod
    def from_selection(
            cls,
            selection: str = "(sele)",
            box_name: Optional[str] = None,
            extending: float = 5.0,
            offset: Tuple[float, float, float] = (0, 0, 0)):
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
    showaxes()
    if isinstance(box, str):
        if any(x is None for x in [minX, maxX, minY, maxY, minZ, maxZ]):
            raise ValueError(
                "To make a box, you must specify minX, maxX, minY, maxY, minZ, maxZ as valid floats or float-like strings."
            )
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
    print('*' * 45, 'AutoDock Vina', '*' * 45, '\n', box.to_vina, '\n\n')
    print('*' * 45, 'AutoGrid', '*' * 45, '\n', box.to_autogrid, '\n\n')
    print('*' * 45, 'LeDock', '*' * 45, '\n', box.to_ledock, '\n\n')
    box.load_to_pymol()
    return box
def movebox(box_name: str, x: float = 0, y: float = 0, z: float = 0):
    if all(i == 0 for i in [x, y, z]):
        print("No movement specified")
        return
    new_box = CgoBox.from_selection(
        selection=box_name,
        box_name=box_name,
        extending=0,
        offset=(float(x), float(y), float(z)))
    new_box.load_to_pymol()
def enlargebox(box_name: str, x: float = 0, y: float = 0, z: float = 0):
    if all(i == 0 for i in [x, y, z]):
        print("No enlargement/truncation specified")
        return
    new_box = CgoBox.from_selection(
        selection=box_name,
        box_name=box_name,
        extending=0)
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
    new_box.rebuild()
    new_box.load_to_pymol()
def getbox(selection="(sele)", new_box_name: Optional[str] = None, extending=5.0):
    cmd.hide("spheres")
    cmd.show("spheres", selection)
    showaxes()
    box = CgoBox.from_selection(selection=selection, box_name=new_box_name, extending=extending)
    showbox(box)
    boxName = box.name
    print(f'{boxName=}')
    cmd.zoom(boxName)
    return
def removeions():
    cmd.select("Ions", "((resn PO4) | (resn SO4) | (resn ZN) | (resn CA) | (resn MG) | (resn CL)) & hetatm")
    cmd.remove("Ions")
    cmd.delete("Ions")
    return
def rmhet():
    cmd.select("rmhet", "hetatm")
    cmd.remove("rmhet")
    return
def get_oriented_bounding_box(selection, padding=5.0):
    model = cmd.get_model(selection)
    coords = np.array([atom.coord for atom in model.atom])
    centroid = np.mean(coords, axis=0)
    centered = coords - centroid
    cov = np.cov(centered, rowvar=False)
    eigvals, eigvecs = np.linalg.eigh(cov)
    transformed = centered.dot(eigvecs)
    min_vals = np.min(transformed, axis=0)
    max_vals = np.max(transformed, axis=0)
    min_vals -= padding
    max_vals += padding
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
    orig_vertices = vertices.dot(eigvecs.T) + centroid
    return orig_vertices
def plot_pca_box(orig_vertices, new_box_name: str = 'pca_box'):
    faces = [
        [0, 1, 3, 2],
        [4, 5, 7, 6],
        [1, 3, 7, 5],
        [0, 2, 6, 4],
        [0, 4, 5, 1],
        [2, 6, 7, 3]
    ]
    goc = GOC([])
    for i, face_indices in enumerate(faces):
        face_vertices = [orig_vertices[idx] for idx in face_indices]
        goc.objects.append(PolyLines(
            width=2.0,
            color='cyan',
            points=LineVertex.from_points(face_vertices),
            line_type='LINE_LOOP'
        ))
    for _idx, axis_edges in enumerate([[0, 4], [1, 5], [2, 6], [3, 7]]):  
        edge_vertices = [orig_vertices[idx] for idx in axis_edges]
        PolyLines(
            width=1.5,
            color='yellow',
            points=LineVertex.from_points(edge_vertices),
            line_type='LINE_STRIP'
        ).load_as(f'pca_axes_{_idx}')
    for i, v in enumerate(orig_vertices):
        goc.objects.append(Sphere(Point(*v), radius=1))
    goc.rebuild()
    goc.load_as(new_box_name)
def get_pca_box(selection="(sele)", new_box_name: Optional[str] = None, extending=5.0):
    if not new_box_name:
        boxName = "pca_box_" + str(randint(0, 10000))
        while boxName in cmd.get_names():
            boxName = "pca_box_" + str(randint(0, 10000))
    else:
        boxName = new_box_name
    orig_vertices = get_oriented_bounding_box(
        selection=selection,
        padding=extending,
    )
    plot_pca_box(
        orig_vertices=orig_vertices,
        new_box_name=boxName
    )
def box_helper(box_name: str):
    from REvoDesign import ConfigBus
    bus = ConfigBus()
    direction: Literal['x', 'y', 'z'] = 'x'
    delta_distance: float = 1.0
    action: Literal['move_coords', 'change_size'] = 'move_coords'
    action_method = movebox
    class MyDoubleSpinBox(QtWidgets.QDoubleSpinBox):
        def keyPressEvent(self, event):
            if event.key() in (QtCore.Qt.Key_Left, QtCore.Qt.Key_A,
                               QtCore.Qt.Key_Down, QtCore.Qt.Key_S, QtCore.Qt.Key_Right, QtCore.Qt.Key_D,
                               QtCore.Qt.Key_Up, QtCore.Qt.Key_W):
                event.ignore()  
            else:
                super().keyPressEvent(event)
    def set_action(new_action: Literal['move_coords', 'change_size']):
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
        nonlocal delta_distance
        logging.debug(f'Set distance delta to {distance}')
        delta_distance = float(distance)
    def set_direction(direction_str: str):
        nonlocal direction
        _direction = direction_str.lower()
        if _direction not in ['x', 'y', 'z']:
            raise ValueError(f'Invalid direction: {direction_str}')
        logging.debug(f'Set direction to {direction_str}')
        direction = _direction
    def set_box_info_to_banner():
        nonlocal banner_info
        box = CgoBox.from_selection(box_name, '_select_box', 0, (0, 0, 0))
        banner_info.setText(
            f"""Box {box_name} info:\n{repr(box)}\n\nAutoDock Vina:\n{box.to_vina}\n\nAutoGrid:\n{box.to_autogrid}"""
        )
    def action_wrapper(params: Dict[str, float]):
        logging.info(f'{params=}')
        action_method(box_name=box_name, **params)
        set_box_info_to_banner()
    def keyboard_event_handler(event):
        if event.key() in (QtCore.Qt.Key_Left, QtCore.Qt.Key_A,
                           QtCore.Qt.Key_Down, QtCore.Qt.Key_S):
            action_wrapper({direction: -delta_distance})
        elif event.key() in (QtCore.Qt.Key_Right, QtCore.Qt.Key_D,
                             QtCore.Qt.Key_Up, QtCore.Qt.Key_W):
            action_wrapper({direction: delta_distance})
        else:
            print('Ignored')
    window = REvoDesignWidget("MoveOrChangeBox")
    main_layout = QtWidgets.QVBoxLayout(window)
    banner_label = QtWidgets.QLabel('Pick action to start')
    banner_label.setWordWrap(True)
    banner_label.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
    banner_label.setStyleSheet(
    )
    main_layout.addWidget(banner_label)
    distance_layout = QtWidgets.QHBoxLayout()
    distance_label = QtWidgets.QLabel("Distance to alter: ")
    distance_layout.addWidget(distance_label)
    distance_spinbox = MyDoubleSpinBox()
    distance_spinbox.setRange(0, 10)
    distance_spinbox.setValue(1.0)
    distance_spinbox.setSingleStep(0.1)
    distance_spinbox.valueChanged.connect(set_distance_delta)
    distance_layout.addWidget(distance_spinbox)
    main_layout.addLayout(distance_layout)
    action_group_box = QtWidgets.QGroupBox("Actions to take")
    action_layout = QtWidgets.QHBoxLayout()
    move_action_radio_button = QtWidgets.QRadioButton("Move Box")
    move_action_radio_button.toggled.connect(lambda: set_action('move_coords'))
    move_action_radio_button.setChecked(True)  
    action_layout.addWidget(move_action_radio_button)
    resize_action_radio_button = QtWidgets.QRadioButton("Resize Box")
    resize_action_radio_button.toggled.connect(lambda: set_action('change_size'))
    action_layout.addWidget(resize_action_radio_button)
    action_group_box.setLayout(action_layout)
    main_layout.addWidget(action_group_box)
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
    banner_info = QtWidgets.QTextEdit("")
    banner_info.setStyleSheet(
    )
    banner_info.setReadOnly(True)
    main_layout.addWidget(banner_info)
    window.keyPressEvent = keyboard_event_handler
    window.show()