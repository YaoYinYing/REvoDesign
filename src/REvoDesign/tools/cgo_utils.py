import itertools
import math
import string
from abc import abstractmethod
from dataclasses import dataclass, field
from functools import cached_property
from typing import Iterable, List, Literal, Optional, Union
import numpy as np
import tree
import webcolors
from chempy import cpv
from fontTools.ttLib import TTFont
from immutabledict import immutabledict
from matplotlib import _color_data as _cdata
from pymol import cgo, cmd
from pymol.vfont import plain
from REvoDesign.tools.utils import pairwise, pairwise_loop, timing
DEBUG = True
BASE_COLORS: immutabledict[str, str] = immutabledict({name: webcolors.rgb_to_hex(
    tuple(map(lambda x: int(255 * x), value))) for name, value in _cdata.BASE_COLORS.items()})  
TABLEAU_COLORS: immutabledict[str, str] = immutabledict(
    {name.lstrip('tab:'): value for name, value in _cdata.TABLEAU_COLORS.items()})
CSS4_COLORS: immutabledict[str, str] = immutabledict(_cdata.CSS4_COLORS)
XKCD_COLORS: immutabledict[str, str] = immutabledict(
    {name.lstrip('xkcd:').replace(' ', '_'): value for name, value in _cdata.XKCD_COLORS.items()})
COLOR_TABLES = (BASE_COLORS, TABLEAU_COLORS, CSS4_COLORS, XKCD_COLORS,)
def not_none_float(*args: Optional[float]):
    for idx, float_in in enumerate(args):
        if float_in is None:
            continue
        try:
            return float(float_in)
        except Exception as e:
            print(f'Skip {idx} ({float_in}): {e}')
    return 0.0
@dataclass(frozen=True)
class Point:
    x: float
    y: float
    z: float
    def __add__(self, other: 'Point') -> 'Point':
        return Point.from_array(self.array + other.array)
    def __sub__(self, other: 'Point'):
        return Point.from_array(self.array - other.array)
    def __truediv__(self, other: float) -> 'Point':
        return Point.from_array(self.array / other)
    def __mul__(self, other: float) -> 'Point':
        return Point.from_array(self.array * other)
    @property
    def copy(self):
        return Point.from_array(self.array)
    @classmethod
    def dot(cls, point1: 'Point', point2: 'Point') -> float:
        return np.dot(point1.array, point2.array)
    @classmethod
    def cross(cls, point1: 'Point', point2: 'Point'):
        return cls.from_array(np.cross(point1.array, point2.array))
    @cached_property
    def array(self) -> np.ndarray:
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
    def delta_xyz(self, point: 'Point') -> np.ndarray:
        return point.array - self.array
    def center_xyz(self, point: 'Point') -> np.ndarray:
        return (point.array - self.array) / 2
    def distance_to(self, point: 'Point') -> float:
        return np.linalg.norm(point.array - self.array).astype(float)
    @classmethod
    def from_array(cls, array: np.ndarray) -> 'Point':
        return cls(*array)
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
            if DEBUG:
                print(f'[DEBUG] {name}: {cdict[name]}')
            return np.array(webcolors.hex_to_rgb(cdict[name]), dtype=float) / 255  
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
        return np.concatenate((np.array([cgo.ALPHA, self.alpha, cgo.COLOR]), self.array))
@dataclass
class GraphicObject:
    def rebuild(self):
        self._data: List[float] = []
    def __post_init__(self):
        self.rebuild()
    @property
    def data(self):
        return self._data
    def load_as(self, name: str, *args, **kwargs):
        if name in cmd.get_names():
            cmd.delete(name)
        if DEBUG:
            print(f'[DEBUG]: {self.__class__.__name__}: \n{self.data}')
        cmd.load_cgo(self.data, name, *args, **kwargs)
@dataclass
class PseudoCurve(GraphicObject):
    control_points: List[Point]
    color: Optional[str] = None
    steps: int = 50
    def check_control_points(
            self,
            num_min: Optional[int] = None,
            num_max: Optional[int] = None,
            attr_name: str = 'control_points'):
        len_cp = len(getattr(self, attr_name))
        if num_min and len_cp < num_min:
            raise ValueError(f'Number of Control Points mismatch. Required {num_min} as minimum but got {len_cp}')
        if num_max and len_cp > num_max:
            raise ValueError(f'Number of Control Points mismatch. Required {num_max} as maximum but got {len_cp}')
    @abstractmethod
    def sample(self) -> List["Point"]:
    def rebuild(self) -> None:
        vertices_points = self.sample()  
        cgo_obj = []
        if self.color is not None:
            cgo_obj.extend(Color(self.color).as_cgo)  
        cgo_obj.extend(Point.as_vertexes(vertices_points))  
        self._data = cgo_obj
@dataclass
class PseudoBezier(PseudoCurve):
    def sample(self) -> List[Point]:
        self.check_control_points(4, 4)
        control_points = self.control_points
        n = len(control_points) - 1
        points = []
        t_values = np.linspace(0, 1, self.steps + 1)
        for t in t_values:
            x = y = z = 0.0
            for j, cp in enumerate(control_points):
                bernstein = math.comb(n, j) * (t ** j) * ((1 - t) ** (n - j))
                x += cp.x * bernstein
                y += cp.y * bernstein
                z += cp.z * bernstein
            points.append(Point(x, y, z))
        return points
@dataclass
class PseudoCatmullRom(PseudoCurve):
    def sample(self) -> List[Point]:
        self.check_control_points(num_min=4)
        points = []
        for i in range(1, len(self.control_points) - 2):
            P0 = self.control_points[i - 1]
            P1 = self.control_points[i]
            P2 = self.control_points[i + 1]
            P3 = self.control_points[i + 2]
            t_values = np.linspace(0, 1, self.steps)
            for t in t_values:
                t2 = t * t
                t3 = t2 * t
                x = 0.5 * ((2 * P1.x) +
                           (-P0.x + P2.x) * t +
                           (2 * P0.x - 5 * P1.x + 4 * P2.x - P3.x) * t2 +
                           (-P0.x + 3 * P1.x - 3 * P2.x + P3.x) * t3)
                y = 0.5 * ((2 * P1.y) +
                           (-P0.y + P2.y) * t +
                           (2 * P0.y - 5 * P1.y + 4 * P2.y - P3.y) * t2 +
                           (-P0.y + 3 * P1.y - 3 * P2.y + P3.y) * t3)
                z = 0.5 * ((2 * P1.z) +
                           (-P0.z + P2.z) * t +
                           (2 * P0.z - 5 * P1.z + 4 * P2.z - P3.z) * t2 +
                           (-P0.z + 3 * P1.z - 3 * P2.z + P3.z) * t3)
                points.append(Point(x, y, z))
        points.append(self.control_points[-2])
        return points
@dataclass
class PseudoBSpline(PseudoCurve):
    degree: int = 3
    knots: Optional[List[float]] = None
    def sample(self) -> List[Point]:
        from scipy.interpolate import BSpline
        n = len(self.control_points) - 1
        p = self.degree
        if self.knots is None:
            self.knots = [0.0] * (p + 1) + list(range(1, n - p + 1)) + [n - p + 1] * (p + 1)
        ctrl_pts = np.array([[pt.x, pt.y, pt.z] for pt in self.control_points])
        u_start = self.knots[p]
        u_end = self.knots[n + 1]
        u_vals = np.linspace(u_start, u_end, self.steps + 1)
        bspline = BSpline(self.knots, ctrl_pts, p)
        spline_pts = bspline(u_vals)
        return [Point(x, y, z) for x, y, z in spline_pts]
@dataclass
class PseudoHermite(PseudoCurve):
    tangents: List[Point] = field(default_factory=list)
    def sample(self) -> List[Point]:
        self.check_control_points(2, 2)
        self.check_control_points(2, 2, 'tangents')
        A = self.control_points[0]
        B = self.control_points[1]
        T0 = self.tangents[0]
        T1 = self.tangents[1]
        points = []
        t_values = np.linspace(0, 1, self.steps + 1)
        for t in t_values:
            t2 = t * t
            t3 = t2 * t
            h00 = 2 * t3 - 3 * t2 + 1
            h10 = t3 - 2 * t2 + t
            h01 = -2 * t3 + 3 * t2
            h11 = t3 - t2
            x = h00 * A.x + h10 * T0.x + h01 * B.x + h11 * T1.x
            y = h00 * A.y + h10 * T0.y + h01 * B.y + h11 * T1.y
            z = h00 * A.z + h10 * T0.z + h01 * B.z + h11 * T1.z
            points.append(Point(x, y, z))
        return points
@dataclass
class PseudoArc(PseudoCurve):
    radius: float = 0.0
    angles: List[float] = field(default_factory=lambda: [0.0, 0.0])
    def sample(self) -> List[Point]:
        self.check_control_points(1, 1)
        self.check_control_points(2, 2, 'angles')
        center = self.control_points[0]
        start_angle, end_angle = self.angles
        angles = np.linspace(start_angle, end_angle, self.steps + 1)
        points = []
        for angle in angles:
            x = center.x + self.radius * np.cos(angle)
            y = center.y + self.radius * np.sin(angle)
            z = center.z
            points.append(Point(x, y, z))
        return points
@dataclass
class PseudoNURBS(PseudoCurve):
    weights: List[float] = field(default_factory=list)
    degree: int = 3
    knots: Optional[List[float]] = None
    def sample(self) -> List[Point]:
        n = len(self.control_points) - 1
        p = self.degree
        if len(self.weights) != n + 1:
            raise ValueError("The number of weights must equal the number of control points")
        if self.knots is None:
            self.knots = [0.0] * (p + 1) + list(range(1, n - p + 1)) + [n - p + 1] * (p + 1)
        u_start = self.knots[p]
        u_end = self.knots[n + 1]
        u_vals = np.linspace(u_start, u_end, self.steps + 1)
        points = []
        for u in u_vals:
            numerator = np.zeros(3)
            denominator = 0.0
            for i in range(n + 1):
                N = self.basis(i, p, u, self.knots)
                w = self.weights[i]
                numerator += N * w * np.array(self.control_points[i].array)
                denominator += N * w
            if denominator != 0:
                pt = numerator / denominator
            else:
                pt = np.zeros(3)
            points.append(Point(pt[0], pt[1], pt[2]))
        return points
    def basis(self, i: int, p: int, u: float, knots: List[float]) -> float:
        if p == 0:
            if knots[i] <= u < knots[i + 1]:
                return 1.0
            if u == knots[-1] and knots[i + 1] == knots[-1]:
                return 1.0
            return 0.0
        denom1 = knots[i + p] - knots[i]
        denom2 = knots[i + p + 1] - knots[i + 1]
        term1 = 0.0
        term2 = 0.0
        if denom1 != 0:
            term1 = ((u - knots[i]) / denom1) * self.basis(i, p - 1, u, knots)
        if denom2 != 0:
            term2 = ((knots[i + p + 1] - u) / denom2) * self.basis(i + 1, p - 1, u, knots)
        return term1 + term2
@dataclass
class LineVertex(GraphicObject):
    point: Union[Point, PseudoCurve]
    width: Optional[float] = None
    color: Optional[str] = None
    def rebuild(self):
        self._data = []
        if self.width:
            self._data.extend([cgo.LINEWIDTH, self.width])
        if self.color:
            self._data.extend(Color(self.color).as_cgo)
        if isinstance(self.point, Point):
            self._data.extend(self.point.as_vertex)
        elif isinstance(self.point, PseudoCurve):
            self._data.extend(self.point.data)
        else:
            raise NotImplementedError('this curve is not currently supported')
    @classmethod
    def from_points(cls, points: Iterable[Union[Point, Iterable[float]]], width: Optional[float]
                    = None, color: Optional[str] = None) -> tuple['LineVertex', ...]:
        return tuple(cls(p if isinstance(p, Point) else Point(*p), width=width, color=color) for p in points)
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
class Sausage(GraphicObject):
    p1: Point
    p2: Point
    radius: float
    color_1: str
    color_2: str
    def rebuild(self):
        self._data = [
            cgo.SAUSAGE,
            *self.p1.array,
            *self.p2.array,
            self.radius,
            *Color(self.color_1).array,
            *Color(self.color_2).array
        ]
@dataclass
class Doughnut(GraphicObject):  
    center: Point = Point(0.0, 0.0, 0.0)
    normal: Point = Point(0.0, 0.0, 1.0)
    radius: float = 1.0
    color: str = 'w'
    cradius: float = 0.25
    samples: int = 20
    csamples: int = 20
    def rebuild(self) -> None:
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
    tip: Point
    base_center: Point
    radius_tip: float
    radius_base: float
    color_tip: str = 'w'
    color_base: str = 'g'
    caps: tuple[float, float] = (1, 0)
    def rebuild(self) -> None:
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
class Cube(GraphicObject):
    p1: Point = Point(0, 0, 0)
    p2: Point = Point(1, 1, 1)
    color_w: str = 'yellow'
    color_x: str = 'red'
    color_y: str = 'green'
    color_z: str = 'blue'
    wire_frame: bool = True
    linewidth: float = 2
    def _rebuild_wireframe(self):
        self._data = [
            cgo.LINEWIDTH, float(self.linewidth),
            cgo.BEGIN, cgo.LINES,
        ]
        for i, j in itertools.combinations('xyz', r=2):
            for _i, _j in itertools.product(
                (getattr(self.p1, i), getattr(self.p2, i)),
                (getattr(self.p1, j), getattr(self.p2, j))
            ):
                move_dict = {i: _i, j: _j}
                self._data.extend([
                    *Color(getattr(self, f'color_{"xyz".replace(i, "").replace(j, "")}')).as_cgo,
                    *self.p1.move(**move_dict).as_vertex,
                    *self.p2.move(**move_dict).as_vertex,
                ])
        self._data.append(cgo.END)
    def _rebuild_solid(self):
        def make_face(a: Point, b: Point, c: Point, d: Point) -> List[float]:
            face = Square(
                corner_a=a, corner_b=b, corner_c=c, corner_d=d,
                color_a=self.color_w,
                color_b=self.color_x,
                color_c=self.color_y,
                color_d=self.color_z
            )
            face.rebuild()
            return face.data
        x1, y1, z1 = self.p1.x, self.p1.y, self.p1.z
        x2, y2, z2 = self.p2.x, self.p2.y, self.p2.z
        face1_data = make_face(
            Point(x1, y1, z1), Point(x1, y1, z2), Point(x1, y2, z2), Point(x1, y2, z1)
        )
        face2_data = make_face(
            Point(x2, y1, z1), Point(x2, y2, z1), Point(x2, y2, z2), Point(x2, y1, z2)
        )
        face3_data = make_face(
            Point(x1, y1, z1), Point(x2, y1, z1), Point(x2, y1, z2), Point(x1, y1, z2)
        )
        face4_data = make_face(
            Point(x1, y2, z1), Point(x1, y2, z2), Point(x2, y2, z2), Point(x2, y2, z1)
        )
        face5_data = make_face(
            Point(x1, y1, z1), Point(x1, y2, z1), Point(x2, y2, z1), Point(x2, y1, z1)
        )
        face6_data = make_face(
            Point(x1, y1, z2), Point(x2, y1, z2), Point(x2, y2, z2), Point(x1, y2, z2)
        )
        self._data = face1_data + face2_data + face3_data + \
            face4_data + face5_data + face6_data
    def rebuild(self):
        if self.wire_frame:
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
class PolyLines(GraphicObject):
    width: float
    color: str
    points: Iterable[LineVertex]
    line_type: Literal['LINE_STRIP', 'LINE_LOOP', 'TRIANGLE_STRIP', 'TRIANGLE_FAN'] = 'LINE_STRIP'
    def rebuild(self):
        self._data = [
            cgo.LINEWIDTH, self.width,
            *Color(self.color).as_cgo,
            cgo.BEGIN, getattr(cgo, self.line_type),
        ]
        for pv in self.points:
            self._data.extend([*pv.data])
        self._data.append(cgo.END)
@dataclass
class Arrow(GraphicObject):
    start: Point  
    point_to: Point  
    radius: float = 0.1  
    header_height: float = 0.25
    header_ratio: float = 1.618
    color_header: str = 'red'
    color_tail: str = 'white'
    @property
    def cone_base_r(self):
        return self.radius * self.header_ratio  
    @property
    def cyl_length(self) -> float:
        return max(self.point_to.distance_to(self.start) - self.header_height, 0)
    @cached_property
    def joint(self):
        return self.start + (self.point_to - self.start) * self.cyl_length / self.point_to.distance_to(self.start)
    def rebuild(self):
        go = GraphicObjectCollection(
            [
                Cylinder(
                    self.start,
                    self.joint,
                    self.radius,
                    self.color_tail, self.color_tail
                ),
                Cone(
                    self.point_to,
                    self.joint,
                    0.0,
                    self.cone_base_r,
                    self.color_header, self.color_header,
                    (1, 1)
                ),
            ]
        )
        go.rebuild()
        self._data = go.data
@dataclass
class RoundedRectangle(GraphicObject):
    center: Point
    axis1: Point
    axis2: Point
    width: float
    height: float
    radius: float
    color: str
    line_width: float
    steps: int = 50
    def local_to_global(self, u: float, v: float) -> Point:
        global_coord = self.center.array + u * self.axis1.array + v * self.axis2.array
        return Point(global_coord[0], global_coord[1], global_coord[2])
    def rebuild(self) -> None:
        self.radius = min(self.width / 2, self.radius)
        half_w = self.width / 2
        half_h = self.height / 2
        r = self.radius
        k = 0.5522847498  
        edge_bottom_start = (-half_w + r, -half_h)
        edge_bottom_end = (half_w - r, -half_h)
        edge_right_start = (half_w, -half_h + r)
        edge_right_end = (half_w, half_h - r)
        edge_top_start = (half_w - r, half_h)
        edge_top_end = (-half_w + r, half_h)
        edge_left_start = (-half_w, half_h - r)
        edge_left_end = (-half_w, -half_h + r)
        cp1_br = (edge_bottom_end[0] + k * r, edge_bottom_end[1])
        cp2_br = (edge_right_start[0], edge_right_start[1] - k * r)
        cp1_tr = (edge_right_end[0], edge_right_end[1] + k * r)
        cp2_tr = (edge_top_start[0] + k * r, edge_top_start[1])
        cp1_tl = (edge_top_end[0] - k * r, edge_top_end[1])
        cp2_tl = (edge_left_start[0], edge_left_start[1] + k * r)
        cp1_bl = (edge_left_end[0], edge_left_end[1] - k * r)
        cp2_bl = (edge_bottom_start[0] - k * r, edge_bottom_start[1])
        bottom_right_corner = PseudoBezier(
            control_points=[
                self.local_to_global(*edge_bottom_end),
                self.local_to_global(*cp1_br),
                self.local_to_global(*cp2_br),
                self.local_to_global(*edge_right_start)
            ],
            color=self.color,
            steps=self.steps
        )
        top_right_corner = PseudoBezier(
            control_points=[
                self.local_to_global(*edge_right_end),
                self.local_to_global(*cp1_tr),
                self.local_to_global(*cp2_tr),
                self.local_to_global(*edge_top_start)
            ],
            color=self.color,
            steps=self.steps
        )
        top_left_corner = PseudoBezier(
            control_points=[
                self.local_to_global(*edge_top_end),
                self.local_to_global(*cp1_tl),
                self.local_to_global(*cp2_tl),
                self.local_to_global(*edge_left_start)
            ],
            color=self.color,
            steps=self.steps
        )
        bottom_left_corner = PseudoBezier(
            control_points=[
                self.local_to_global(*edge_left_end),
                self.local_to_global(*cp1_bl),
                self.local_to_global(*cp2_bl),
                self.local_to_global(*edge_bottom_start)
            ],
            color=self.color,
            steps=self.steps
        )
        vertices = [
            LineVertex(self.local_to_global(*edge_bottom_start)),   
            LineVertex(self.local_to_global(*edge_bottom_end)),     
            LineVertex(bottom_right_corner),                        
            LineVertex(self.local_to_global(*edge_right_end)),      
            LineVertex(top_right_corner),                           
            LineVertex(self.local_to_global(*edge_top_end)),        
            LineVertex(top_left_corner),                            
            LineVertex(self.local_to_global(*edge_left_end)),       
            LineVertex(bottom_left_corner)                          
        ]
        poly = PolyLines(
            width=self.line_width,
            color=self.color,
            points=vertices,
            line_type='LINE_LOOP'
        )
        poly.rebuild()
        self._data = poly._data
@dataclass
class Ellipse(GraphicObject):
    center: Point
    axis1: Point
    axis2: Point
    major_radius: float
    minor_radius: float
    color: str
    line_width: float
    steps: int = 50
    def local_to_global(self, u: float, v: float) -> Point:
        global_coord = self.center.array + u * self.axis1.array + v * self.axis2.array
        return Point(global_coord[0], global_coord[1], global_coord[2])
    def rebuild(self) -> None:
        t_values = np.linspace(0, 2 * math.pi, self.steps + 1)
        points = []
        for t in t_values:
            u = self.major_radius * math.cos(t)
            v = self.minor_radius * math.sin(t)
            points.append(self.local_to_global(u, v))
        vertices = [LineVertex(pt) for pt in points]
        poly = PolyLines(
            width=self.line_width,
            color=self.color,
            points=vertices,
            line_type='LINE_LOOP'
        )
        poly.rebuild()
        self._data = poly.data
@dataclass
class Ellipsoid(GraphicObject):
    center: Point
    radius_x: float
    radius_y: float
    radius_z: float
    color: str
    steps_theta: int = 50
    steps_phi: int = 50
    def rebuild(self) -> None:
        theta = np.linspace(0, math.pi, self.steps_theta + 1)  
        phi = np.linspace(0, 2 * math.pi, self.steps_phi + 1)    
        theta_grid, phi_grid = np.meshgrid(theta, phi, indexing='ij')
        x = self.center.x + self.radius_x * np.sin(theta_grid) * np.cos(phi_grid)
        y = self.center.y + self.radius_y * np.sin(theta_grid) * np.sin(phi_grid)
        z = self.center.z + self.radius_z * np.cos(theta_grid)
        vertices_grid = np.stack((x, y, z), axis=-1)
        triangles = []
        for i in range(self.steps_theta):
            for j in range(self.steps_phi):
                p0 = Point(*vertices_grid[i, j])
                p1 = Point(*vertices_grid[i + 1, j])
                p2 = Point(*vertices_grid[i + 1, j + 1])
                p3 = Point(*vertices_grid[i, j + 1])
                triangles.append([p0, p1, p2])
                triangles.append([p0, p2, p3])
        cgo_obj = []
        cgo_obj.extend(Color(self.color).as_cgo)
        cgo_obj.extend([cgo.BEGIN, cgo.TRIANGLES])
        for tri in triangles:
            for vertex in tri:
                cgo_obj.extend(vertex.as_vertex)
        cgo_obj.append(cgo.END)
        self._data = cgo_obj
@dataclass
class Polygon(GraphicObject):
    vertices: List[Point]
    color: str
    def rebuild(self) -> None:
        cgo_obj = []
        cgo_obj.extend(Color(self.color).as_cgo)
        cgo_obj.extend([cgo.BEGIN, cgo.TRIANGLE_FAN])
        for vertex in self.vertices:
            cgo_obj.extend(vertex.as_vertex)
        cgo_obj.append(cgo.END)
        self._data = cgo_obj
@dataclass
class Polyhedron(GraphicObject):
    vertices: List[Point]
    faces: List[List[int]]
    color: str
    def rebuild(self) -> None:
        cgo_obj = []
        cgo_obj.extend(Color(self.color).as_cgo)
        for face in self.faces:
            if len(face) < 3:
                continue  
            cgo_obj.extend([cgo.BEGIN, cgo.TRIANGLE_FAN])
            for idx in face:
                vertex = self.vertices[idx]
                cgo_obj.extend(vertex.as_vertex)
            cgo_obj.append(cgo.END)
        self._data = cgo_obj
def to3d(pt):
    pt = tuple(pt)
    if len(pt) == 2:
        return pt + (0.0,)
    return pt
def sample_quadratic_bezier(p0, p1, p2, num=10):
    def ensure3d(pt):
        pt = np.array(pt, dtype=float)
        if pt.shape[0] == 2:
            pt = np.append(pt, 0.0)
        return pt
    p0 = ensure3d(p0)
    p1 = ensure3d(p1)
    p2 = ensure3d(p2)
    pts = []
    for t in np.linspace(0, 1, num):
        pt = (1 - t)**2 * p0 + 2 * (1 - t) * t * p1 + t**2 * p2
        pts.append(tuple(pt))
    return pts
class PolygonPen:
    def __init__(self, sample_num: int = 10):
        self.contours: List[List[Point]] = []
        self.current_contour: List[Point] = []
        self.sample_num = sample_num
    def moveTo(self, pt):
        p = Point(*to3d(pt))
        self.current_contour = [p]
    def lineTo(self, pt):
        p = Point(*to3d(pt))
        self.current_contour.append(p)
    def qCurveTo(self, *points):
        pts = list(points)
        if pts[-1] is None:
            pts = pts[:-1]
        start = self.current_contour[-1]
        for i in range(0, len(pts) - 1, 2):
            control = pts[i]
            end = pts[i + 1]
            sampled = sample_quadratic_bezier(start.array, control, end, num=self.sample_num)
            for coord in sampled[1:]:
                self.current_contour.append(Point(coord[0], coord[1], coord[2]))
            start = Point(*to3d(end))
    def closePath(self):
        if self.current_contour:
            self.contours.append(self.current_contour)
            self.current_contour = []
    def endPath(self):
        self.closePath()
@dataclass
class TextCharPolygon(GraphicObject):
    char: str
    font_path: str
    color: str
    scale: float = 1.0
    offset: Optional[Point] = None
    width: float = 1.0
    format: Literal['LINE_LOOP', 'SAUSAGE', 'TRIANGLE_FAN'] = 'LINE_LOOP'
    sample_num: int = 10
    def rebuild(self) -> None:
        font = TTFont(self.font_path)
        cmap = font['cmap'].getBestCmap()  
        glyph_name = cmap.get(ord(self.char))
        if glyph_name is None:
            raise ValueError(f"Glyph for character '{self.char}' not found in {self.font_path}")
        glyph_set = font.getGlyphSet()
        glyph = glyph_set[glyph_name]
        pen = PolygonPen(sample_num=self.sample_num)
        glyph.draw(pen)
        polygons = pen.contours
        scaled_polygons: List[List[Point]] = []
        for contour in polygons:
            scaled_contour: List[Point] = []
            for pt in contour:
                x = pt.x * self.scale
                y = pt.y * self.scale
                z = pt.z * self.scale
                if self.offset:
                    x += self.offset.x
                    y += self.offset.y
                    z += self.offset.z
                scaled_contour.append(Point(x, y, z))
            scaled_polygons.append(scaled_contour)
        cgo_obj = []
        cgo_obj.extend(Color(self.color).as_cgo)
        if self.format == 'LINE_LOOP':
            for contour in scaled_polygons:
                if contour[0].array.tolist() != contour[-1].array.tolist():
                    contour.append(contour[0])
                poly = PolyLines(
                    width=self.width,
                    color=self.color,
                    points=[LineVertex(pt) for pt in contour],
                    line_type=self.format,
                )
                poly.rebuild()
                cgo_obj.extend(poly.data)
        elif self.format == 'SAUSAGE':
            for contour in scaled_polygons:
                cgo_obj.extend(
                    tree.flatten(
                        [
                            Sausage(p1, p2, radius=self.width, color_1=self.color, color_2=self.color).data
                            for p1, p2 in pairwise_loop(contour)
                        ]
                    )
                )
        else:
            raise NotImplementedError(f'{self.format} is not support.')
        self._data = cgo_obj
@dataclass
class TextBoard(GraphicObject):
    text: str
    font_path: str
    start_point: Point = Point(0, 0, 0)
    color: str = 'random'
    scale: float = 0.1
    offset = Point(0, 0, 0)
    width: float = 5
    space: float = 100
    format: Literal['LINE_LOOP', 'SAUSAGE', 'TRIANGLE_FAN'] = 'SAUSAGE'
    sample_num: int = 5
    def rebuild(self):
        import random
        if self.color == 'random':
            color = random.sample(list(CSS4_COLORS.keys()), len(self.text))
        else:
            color = [self.color for _ in self.text]
        goc = GraphicObjectCollection([])
        curser_point = self.start_point.copy
        origin_point = curser_point.copy
        for (_, char), (_, c) in zip(enumerate(self.text), enumerate(color)):
            if char in string.printable:
                space = self.space
            else:
                space = self.space * 2
            if char != '\n':
                curser_point = curser_point.move(x=curser_point.x + space)
            else:
                curser_point = curser_point.move(x=origin_point.x, y=curser_point.y - self.space * 2)
                continue
            goc.objects.append(TextCharPolygon(
                char=char,
                font_path=self.font_path,
                color=c,
                scale=self.scale,
                offset=curser_point,
                width=self.width,
                format='SAUSAGE',
                sample_num=self.sample_num
            ))
        goc.rebuild()
        self._data = goc.data
@dataclass
class GraphicObjectCollection(GraphicObject):
    objects: List[GraphicObject]
    force_to_rebuild: bool = False
    def rebuild(self):
        self._data = []
        for go_idx, go in enumerate(self.objects):
            print(f"Adding: 
            if self.force_to_rebuild:
                go.rebuild()
        self._data.extend(tree.flatten([go.data for go in self.objects]))
def __easter_egg():
    if any(not n.startswith('_') for n in cmd.get_names()):
        return
    poision = GraphicObjectCollection([
        Sphere(
            center=Point(-2, 0, 0),
            radius=1,
            color='white'
        ),
        Cylinder(
            Point(-2, 0, 0),
            Point(0.5, 0, 0),
            radius=1,
            color1='white',
            color2='white'
        ),
        Cylinder(
            Point(0, 0, 0),
            Point(2, 0, 0),
            radius=1.015,
            color1='red',
            color2='red'
        ),
        Sphere(
            center=Point(2, 0, 0),
            radius=1.015,
            color='red'
        ),
        PolyLines(
            5, 'black',
            [
                LineVertex(Point(-1.6, 0.5, 0.9)),  
                LineVertex(Point(1.6, 0.5, 0.9)),  
                LineVertex(PseudoBezier(
                    [Point(1.6, 0.5, 0.9),  
                     Point(2.2, 0.5, 1.08),  
                     Point(2.2, -0.5, 1.08),  
                     Point(1.6, -0.5, 0.9)]  
                )),
                LineVertex(Point(1.6, -0.5, 0.9)),  
                LineVertex(Point(-1.6, -0.5, 0.9)),  
                LineVertex(PseudoBezier(
                    [Point(-1.6, -0.5, 0.9),  
                     Point(-2.2, -0.5, 1.05),  
                     Point(-2.2, 0.5, 1.05),  
                     Point(-1.6, 0.5, 0.9)]  
                )),
            ], line_type='LINE_LOOP'
        )
    ]
    )
    cgo.cyl_text(
        poision.data,
        plain,
        Point(-1.5, -0.25, 1.01).array,
        'APTX-4869',
        0.03,
        axes=[Point(0.5, 0, 0).array, Point(0, 0.5, 0).array, Point(0, 0, 0.5).array],
        color=Color('black').array)
    poision.load_as('APTX-4869')
    cmd.turn('z', 16)
    cmd.zoom('APTX-4869', 0)
    cmd.movie.add_roll(8, loop=0, axis='y', start=1)
    cmd.set('movie_fps', 90)
    print(__easter_egg.__doc__)
    cmd.mplay()
cmd.extend('hello_revodesign', __easter_egg)