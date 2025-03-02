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

from dataclasses import dataclass,field
import math
from typing import Iterable, List
from functools import cached_property
from pymol import cgo
import webcolors
import numpy as np
from pymol import cmd
from chempy import cpv


import matplotlib.colors as mcolors
from matplotlib import _color_data as _cdata

from immutabledict import immutabledict

cmd.color
# name: hsv imutable dicts
BASE_COLORS: immutabledict[str, str]=immutabledict({name: webcolors.rgb_to_hex(tuple(map(lambda x: int(255*x), value))) for name,value in _cdata.BASE_COLORS.items()}) # type: ignore
TABLEAU_COLORS: immutabledict[str, str]=immutabledict({name.lstrip('tab:'): value for name,value in _cdata.TABLEAU_COLORS.items()})
CSS4_COLORS: immutabledict[str, str]=immutabledict(_cdata.CSS4_COLORS)
XKCD_COLORS: immutabledict[str, str]=immutabledict({name.lstrip('xkcd:').replace(' ', '_'): value for name,value in _cdata.XKCD_COLORS.items()})

# color tables
COLOR_TABLES=(BASE_COLORS,TABLEAU_COLORS, CSS4_COLORS, XKCD_COLORS,)

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
        return np.insert(cgo.VERTEX, 0, self.array)
    
    
    @cached_property
    def as_normal(self):
        return np.insert(cgo.NORMAL, 0, self.array)
    
    @cached_property
    def move(self, x: float = 0, y: float = 0, z: float = 0) -> 'Point':
        return Point(self.x + x, self.y + y, self.z + z)


    @staticmethod
    def as_arrays(points: Iterable['Point']):
        return np.concatenate(tuple(point.array for point in points))
    
    @staticmethod
    def as_vertexes(points: Iterable['Point']):
        return np.concatenate(tuple(point.as_vertex for point in points))
    

    @classmethod
    def from_xyz(cls, x: float, y: float, z: float):
        return Point(x,y,z)
@dataclass(frozen=True)
class Color:
    name: str
    alpha: float = 1.0

    @cached_property
    def array(self)-> np.ndarray:
        name = self.name.lower().replace(" ","_")
        for cdict in COLOR_TABLES:
            if name not in cdict:
                continue
            return np.array(cdict[name])
        
        try:
            return np.array(webcolors.name_to_rgb(self.name))
        except ValueError as e:
            raise ValueError(f"{self.name} is not a valid color name from matplotlib or webcolors") from e

    @cached_property
    def array_alpha(self)-> np.ndarray:
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
    _data: List[float] =field(default_factory=list)


    def rebuild(self):
        """
        Rebuild the CGO data.
        """
        self._data.clear()

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
        
        cmd.load_cgo(self.data, name)
    
    
@dataclass
class Sphere(GraphicObject):
    center: Point=Point(0,0,0) 
    radius: float=0.0
    color: Color=Color('w')

    def rebuild(self):
        

        self._data=[
            *self.color.as_cgo,
            cgo.SPHERE,
            *self.center.array,
            self.radius,
        ]

@dataclass
class Cylinder(GraphicObject):
    point1: Point = Point(0, 0, 0)
    point2: Point = Point(1, 1, 1)
    radius: float = 1.0
    color1: Color = Color('w')
    color2: Color = Color('b')

    def rebuild(self):
        self._data=[
            cgo.CYLINDER,
            *self.point1.array,
            *self.point2.array,
            self.radius,
            *self.color1.as_cgo,
            *self.color2.as_cgo,
        ]

        
@dataclass
class Doughnut(GraphicObject): # Torus
    center: Point = Point(0.0, 0.0, 0.0)
    normal: Point = Point(0.0, 0.0, 1.0)
    radius: float = 1.0
    color: Color = Color('w')
    cradius: float = 0.25
    samples: int = 20
    csamples: int = 20

    # from pymol.cgobuilder.Torus
    def rebuild(self) -> None:
        """
        Rebuilds torus
        """
        obj = []

        axis = cpv.cross_product(self.normal.array(), (0., 0., 1.))
        angle = -cpv.get_angle(self.normal.array(), (0., 0., 1.))
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
            obj.extend(self.color.array)

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
    radius_base: float=0.0
    color_tip: Color = Color('w')
    color_base:Color=Color('g')

    caps: tuple[float,float]= (1, 0)

    def rebuild(self) -> None:
        """
        Rebuilds cone
        """
        self._data=[
                cgo.CONE,
                *self.tip.array,
                *self.base_center.array,
                self.radius_tip, self.radius_base,
                *self.color_tip.array,
                *self.color_base.array,
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
        super().rebuild()
        self._data.extend(
            [
                cgo.BEZIER,
                *Point.as_arrays(
                    (self.control_pt_A,
                    self.A_right_handle,
                    self.B_left_handle,
                    self.control_pt_B,)
                )
            ]
        )



@dataclass
class Triangle(GraphicObject):
    vertex_a: Point = Point(1, 0, 0)
    vertex_b: Point = Point(0, 1, 0)
    vertex_c: Point = Point(0, 0, 1)

    normal_a: Point = Point(1, 0, 0)
    normal_b: Point = Point(0, 1, 0)
    normal_c: Point = Point(0, 0, 1)

    color_a: Color = Color('r')
    color_b: Color = Color('g')
    color_c: Color = Color('b')

    def rebuild(self):
        self._data=[
                *Point.as_arrays((self.vertex_a, self.vertex_b, self.vertex_c)),
                *Point.as_arrays((self.normal_a, self.normal_b, self.normal_c)),
                *Color.as_arrays((self.color_a, self.color_b, self.color_c))
            ]



class TriangleSimple(GraphicObject):
    vertex_a: Point = Point(1, 0, 0)
    vertex_b: Point = Point(0, 1, 0)
    vertex_c: Point = Point(0, 0, 1)

    color_a: Color = Color('r')
    color_b: Color = Color('g')
    color_c: Color = Color('b')


    def rebuild(self):

        self._data=[
                cgo.BEGIN, cgo.TRIANGLE,

                *self.color_a.as_cgo,
                *self.vertex_a.as_vertex,
                
                *self.color_b.as_cgo,
                *self.vertex_b.as_vertex,

                *self.color_c.as_cgo,
                *self.vertex_c.as_vertex,
                
                cgo.END
            ]


@dataclass
class Line(GraphicObject):
    start: Point=Point(0, 0, 0)
    end: Point= Point(0, 0, 1)

    @property
    def points(self):
        return (self.start, self.end)

    def rebuild(self):
        self._data= [
                *Point.as_vertexes((self.start, self.end))
            ]

@dataclass
class Lines(GraphicObject):
    color: Color=Color('w')

    lines: tuple[Line]=field(default_factory=tuple)


    def rebuild(self):
        self._data=[
            *self.color.as_cgo, 
        ]
        for line in self.lines:
            self._data.extend(line.data)