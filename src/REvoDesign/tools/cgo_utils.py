'''
Utilities for pymol.cgo, modified from `pymol.cgobuilder`

docs of cgo:

Lowercase names below should be replaced with floating-point numbers. Generally, the TRIANGLE primitive should only be used only as a last restore since it is much less effective to render than using a series of vertices with a BEGIN/END group.

BEGIN, { POINTS | LINES | LINE_LOOP | LINE_STRIP | TRIANGLES | TRIANGLE_STRIP | TRIANGLE_FAN },

VERTEX, x,  y,  z,

COLOR,  red, green, blue,

NORMAL, normal-x, normal-y,  normal-z,

END,

LINEWIDTH, line-width,

WIDTHSCALE, width-scale,   # for ray-tracing

SPHERE, x, y, z,  radius    # uses the current color


[[Category:CGO]]

CYLINDER, x1, y1, z1, x2, y2, z2, radius,
          red1, green1, blue1, red2, green2, blue2,

TRIANGLE,  x1, y1, z1,
           x2, y2, z2,
           x3, y3, z3,
           normal-x1, normal-y1, normal-z1,
           normal-x2, normal-y2, normal-z2,
           normal-x3, normal-y3, normal-z3,
           red1, green1, blue1,
           red2, green2, blue2,
           red3, green3, blue3,

CONE,      x1, y1, z1,
           x2, y2, z2,
           r1, r2,
           red1, green1, blue1,
           red2, green2, blue2,
           cap1, cap2   # should the ends be solid (1) or open (0)?



'''

import itertools
import math
from dataclasses import dataclass, field
from functools import cached_property
from typing import Iterable, List, Optional, Literal
import numpy as np
import webcolors
from chempy import cpv
from immutabledict import immutabledict
from matplotlib import _color_data as _cdata
from pymol import cgo, cmd
from PIL import Image, ImageDraw, ImageFont

import matplotlib.font_manager as fm


# name: hsv imutable dicts
BASE_COLORS: immutabledict[str, str] = immutabledict({name: webcolors.rgb_to_hex(
    tuple(map(lambda x: int(255 * x), value))) for name, value in _cdata.BASE_COLORS.items()})  # type: ignore
TABLEAU_COLORS: immutabledict[str, str] = immutabledict(
    {name.lstrip('tab:'): value for name, value in _cdata.TABLEAU_COLORS.items()})
CSS4_COLORS: immutabledict[str, str] = immutabledict(_cdata.CSS4_COLORS)
XKCD_COLORS: immutabledict[str, str] = immutabledict(
    {name.lstrip('xkcd:').replace(' ', '_'): value for name, value in _cdata.XKCD_COLORS.items()})

# color tables
COLOR_TABLES = (BASE_COLORS, TABLEAU_COLORS, CSS4_COLORS, XKCD_COLORS,)


def not_none_float(float_in_1: Optional[float], float_in_2: Optional[float]):
    if float_in_1 is not None:
        return float(float_in_1)
    if float_in_2 is not None:
        return float(float_in_2)
    return 0.0


@dataclass(frozen=True)
class Point:
    x: float
    y: float
    z: float

    @cached_property
    def array(self):
        return np.array([self.x, self.y, self.z])

    @cached_property
    def as_vertex(self):
        return np.insert(cgo.VERTEX, 1, self.array)

    @cached_property
    def as_normal(self):
        return np.insert(cgo.NORMAL, 1, self.array)

    def move(self, x: Optional[float] = None, y: Optional[float] = None, z: Optional[float] = None) -> 'Point':
        return Point(
            not_none_float(x, self.x),
            not_none_float(y, self.y),
            not_none_float(z, self.z))

    @staticmethod
    def as_arrays(points: Iterable['Point']):
        return np.concatenate(tuple(point.array for point in points))

    @staticmethod
    def as_vertexes(points: Iterable['Point']):
        return np.concatenate(tuple(point.as_vertex for point in points))

    @classmethod
    def from_xyz(cls, x: float, y: float, z: float):
        return Point(x, y, z)




@dataclass(frozen=True)
class Color:
    name: str
    alpha: float = 1.0

    @cached_property
    def array(self) -> np.ndarray:
        name = self.name.lower().replace(" ", "_")
        for cdict in COLOR_TABLES:
            if name not in cdict:
                continue
            print(f'[DEBUG] {name}: {cdict[name]}')
            return np.array(webcolors.hex_to_rgb(cdict[name]), dtype=float) / 255  # type: ignore

        try:
            return np.array(webcolors.name_to_rgb(self.name), dtype=float) / 255
        except ValueError as e:
            raise ValueError(f"{self.name} is not a valid color name from matplotlib or webcolors") from e

    @cached_property
    def array_alpha(self) -> np.ndarray:
        return np.append(self.array, self.alpha)

    @staticmethod
    def as_arrays(colors: Iterable['Color']):
        return np.concatenate(tuple(color.array for color in colors))

    @staticmethod
    def as_cgos(colors: Iterable['Color']):
        return np.concatenate(tuple(color.as_cgo for color in colors))

    @cached_property
    def as_cgo(self):
        return np.insert(self.array, 0, cgo.COLOR)


@dataclass
class GraphicObject:

    def rebuild(self):
        """
        Rebuild the CGO data.
        """
        self._data: List[float] = []

    def __post_init__(self):
        """
        Post-initialization processing.
        If an object with the same name already exists, it is deleted.
        Ensures the data types of attributes are as expected.
        """
        # Delete existing object with the same name to avoid conflicts
        self.rebuild()

    @property
    def data(self):
        """
        Get the CGO data.
        """
        return self._data

    def load_as(self, name: str):
        if name in cmd.get_names():
            cmd.delete(name)

        print(f'[DEBUG]: {self.__class__}: \n{self.data}')
        cmd.load_cgo(self.data, name)


@dataclass
class Sphere(GraphicObject):
    center: Point = Point(0, 0, 0)
    radius: float = 0.0
    color: str = 'w'

    def rebuild(self):

        self._data = [
            *Color(self.color).as_cgo,
            cgo.SPHERE,
            *self.center.array,
            self.radius,
        ]


@dataclass
class Cylinder(GraphicObject):
    point1: Point = Point(0, 0, 0)
    point2: Point = Point(1, 1, 1)
    radius: float = 1.0
    color1: str = 'violet'
    color2: str = 'cyan'

    def rebuild(self):
        self._data = [
            cgo.CYLINDER,
            *self.point1.array,
            *self.point2.array,
            self.radius,
            *Color(self.color1).array,
            *Color(self.color2).array,
        ]


@dataclass
class Doughnut(GraphicObject):  # Torus
    center: Point = Point(0.0, 0.0, 0.0)
    normal: Point = Point(0.0, 0.0, 1.0)
    radius: float = 1.0
    color: str = 'w'
    cradius: float = 0.25
    samples: int = 20
    csamples: int = 20

    # from pymol.cgobuilder.Torus
    def rebuild(self) -> None:
        """
        Rebuilds torus
        """
        obj = []

        axis = cpv.cross_product(self.normal.array, (0., 0., 1.))
        angle = -cpv.get_angle(self.normal.array, (0., 0., 1.))
        matrix = cpv.rotation_matrix(angle, cpv.normalize(axis))

        def obj_vertex(x, y, z):
            return [cgo.VERTEX] + cpv.add(self.center.array,
                                          cpv.transform(matrix, [x, y, z]))

        def obj_normal(x, y, z):
            return [cgo.NORMAL] + cpv.transform(matrix, [x, y, z])

        r = self.radius
        cr = self.cradius
        rr = 1.5 * cr
        dv = 2 * math.pi / self.csamples
        dw = 2 * math.pi / self.samples
        v = 0.0
        w = 0.0

        while w < 2 * math.pi:
            v = 0.0
            c_w = math.cos(w)
            s_w = math.sin(w)
            c_wdw = math.cos(w + dw)
            s_wdw = math.sin(w + dw)

            obj.append(cgo.BEGIN)
            obj.append(cgo.TRIANGLE_STRIP)

            obj.append(cgo.COLOR)
            obj.extend(Color(self.color).array)

            while v < 2 * math.pi + dv:
                c_v = math.cos(v)
                s_v = math.sin(v)
                c_vdv = math.cos(v + dv)
                s_vdv = math.sin(v + dv)
                obj.extend(
                    obj_normal((r + rr * c_v) * c_w - (r + cr * c_v) * c_w,
                               (r + rr * c_v) * s_w - (r + cr * c_v) * s_w,
                               (rr * s_v - cr * s_v)))
                obj.extend(
                    obj_vertex((r + cr * c_v) * c_w, (r + cr * c_v) * s_w,
                               cr * s_v))
                obj.extend(
                    obj_normal(
                        (r + rr * c_vdv) * c_wdw - (r + cr * c_vdv) * c_wdw,
                        (r + rr * c_vdv) * s_wdw - (r + cr * c_vdv) * s_wdw,
                        rr * s_vdv - cr * s_vdv))
                obj.extend(
                    obj_vertex((r + cr * c_vdv) * c_wdw,
                               (r + cr * c_vdv) * s_wdw, cr * s_vdv))
                v += dv

            obj.append(cgo.END)
            w += dw

        self._data = obj


@dataclass
class Cone(GraphicObject):
    tip: Point = Point(1.0, 0.0, 0.0)
    base_center: Point = Point(0.0, 0.0, 0.0)
    radius_tip: float = 1.0
    radius_base: float = 0.0
    color_tip: str = 'w'
    color_base: str = 'g'

    caps: tuple[float, float] = (1, 0)

    def rebuild(self) -> None:
        """
        Rebuilds cone
        """
        self._data = [
            cgo.CONE,
            *self.tip.array,
            *self.base_center.array,
            self.radius_tip, self.radius_base,
            *Color(self.color_tip).array,
            *Color(self.color_base).array,
            *self.caps
        ]


@dataclass
class Bezier(GraphicObject):
    control_pt_A = Point(-5.0, 0.0, 0.0)
    A_right_handle = Point(0.0, 10.0, 0.0)
    B_left_handle = Point(1.0, -10.0, 0.0)
    control_pt_B = Point(5.0, 0.0, 0.0)

    def rebuild(self) -> None:
        """
        Rebuilds bezier spline
        """
        self._data = [
            cgo.BEZIER,
            *Point.as_arrays(
                (self.control_pt_A,
                 self.A_right_handle,
                 self.B_left_handle,
                 self.control_pt_B,)
            )
        ]


@dataclass
class Triangle(GraphicObject):
    vertex_a: Point = Point(1, 0, 0)
    vertex_b: Point = Point(0, 1, 0)
    vertex_c: Point = Point(0, 0, 1)

    normal_a: Point = Point(1, 0, 0)
    normal_b: Point = Point(0, 1, 0)
    normal_c: Point = Point(0, 0, 1)

    color_a: str = 'r'
    color_b: str = 'g'
    color_c: str = 'b'

    def rebuild(self):
        self._data = [
            *Point.as_arrays((self.vertex_a, self.vertex_b, self.vertex_c)),
            *Point.as_arrays((self.normal_a, self.normal_b, self.normal_c)),
            *Color.as_arrays((Color(self.color_a), Color(self.color_b), Color(self.color_c)))
        ]


@dataclass
class TriangleSimple(GraphicObject):
    vertex_a: Point = Point(1, 0, 0)
    vertex_b: Point = Point(0, 1, 0)
    vertex_c: Point = Point(0, 0, 1)

    color_a: str = 'r'
    color_b: str = 'g'
    color_c: str = 'b'

    def rebuild(self):

        self._data = [
            cgo.BEGIN, cgo.TRIANGLES,

            *Color(self.color_a).as_cgo,
            *self.vertex_a.as_vertex,

            *Color(self.color_b).as_cgo,
            *self.vertex_b.as_vertex,

            *Color(self.color_c).as_cgo,
            *self.vertex_c.as_vertex,

            cgo.END
        ]


@dataclass
class Line(GraphicObject):
    start: Point = Point(0, 0, 0)
    end: Point = Point(0, 0, 1)

    @property
    def points(self):
        return (self.start, self.end)

    def rebuild(self):
        self._data = [
            *Point.as_vertexes((self.start, self.end))
        ]


@dataclass
class Lines(GraphicObject):
    color: str = 'w'

    lines: tuple[Line] = field(default_factory=tuple)

    def rebuild(self):
        self._data = [
            *Color(self.color).as_cgo,
        ]
        for line in self.lines:
            self._data.extend(line.data)


@dataclass
class Cube(GraphicObject):
    color_w: str = 'red'

    color_x: str = 'red'
    color_y: str = 'green'
    color_z: str = 'blue'

    p1: Point = Point(0, 0, 0)
    p2: Point = Point(1, 1, 1)

    transparent: bool = True
    linewidth: float = 2

    def _rebuild_wireframe(self):

        self._data = [
            cgo.LINEWIDTH, float(self.linewidth),
            cgo.BEGIN, cgo.LINES,

        ]
        # x fixed
        for y, z in itertools.product((self.p1.y, self.p2.y), (self.p1.z, self.p2.z)):
            self._data.extend([
                *Color(self.color_x).as_cgo,
                *self.p1.move(y=y, z=z).as_vertex,
                *self.p2.move(y=y, z=z).as_vertex,
            ])

        # y fixed
        for x, z in itertools.product((self.p1.x, self.p2.x), (self.p1.z, self.p2.z)):
            self._data.extend([
                *Color(self.color_y).as_cgo,
                *self.p1.move(x=x, z=z).as_vertex,
                *self.p2.move(x=x, z=z).as_vertex,
            ])

        # z fixed
        for x, y in itertools.product((self.p1.x, self.p2.x), (self.p1.y, self.p2.y)):
            self._data.extend([
                *Color(self.color_z).as_cgo,
                *self.p1.move(x=x, y=y).as_vertex,
                *self.p2.move(x=x, y=y).as_vertex,
            ])

        self._data.append(cgo.END)

    def _rebuild_solid(self):
        """
        用 6 个 Square，合并出一个立方体(或长方体)外表。
        """
        # 简易函数：构造一个纯色的 Square（四个角都用 self.color）
        def make_face(a: Point, b: Point, c: Point, d: Point) -> List[float]:
            face = Square(
                corner_a=a, corner_b=b, corner_c=c, corner_d=d,
                # 给四个角都指定同一个颜色 => 整个面都是 uniform color
                color_a=self.color_w,
                color_b=self.color_x,
                color_c=self.color_y,
                color_d=self.color_z
            )
            face.rebuild()
            return face.data

        # 获取 8 个顶点的 (x,y,z) 各种组合
        x1, y1, z1 = self.p1.x, self.p1.y, self.p1.z
        x2, y2, z2 = self.p2.x, self.p2.y, self.p2.z

        # 面 1: x = x1
        #   A=(x1,y1,z1), B=(x1,y1,z2), C=(x1,y2,z2), D=(x1,y2,z1)
        face1_data = make_face(
            Point(x1, y1, z1), Point(x1, y1, z2), Point(x1, y2, z2), Point(x1, y2, z1)
        )
        # 面 2: x = x2
        #   A=(x2,y1,z1), B=(x2,y2,z1), C=(x2,y2,z2), D=(x2,y1,z2)
        face2_data = make_face(
            Point(x2, y1, z1), Point(x2, y2, z1), Point(x2, y2, z2), Point(x2, y1, z2)
        )
        # 面 3: y = y1
        #   A=(x1,y1,z1), B=(x2,y1,z1), C=(x2,y1,z2), D=(x1,y1,z2)
        face3_data = make_face(
            Point(x1, y1, z1), Point(x2, y1, z1), Point(x2, y1, z2), Point(x1, y1, z2)
        )
        # 面 4: y = y2
        #   A=(x1,y2,z1), B=(x1,y2,z2), C=(x2,y2,z2), D=(x2,y2,z1)
        face4_data = make_face(
            Point(x1, y2, z1), Point(x1, y2, z2), Point(x2, y2, z2), Point(x2, y2, z1)
        )
        # 面 5: z = z1
        #   A=(x1,y1,z1), B=(x1,y2,z1), C=(x2,y2,z1), D=(x2,y1,z1)
        face5_data = make_face(
            Point(x1, y1, z1), Point(x1, y2, z1), Point(x2, y2, z1), Point(x2, y1, z1)
        )
        # 面 6: z = z2
        #   A=(x1,y1,z2), B=(x2,y1,z2), C=(x2,y2,z2), D=(x1,y2,z2)
        face6_data = make_face(
            Point(x1, y1, z2), Point(x2, y1, z2), Point(x2, y2, z2), Point(x1, y2, z2)
        )

        # 将 6 个面的 CGO 数据合并
        self._data = face1_data + face2_data + face3_data + \
            face4_data + face5_data + face6_data

    def rebuild(self):
        if self.transparent:
            self._rebuild_wireframe()
        else:
            self._rebuild_solid()


@dataclass
class Square(GraphicObject):

    corner_a: Point = Point(0, 0, 0)
    corner_b: Point = Point(1, 0, 0)
    corner_c: Point = Point(1, 1, 0)
    corner_d: Point = Point(0, 1, 0)

    color_a: str = 'r'
    color_b: str = 'g'
    color_c: str = 'b'
    color_d: str = 'y'

    def rebuild(self):

        self._data = [
            cgo.BEGIN, cgo.TRIANGLES,

            *Color(self.color_a).as_cgo,
            *self.corner_a.as_vertex,
            *Color(self.color_b).as_cgo,
            *self.corner_b.as_vertex,
            *Color(self.color_c).as_cgo,
            *self.corner_c.as_vertex,

            *Color(self.color_a).as_cgo,
            *self.corner_a.as_vertex,
            *Color(self.color_c).as_cgo,
            *self.corner_c.as_vertex,
            *Color(self.color_d).as_cgo,
            *self.corner_d.as_vertex,

            cgo.END
        ]

@dataclass
class LineVertex(GraphicObject):
    point: Point
    width: Optional[float]=None
    color: Optional[str]=None

    def rebuild(self):
        self._data = []
        if self.width:
            self._data.extend([cgo.LINEWIDTH, self.width])
        if self.color:
            self._data.extend(Color(self.color).as_cgo)
        self._data.extend(self.point.as_vertex)



@dataclass
class PolyLines(GraphicObject):
    # global
    width: float
    color: str

    points: Iterable[LineVertex]
    line_type: Literal['LINE_STRIP', 'LINE_LOOP']= 'LINE_STRIP'
    

    def rebuild(self):
        self._data=[
            cgo.LINEWIDTH, self.width,
            *Color(self.color).as_cgo,
            cgo.BEGIN, cgo.LINE_LOOP if self.line_type=='LINE_LOOP' else cgo.LINE_STRIP,
            ]
        for pv in self.points:
            self._data.extend([*pv.data])

        self._data.append(cgo.END)


# TEST CASES that can be run from pymol
# `run src/REvoDesign/tools/cgo_utils.py`

# sphere=Sphere(center=Point(0,0,0),radius=10, color='cyan')
# sphere.load_as('mysphere')

# cyl=Cylinder()
# cyl.load_as('my_cyl')


# Doughnut(samples=100).load_as('my_treasure')

# Cone(color_base='golden', color_tip='sand_brown').load_as('dyamond')

# Bezier().load_as('bez') #??

# Triangle(
#         vertex_a=Point(3, 0, 0),      # 顶点A
#         vertex_b=Point(0, 3, 0),      # 顶点B
#         vertex_c=Point(0, 0, 3),      # 顶点C

#         normal_a=Point(0, 0, 1),      # A顶点的法向量
#         normal_b=Point(0, 1, 0),      # B顶点的法向量
#         normal_c=Point(1, 0, 0),      # C顶点的法向量

#         color_a='red',         # A的颜色：红色
#         color_b='green',       # B的颜色：绿色
#         color_c='blue',        # C的颜色：蓝色
#     ).load_as('my_triangle')

# TriangleSimple(
#     vertex_a=Point(1, 0, 0),
#     vertex_b=Point(0, 1, 0),
#     vertex_c=Point(0, 0, 1),

#     color_a='cyan',
#     color_b='yellow',
#     color_c='magenta',
#     ).load_as('my_triangle_simple')


# Cube(transparent=True).load_as('a_colorful_cube')
# Cube(
#     transparent=False,
#     color_w='yellow',
#     color_x='yellow',
#     color_y='yellow',
#     color_z='yellow'
# ).load_as('a_yellow_box')

# Cube(transparent=False,
#     color_w='white',
#     color_x='white',
#     color_y='white',
#     color_z='white'
# ).load_as('solid_box')

# Cube(
#     transparent=True,
#     color_w='black',
#     color_x='black',
#     color_y='black',
#     color_z='black'
#     ).load_as('a_black_box')

# Square().load_as('a_square')


PolyLines(
    2.0, 'yellow',
    [LineVertex(Point(0, 0, 0) ),
     LineVertex(Point(0, 0, 1) ),
     LineVertex(Point(0, 1, 0) ),
     LineVertex(Point(1, 0, 0) ),
     LineVertex(Point(1, 1, 2) )]
).load_as('yellow_line_strip')


PolyLines(
    2.0, 'red',
    [LineVertex(Point(0, 0, 0) ),
     LineVertex(Point(0, 0, 1) ),
     LineVertex(Point(0, 1, 0) ),
     LineVertex(Point(1, 0, 0) ),
     LineVertex(Point(1, 1, 2) )],
     line_type='LINE_LOOP'
).load_as('red_line_loop')