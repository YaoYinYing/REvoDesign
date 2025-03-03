'''
Utilities for pymol.cgo, partially modified from `pymol.cgobuilder`

This module is aimed at building programable application protocol for CGO creating via pymol.cgo module


# docs of cgo:

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
from typing import Iterable, List, Optional, Literal, Tuple, Union
import numpy as np
import webcolors
from chempy import cpv
from immutabledict import immutabledict
from matplotlib import _color_data as _cdata
from pymol import cgo, cmd



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

def not_none_float(*args: Optional[float]):
    """
    Returns the first non-None float value from the given arguments.
    
    If all arguments are None or cannot be converted to float, it returns 0.0.
    This function is designed to simplify the extraction and conversion of float values,
    especially when dealing with input data that may contain None values.
    
    Parameters:
    *args: Optional[float] - One or more optional float type arguments.
    
    Returns:
    float - The first non-None float value, or 0.0 if none can be found.
    """
    # Iterate over all input arguments
    for idx, float_in in enumerate(args):
        # Skip the current argument if it is None
        if float_in is None:
            continue
        try:
            # Attempt to convert the current argument to float and return it
            return float(float_in)
        except Exception as e:
            # Print an error message if conversion fails and continue to the next argument
            print(f'Skip {idx} ({float_in}): {e}')
    # Return the default value 0.0 if no valid float can be found
    return 0.0
@dataclass(frozen=True)
class Point:
    '''
    A Point vector object in PyMOL's coordinate system
    This class represents a point in 3D space with coordinates (x, y, z).
    It provides methods to convert the point to a numpy array, and to generate CGO commands for vertices and normals.
    '''
    x: float
    y: float
    z: float

    @cached_property
    def array(self):
        '''
        Convert the point to a numpy array
        This method converts the point's coordinates into a numpy array, facilitating subsequent vector operations.
        '''
        return np.array([self.x, self.y, self.z])

    @cached_property
    def as_vertex(self):
        '''
        Generate a CGO vertex command for the point
        This method inserts the point's coordinates into a CGO vertex command, used for rendering in PyMOL.
        '''
        return np.insert(cgo.VERTEX, 1, self.array)

    @cached_property
    def as_normal(self):
        '''
        Generate a CGO normal command for the point
        This method inserts the point's coordinates into a CGO normal command, used for specifying normals in PyMOL.
        '''
        return np.insert(cgo.NORMAL, 1, self.array)

    def move(self, x: Optional[float] = None, y: Optional[float] = None, z: Optional[float] = None) -> 'Point':
        '''
        Move the point
        This method allows the point to be moved along the x, y, and z axes. If a coordinate is not provided, the original value is used.
        
        Parameters:
        - x: Optional[float] = None, the new x-coordinate, if not provided, the original x-coordinate is used
        - y: Optional[float] = None, the new y-coordinate, if not provided, the original y-coordinate is used
        - z: Optional[float] = None, the new z-coordinate, if not provided, the original z-coordinate is used
        
        Returns:
        - Point: The new point after moving
        '''
        return Point(
            not_none_float(x, self.x),
            not_none_float(y, self.y),
            not_none_float(z, self.z))

    @staticmethod
    def as_arrays(points: Iterable['Point']):
        '''
        Convert a collection of points to a numpy array
        This static method converts a collection of Point objects into a single numpy array, facilitating batch processing.
        
        Parameters:
        - points: Iterable['Point'], a collection of Point objects
        
        Returns:
        - np.ndarray: A numpy array containing the coordinates of all points
        '''
        return np.concatenate(tuple(point.array for point in points))

    @staticmethod
    def as_vertexes(points: Iterable['Point']):
        '''
        Convert a collection of points to CGO vertex commands
        This static method converts a collection of Point objects into CGO vertex commands, used for batch rendering in PyMOL.
        
        Parameters:
        - points: Iterable['Point'], a collection of Point objects
        
        Returns:
        - np.ndarray: A numpy array containing the CGO vertex commands for all points
        '''
        return np.concatenate(tuple(point.as_vertex for point in points))

    @classmethod
    def from_xyz(cls, x: float, y: float, z: float):
        '''
        Create a Point object from x, y, and z coordinates
        This class method creates a new Point object using the provided x, y, and z coordinates.
        
        Parameters:
        - x: float, the x-coordinate
        - y: float, the y-coordinate
        - z: float, the z-coordinate
        
        Returns:
        - Point: The newly created Point object
        '''
        return Point(x, y, z)
    
    def delta_xyz(self, point: 'Point') -> Tuple[float, float, float]:
        return point.x-self.x, point.y-self.y, point.z-self.z
    
    def center_xyz(self, point: 'Point') -> Tuple[float, float, float]:
        return (point.x+self.x)/2, (point.y+self.y)/2, (point.z+self.z)/2

    
    def distance_to(self,point: 'Point') -> float:
        '''
        Euclidean distance from a point to this Point.

        Parameters:
        - point: Point, a target point object.

        Returns:
        - float: The Euclidean distance
        '''
        delta_xyz=self.delta_xyz(point=point)
        return math.sqrt((delta_xyz[0])**2+(delta_xyz[1])**2+(delta_xyz[2])**2)


@dataclass(frozen=True)
class Color:
    """
    Represents a color, including its name and alpha value.
    
    Attributes:
        name (str): The name of the color.
        alpha (float): The alpha value of the color, default is 1.0.
    """
    name: str
    alpha: float = 1.0

    @cached_property
    def array(self) -> np.ndarray:
        """
        Converts the color to an RGB array.
        
        Returns:
            np.ndarray: An RGB array representing the color.
            
        Raises:
            ValueError: If the color name is not valid.
        """
        # Standardize the color name for lookup
        name = self.name.lower().replace(" ", "_")
        # Iterate through the color tables to find a match
        for cdict in COLOR_TABLES:
            if name not in cdict:
                continue
            print(f'[DEBUG] {name}: {cdict[name]}')
            # Convert the found hexadecimal color value to an RGB array
            return np.array(webcolors.hex_to_rgb(cdict[name]), dtype=float) / 255  # type: ignore

        try:
            # Try to convert the color name to an RGB array using webcolors
            return np.array(webcolors.name_to_rgb(self.name), dtype=float) / 255
        except ValueError as e:
            # Raise a ValueError if the color name is not valid
            raise ValueError(f"{self.name} is not a valid color name from matplotlib or webcolors") from e

    @cached_property
    def array_alpha(self) -> np.ndarray:
        """
        Adds the alpha value to the RGB array to create an RGBA array.
        
        Returns:
            np.ndarray: An RGBA array representing the color.
        """
        # Append the alpha value to the RGB array
        return np.append(self.array, self.alpha)

    @staticmethod
    def as_arrays(colors: Iterable['Color']):
        """
        Converts a series of colors to an array of RGB arrays.
        
        Args:
            colors (Iterable['Color']): A series of Color objects.
            
        Returns:
            np.ndarray: An array consisting of the RGB arrays of all colors.
        """
        # Concatenate the RGB arrays of all colors
        return np.concatenate(tuple(color.array for color in colors))

    @staticmethod
    def as_cgos(colors: Iterable['Color']):
        """
        Converts a series of colors to an array suitable for CGO (Color Graphics Operations).
        
        Args:
            colors (Iterable['Color']): A series of Color objects.
            
        Returns:
            np.ndarray: An array consisting of the CGO representations of all colors.
        """
        # Concatenate the CGO representations of all colors
        return np.concatenate(tuple(color.as_cgo for color in colors))

    @cached_property
    def as_cgo(self):
        """
        Converts the color to a CGO (Color Graphics Operations) representation.
        
        Returns:
            np.ndarray: The CGO representation of the color.
        """
        # Insert the color code into the RGB array
        return np.insert(self.array, 0, cgo.COLOR)
@dataclass
class GraphicObject:
    """
    A base class representing a graphic object, providing methods to rebuild and load graphic data.
    """

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
        """
        Load the graphic object as a specified name. If the name is occupied, delete it to regenerate.

        Parameters:
        name (str): The name of the object, used for loading the object data into the software.

        If an object with the same name already exists, it is deleted before loading the new object.
        This prevents loading errors due to duplicate names.
        """
        if name in cmd.get_names():
            cmd.delete(name)

        print(f'[DEBUG]: {self.__class__}: \n{self.data}')
        cmd.load_cgo(self.data, name)

@dataclass
class Bezier(GraphicObject):
    """
    Defines a Bezier curve graphic object.
    This class inherits from GraphicObject and uses the dataclass decorator for automatic generation of special methods.
    """
    # The following four points define a Bezier curve:
    control_pt_A: Point  # Starting control point A
    A_right_handle: Point  # Right handle point of starting control point A
    B_left_handle: Point  # Left handle point of ending control point B
    control_pt_B: Point  # Ending control point B

    def rebuild(self) -> None:
        """
        Rebuilds bezier spline
        This method reconstructs the Bezier curve data, preparing it for rendering or other uses.
        """
        # Reconstructs the Bezier curve data, including the type of graphic object and all control points
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
class LineVertex(GraphicObject):
    """
    Represents a line vertex, inheriting from GraphicObject.
    
    This class is used to define a line drawing element, which can be a point or a Bezier curve, and can include line width and color attributes.
    
    Attributes:
    - point: A Point or Bezier instance, representing the starting point or control point of the line.
    - width: An optional float, representing the line width. If not provided, the default is None.
    - color: An optional string, representing the line color. If not provided, the default is None.
    """
    point: Union[Point, Bezier]
    width: Optional[float]=None
    color: Optional[str]=None

    def rebuild(self):
        """
        Rebuilds the line vertex data.
        
        This method initializes the internal data list, and rebuilds the line vertex data based on the width, color, and point type.
        """
        # Initialize the data list
        self._data = []
        
        # If the width is provided, add the LINEWIDTH command and width value to the data list
        if self.width:
            self._data.extend([cgo.LINEWIDTH, self.width])
        
        # If the color is provided, convert the color to a format compatible with CGO and add it to the data list
        if self.color:
            self._data.extend(Color(self.color).as_cgo)
        
        # If the point type is Point, add the point's vertex data to the data list
        if isinstance(self.point, Point):
            self._data.extend(self.point.as_vertex)
        else:
            # Currently, only Point type is supported. If another type is encountered, raise an exception
            raise NotImplementedError('Bezier is not currently supported')

@dataclass
class Sphere(GraphicObject):
    """
    Represents a sphere in 3D space, inheriting from GraphicObject.

    Attributes:
        center (Point): The center point of the sphere, default is the origin (0, 0, 0).
        radius (float): The radius of the sphere, default is 0.0.
        color (str): The color of the sphere, default is 'w' (white).
    """

    center: Point = Point(0, 0, 0)
    radius: float = 0.0
    color: str = 'w'

    def rebuild(self):
        """
        Rebuilds the sphere's data representation using CGO (Chimera Graphics Object) format.

        This method constructs the sphere's data by combining the color information and the sphere's geometric properties.
        """
        self._data = [
            *Color(self.color).as_cgo,  # Convert color to CGO format and unpack it into the data list
            cgo.SPHERE,                 # Specify the CGO object type as SPHERE
            *self.center.array,         # Unpack the center coordinates into the data list
            self.radius,                # Add the radius to the data list
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
    tip: Point
    base_center: Point

    radius_tip: float
    radius_base: float

    color_tip: str = 'w'
    color_base: str = 'g'

    # where to add caps to tip and/or base. 1 for True, 0 for False
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

        for i,j in itertools.combinations('xyz', r=2):
            for _i, _j in itertools.product(
                    (getattr(self.p1, i), getattr(self.p2, i)), 
                    (getattr(self.p1, j), getattr(self.p2, j))
                ):
                move_dict={i: _i, j:_j}
                self._data.extend([
                    *Color(getattr(self, f'color_{"xyz".replace(i, "").replace(j, "")}')).as_cgo,
                    *self.p1.move(**move_dict).as_vertex,
                    *self.p2.move(**move_dict).as_vertex,
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
    # global
    width: float
    color: str

    points: Iterable[LineVertex]
    line_type: Literal['LINE_STRIP', 'LINE_LOOP', 'TRIANGLE_STRIP', 'TRIANGLE_FAN']= 'LINE_STRIP'


    def rebuild(self):
        self._data=[
            cgo.LINEWIDTH, self.width,
            *Color(self.color).as_cgo,
            cgo.BEGIN, getattr(cgo, self.line_type),
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

# for i, j in itertools.product(range(2), repeat=2):
#     Cone(tip=Point(0, 0, 1.4),
#          base_center=Point(0,0, 0),
#          radius_tip=0.5,
#          radius_base=1.5,
#         color_base='golden', color_tip='sand_brown', caps=(i,j,)).load_as(f'dyamond_{i},{j}')


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


Cube(wire_frame=True).load_as('a_colorful_cube')
Cube(wire_frame=False).load_as('a_colorful_solid_cube')
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


# PolyLines(
#     2.0, 'yellow',
#     [LineVertex(Point(0, 0, 0) ),
#      LineVertex(Point(0, 0, 1) ),
#      LineVertex(Point(0, 1, 0) ),
#      LineVertex(Point(1, 0, 0) ),
#      LineVertex(Point(1, 1, 2) )]
# ).load_as('yellow_line_strip')


# PolyLines(
#     2.0, 'red',
#     [LineVertex(Point(0, 0, 0) ),
#      LineVertex(Point(0, 0, 1) ),
#      LineVertex(Point(0, 1, 0) ),
#      LineVertex(Point(1, 0, 0) ),
#      LineVertex(Point(1, 1, 2) )],
#      line_type='LINE_LOOP'
# ).load_as('red_line_loop')


# PolyLines(
#     2.0, 'cyan',
#     [LineVertex(Point(0, 0, 0) ),
#      LineVertex(Point(0, 0, 1) ),
#      LineVertex(Point(0, 1, 0) ),
#     ],
#      line_type='TRIANGLE_STRIP'
# ).load_as('cyan_trangle_shape')

# PolyLines(
#     2.0, 'violet',
#     [
#      LineVertex(Point(0, 0, 0) ),
#      LineVertex(Point(0, 1, 0) ),
#      LineVertex(Point(1, 0, 0) ),
#      LineVertex(Point(1, 1, 0) ),
#     ],
#      line_type='TRIANGLE_STRIP'
# ).load_as('violet_square_shape')

# PolyLines(
#     2.0, 'pink',
#     [                             # continous triangles
#      LineVertex(Point(0, 0, 0) ), # -\  triangle # 1
#      LineVertex(Point(0, 1, 0) ), #   |-'  -\  triangle # 2
#      LineVertex(Point(1, 1, 0) ), # -/       |-'  -\  triangle # 3
#      LineVertex(Point(1, 0, 0) ), #        -/       |-'
#      LineVertex(Point(1, 1, 1) ), #               -/ 
#     ],
#      line_type='TRIANGLE_STRIP'
# ).load_as('pink_3_tri_shape')

# PolyLines(
#     2.0, 'white',
#     [
#      LineVertex(Point(0, 0, 0) ),
#      LineVertex(Point(0, 1, 0) ),
#      LineVertex(Point(1, 1, 0) ),
#      LineVertex(Point(1, 0, 0) ),
     
#     ],
#      line_type='TRIANGLE_FAN'
# ).load_as('white_square')


# PolyLines(
#     2.0, 'golden',
#     [
#      LineVertex(Point(-1,1, 0) ), # left top 
#      LineVertex(Point(0, 0, 1.4) ), # tip
#      LineVertex(Point(1, 1, 0) ), # right top
#      LineVertex(Point(1, -1, 0) ), # right bottom
#      LineVertex(Point(0, 0, 1.4) ), # tip again
#      LineVertex(Point(-1, -1, 0) ), # left bottom
#      LineVertex(Point(-1,1, 0) ), # left top back
#     ],
#      line_type='TRIANGLE_STRIP'
# ).load_as('pyramid')


# PolyLines(
#     4.0, 'white',
#     [
#      LineVertex(Point(-1,1, 0) ),
#      LineVertex(Point(0, 0, 1.4) ),
#      LineVertex(Point(1, 1, 0) ),
#      LineVertex(Point(1, -1, 0) ),
#      LineVertex(Point(0, 0, 1.4) ),
#      LineVertex(Point(-1, -1, 0) ),
#      LineVertex(Point(-1,1, 0) ),
#     ],
#      line_type='LINE_LOOP'
# ).load_as('pyramid_curve')



