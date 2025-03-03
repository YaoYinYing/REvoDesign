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
from typing import Iterable, List, Literal, Optional, Tuple, Union

import numpy as np
import webcolors
from chempy import cpv
from immutabledict import immutabledict
from matplotlib import _color_data as _cdata
from pymol import cgo, cmd
from pymol.vfont import plain

DEBUG = True


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
    def array(self) -> np.ndarray:
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
        return point.array - self.array

    def center_xyz(self, point: 'Point') -> Tuple[float, float, float]:
        return (point.array - self.array) / 2

    def distance_to(self, point: 'Point') -> float:
        '''
        Euclidean distance from a point to this Point.

        Parameters:
        - point: Point, a target point object.

        Returns:
        - float: The Euclidean distance
        '''
        return np.linalg.norm(point.array - self.array).astype(float)


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
            if DEBUG:
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

    def load_as(self, name: str, *args, **kwargs):
        """
        Load the graphic object as a specified name. If the name is occupied, delete it to regenerate.

        Parameters:
        name (str): The name of the object, used for loading the object data into the software.

        If an object with the same name already exists, it is deleted before loading the new object.
        This prevents loading errors due to duplicate names.
        """
        if name in cmd.get_names():
            cmd.delete(name)

        if DEBUG:
            print(f'[DEBUG]: {self.__class__}: \n{self.data}')
        cmd.load_cgo(self.data, name, *args, **kwargs)


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
class PseudoBezier(GraphicObject):
    """
    A class representing a pseudo-Bezier curve, inheriting from GraphicObject.

    This class defines a Bezier curve with two control points and their respective handles,
    and provides functionality to rebuild the curve based on these points.

    Attributes:
        control_pt_A (Point): The coordinates of the starting control point.
        A_right_handle (Point): The coordinates of the handle on the right side of the starting control point.
        B_left_handle (Point): The coordinates of the handle on the left side of the ending control point.
        control_pt_B (Point): The coordinates of the ending control point.
        color (Optional[str]): The color of the curve, optional.
        steps (int): The number of segments the curve is divided into for drawing, default is 50.
    """
    control_pt_A: Point
    A_right_handle: Point
    B_left_handle: Point
    control_pt_B: Point
    color: Optional[str] = None
    steps: int = 50

    def rebuild(self) -> None:
        """
        Rebuilds the pseudo-Bezier curve.

        This method calculates all vertices of the Bezier curve using the Bezier curve formula,
        and updates the internal data representation of the curve for rendering.
        """
        # Load the coordinates of the control points and handles as arrays
        cpA = self.control_pt_A.array
        cpA_right = self.A_right_handle.array
        cpB_left = self.B_left_handle.array
        cpB = self.control_pt_B.array

        # Organize the control points and handles into a list
        control_points = [cpA, cpA_right, cpB_left, cpB]
        n = len(control_points) - 1

        # Initialize the list of vertices
        vertices_points = []
        # Calculate the vertices of the Bezier curve
        for i in range(self.steps + 1):
            t = i / self.steps
            x = y = z = 0.0
            # Calculate the coordinates of each point on the curve using the Bezier formula
            for j, cp in enumerate(control_points):
                bernstein = math.comb(n, j) * (t ** j) * ((1 - t) ** (n - j))
                x += cp[0] * bernstein
                y += cp[1] * bernstein
                z += cp[2] * bernstein
            vertices_points.append(Point(x, y, z))

        # Set the curve color if specified
        if self.color is not None:
            cgo_obj = [*Color(self.color).as_cgo]
        else:
            cgo_obj = []

        # Add the vertices data to the CGO object
        cgo_obj.extend(Point.as_vertexes(vertices_points))

        # Update the internal data representation of the curve
        self._data = cgo_obj


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
    point: Union[Point, PseudoBezier]
    width: Optional[float] = None
    color: Optional[str] = None

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
        elif isinstance(self.point, PseudoBezier):
            self._data.extend(self.point.data)
        else:
            # Currently, only Point type is supported. If another type is encountered, raise an exception
            raise NotImplementedError('Bezier is not currently supported')

    @classmethod
    def from_points(cls, points: Iterable[Union[Point, Iterable[float]]], width: Optional[float]
                    = None, color: Optional[str] = None) -> tuple['LineVertex', ...]:
        return tuple(cls(p if isinstance(p, Point) else Point(*p), width=width, color=color) for p in points)


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
    """
    Represents a cylindrical graphic object.

    Attributes:
    - point1 (Point): The first endpoint of the cylinder, defaulting to Point(0, 0, 0).
    - point2 (Point): The second endpoint of the cylinder, defaulting to Point(1, 1, 1).
    - radius (float): The radius of the cylinder, defaulting to 1.0.
    - color1 (str): The color of the first end of the cylinder, defaulting to 'violet'.
    - color2 (str): The color of the second end of the cylinder, defaulting to 'cyan'.
    """

    point1: Point = Point(0, 0, 0)
    point2: Point = Point(1, 1, 1)
    radius: float = 1.0
    color1: str = 'violet'
    color2: str = 'cyan'

    def rebuild(self):
        """
        Rebuilds the cylinder's data representation.

        This method constructs the data array for the cylinder using the specified attributes.
        """
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
    """
    Represents a sausage-shaped graphic object with two endpoints, a radius, and two colors.

    Attributes:
        p1 (Point): The starting point of the sausage.
        p2 (Point): The ending point of the sausage.
        radius (float): The radius of the sausage.
        color_1 (str): The color at the start of the sausage.
        color_2 (str): The color at the end of the sausage.
    """

    p1: Point
    p2: Point
    radius: float
    color_1: str
    color_2: str

    def rebuild(self):
        """
        Rebuilds the internal data representation of the sausage object.
        This method constructs a list that includes the sausage identifier and the coordinates,
        radius, and colors of the sausage.
        """
        self._data = [
            cgo.SAUSAGE,
            *self.p1.array,
            *self.p2.array,
            self.radius,
            *Color(self.color_1).array,
            *Color(self.color_2).array
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
    """
    Represents a cone graphic object.

    Attributes:
        tip: The position of the cone's tip.
        base_center: The position of the cone's base center.
        radius_tip: The radius of the cone at the tip.
        radius_base: The radius of the cone at the base.
        color_tip: The color of the cone's tip. Default is 'w' for white.
        color_base: The color of the cone's base. Default is 'g' for green.
        caps: A tuple indicating whether to add caps to the tip and/or base. 1 for True, 0 for False. Default is (1, 0), meaning the tip has a cap and the base does not.
    """
    tip: Point
    base_center: Point

    radius_tip: float
    radius_base: float

    color_tip: str = 'w'
    color_base: str = 'g'

    # whether to add caps to tip and/or base. 1 for True, 0 for False
    caps: tuple[float, float] = (1, 0)

    def rebuild(self) -> None:
        """
        Rebuilds cone

        This method rebuilds the cone based on its attributes, including position, size, color, and whether to add caps.
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
    """
    Represents a triangle in 3D space, inheriting from GraphicObject.
    It defines the vertices, normals, and colors of the triangle.

    Attributes:
        vertex_a (Point): The first vertex of the triangle, default is Point(1, 0, 0).
        vertex_b (Point): The second vertex of the triangle, default is Point(0, 1, 0).
        vertex_c (Point): The third vertex of the triangle, default is Point(0, 0, 1).
        normal_a (Point): The normal vector at the first vertex, default is Point(1, 0, 0).
        normal_b (Point): The normal vector at the second vertex, default is Point(0, 1, 0).
        normal_c (Point): The normal vector at the third vertex, default is Point(0, 0, 1).
        color_a (str): The color of the first vertex, default is 'r' (red).
        color_b (str): The color of the second vertex, default is 'g' (green).
        color_c (str): The color of the third vertex, default is 'b' (blue).
    """

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
        """
        Rebuilds the internal data representation of the triangle by combining
        the arrays of vertices, normals, and colors.
        """
        self._data = [
            *Point.as_arrays((self.vertex_a, self.vertex_b, self.vertex_c)),
            *Point.as_arrays((self.normal_a, self.normal_b, self.normal_c)),
            *Color.as_arrays((Color(self.color_a), Color(self.color_b), Color(self.color_c)))
        ]
@dataclass
class TriangleSimple(GraphicObject):
    """
    Represents a simple triangle graphic object with three vertices and corresponding colors.

    Attributes:
    - vertex_a (Point): The first vertex of the triangle, defaulting to Point(1, 0, 0).
    - vertex_b (Point): The second vertex of the triangle, defaulting to Point(0, 1, 0).
    - vertex_c (Point): The third vertex of the triangle, defaulting to Point(0, 0, 1).
    - color_a (str): The color of the first vertex, defaulting to 'r' (red).
    - color_b (str): The color of the second vertex, defaulting to 'g' (green).
    - color_c (str): The color of the third vertex, defaulting to 'b' (blue).
    """

    vertex_a: Point = Point(1, 0, 0)
    vertex_b: Point = Point(0, 1, 0)
    vertex_c: Point = Point(0, 0, 1)

    color_a: str = 'r'
    color_b: str = 'g'
    color_c: str = 'b'

    def rebuild(self):
        """
        Rebuilds the triangle's data representation using the specified vertices and colors.
        """
        self._data = [
            cgo.BEGIN, cgo.TRIANGLES,

            # Add the color and vertex data for the first point
            *Color(self.color_a).as_cgo,
            *self.vertex_a.as_vertex,

            # Add the color and vertex data for the second point
            *Color(self.color_b).as_cgo,
            *self.vertex_b.as_vertex,

            # Add the color and vertex data for the third point
            *Color(self.color_c).as_cgo,
            *self.vertex_c.as_vertex,

            cgo.END
        ]
@dataclass
class Line(GraphicObject):
    """
    Represents a line, inheriting from GraphicObject.
    
    Attributes:
        start: The starting point of the line, default is at the origin (0, 0, 0).
        end: The ending point of the line, default is at (0, 0, 1).
    """
    
    start: Point = Point(0, 0, 0)
    end: Point = Point(0, 0, 1)

    @property
    def points(self):
        """
        Returns the starting and ending points of the line.
        
        Returns:
            A tuple containing the starting and ending points.
        """
        return (self.start, self.end)

    def rebuild(self):
        """
        Rebuilds the line's vertex data.
        
        This method converts the starting and ending points into vertex data format and assigns it to self._data.
        """
        self._data = [
            *Point.as_vertexes((self.start, self.end))
        ]


@dataclass
class Lines(GraphicObject):
    """
    Represents a collection of lines, inheriting from GraphicObject.
    
    Attributes:
        color: The color of the lines, default is 'w' (white).
        lines: A tuple containing the Line objects, default is an empty tuple.
    """
    
    color: str = 'w'
    lines: tuple[Line] = field(default_factory=tuple)

    def rebuild(self):
        """
        Rebuilds the collection of lines' data.
        
        This method first sets self._data to the color data, then extends it with the data of each line.
        """
        self._data = [
            *Color(self.color).as_cgo,
        ]
        for line in self.lines:
            self._data.extend(line.data)

@dataclass
class Cube(GraphicObject):
    '''
    Cubic box with edges aligned with axes


    '''

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
    """
    Represents a square graphic object, inheriting from GraphicObject.
    
    Attributes:
        corner_a, corner_b, corner_c, corner_d: Define the four corners of the square using Point objects.
        color_a, color_b, color_c, color_d: Define the colors for each corner of the square.
    """

    corner_a: Point = Point(0, 0, 0)
    corner_b: Point = Point(1, 0, 0)
    corner_c: Point = Point(1, 1, 0)
    corner_d: Point = Point(0, 1, 0)

    color_a: str = 'r'
    color_b: str = 'g'
    color_c: str = 'b'
    color_d: str = 'y'

    def rebuild(self):
        """
        Rebuilds the square object's drawing data.
        
        This method initializes a graphic object drawing data (_data) by defining the vertices and colors of the triangles that make up the square.
        It uses the Color utility class to handle color conversion and the Point class for vertex coordinates.
        """
        # Start drawing, defining the drawing mode as triangles
        self._data = [
            cgo.BEGIN, cgo.TRIANGLES,

            # Define the first triangle, including the color and vertex of each corner
            *Color(self.color_a).as_cgo,
            *self.corner_a.as_vertex,
            *Color(self.color_b).as_cgo,
            *self.corner_b.as_vertex,
            *Color(self.color_c).as_cgo,
            *self.corner_c.as_vertex,

            # Define the second triangle, including the color and vertex of each corner
            *Color(self.color_a).as_cgo,
            *self.corner_a.as_vertex,
            *Color(self.color_c).as_cgo,
            *self.corner_c.as_vertex,
            *Color(self.color_d).as_cgo,
            *self.corner_d.as_vertex,

            # End drawing
            cgo.END
        ]
@dataclass
class PolyLines(GraphicObject):
    """
    Represents a collection of polylines, inheriting from GraphicObject.
    
    This class is used to define a series of lines connected in a specific way, with common attributes such as width and color.
    
    Attributes:
        width (float): The line width.
        color (str): The line color, represented as a string.
        points (Iterable[LineVertex]): A collection of line vertices.
        line_type (Literal['LINE_STRIP', 'LINE_LOOP', 'TRIANGLE_STRIP', 'TRIANGLE_FAN']): The drawing mode of the line, defaulting to 'LINE_STRIP'.
    """
    # global
    width: float
    color: str

    points: Iterable[LineVertex]
    line_type: Literal['LINE_STRIP', 'LINE_LOOP', 'TRIANGLE_STRIP', 'TRIANGLE_FAN'] = 'LINE_STRIP'

    def rebuild(self):
        """
        Rebuilds the line data.
        
        This method initializes the line drawing data, including setting the line width, color, and type, and updates the data for each vertex.
        """
        # Initialize the line drawing data, including line width and color
        self._data = [
            cgo.LINEWIDTH, self.width,
            *Color(self.color).as_cgo,
            cgo.BEGIN, getattr(cgo, self.line_type),
        ]
        # Update the data for each vertex
        for pv in self.points:
            self._data.extend([*pv.data])

        self._data.append(cgo.END)


@dataclass
class GraphicObjectCollection(GraphicObject):
    """
    A collection class for GraphicObject, which contains multiple graphic objects.
    
    Attributes:
        objects (List[GraphicObject]): A list of GraphicObject instances.
        force_to_rebuild (bool): A flag indicating whether to force rebuild the graphic objects in the collection.
    """
    objects: List[GraphicObject]
    force_to_rebuild: bool = False

    def rebuild(self):
        """
        Rebuilds the data for all graphic objects in the collection.
        
        This method empties the existing graphic object data, then iterates through each graphic object in the collection.
        If the force_to_rebuild flag is set to True, it calls the rebuild method on each graphic object.
        Finally, it adds the data of each graphic object to the collection's _data list.
        """
        # Reset the collection's data
        self._data = []
        # Iterate through each graphic object in the collection
        for go_idx, go in enumerate(self.objects):
            # If forced to rebuild, call the rebuild method on the graphic object
            if self.force_to_rebuild:
                go.rebuild()
            # Add the graphic object's data to the collection's data list
            self._data.extend(go.data)
            # Print the addition information of the graphic object
            print(f"Added: #{go_idx} ({go.__class__.__name__})")


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


# Cube(wire_frame=True).load_as('a_colorful_cube')
# Cube(wire_frame=False).load_as('a_colorful_solid_cube')
# Cube(
#     wire_frame=True,
#     color_w='yellow',
#     color_x='yellow',
#     color_y='yellow',
#     color_z='yellow'
# ).load_as('a_yellow_box')

# Cube(wire_frame=True,
#     color_w='white',
#     color_x='white',
#     color_y='white',
#     color_z='white'
# ).load_as('solid_box')

# Cube(
#     wire_frame=True,
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
#     LineVertex.from_points(
#         (
#             Point(0, 1, 0),
#             Point(1, 2, 0),
#             Point(2, 3, 0),
#             Point(0, 0.5, 0),
#             Point(-0.3, 0.5, 0),
#             Point(0, 0, 0)

#         )

#     ),
#     line_type='TRIANGLE_FAN'
# ).load_as('white_square_fan')


# Sausage(
#     p1=Point(0, 0, 1),
#     p2=Point(0, 0, 2),
#     radius=0.5,
#     color_1='red',
#     color_2='white'
# ).load_as('tasty_sausage')


# PolyLines(
#     2.0, 'white',
#     LineVertex.from_points(
#         (
#             Point(0, 1, 0),
#             Point(1, 1, 0),
#             Point(1, 0, 0),
#             Point(0, 0, 0)
#         )

#     ),
#     line_type='LINE_LOOP'
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


def __east_egg():
    '''
    There is only one truth!

    真しん実じつはいつもひとつ!
    '''
    global DEBUG
    _DEBUG = DEBUG

    DEBUG = False
    aptx_4869 = GraphicObjectCollection([
        Sphere(
            center=Point(-2, 0, 0),
            radius=1,
            color='white'
        ),
        Cylinder(
            Point(-2, 0, 0),
            Point(0, 0, 0),
            radius=1,
            color1='white',
            color2='white'
        ),
        Cylinder(
            Point(0, 0, 0),
            Point(2, 0, 0),
            radius=1,
            color1='red',
            color2='red'
        ),
        Sphere(
            center=Point(2, 0, 0),
            radius=1,
            color='red'
        ),
        PolyLines(
            5, 'black',
            [
                LineVertex(Point(-1.6, 0.5, 0.9)),
                LineVertex(Point(1.6, 0.5, 0.9)),
                LineVertex(PseudoBezier(
                    Point(1.6, 0.5, 0.9),
                    Point(2.2, 0.5, 1.05),
                    Point(2.2, -0.5, 1.05),
                    Point(1.6, -0.5, 0.9)
                )),
                LineVertex(Point(1.6, -0.5, 0.9)),
                LineVertex(Point(-1.6, -0.5, 0.9)),
                LineVertex(PseudoBezier(
                    Point(-1.6, -0.5, 0.9),
                    Point(-2.2, -0.5, 1.05),
                    Point(-2.2, 0.5, 1.05),
                    Point(-1.6, 0.5, 0.9)
                )),
            ], line_type='LINE_LOOP'
        )
    ]
    )

    cgo.cyl_text(
        aptx_4869.data,
        plain,
        Point(-1.5, -0.3, 1.01).array,
        'APTX-4869',
        0.03,
        axes=[Point(0.5, 0, 0).array, Point(0, 0.5, 0).array, Point(0, 0, 0.5).array],
        color=Color('black').array)

    from ..shortcuts.tools.vina_tools import showaxes

    showaxes()
    aptx_4869.load_as('APTX-4869')

    cmd.zoom()
    cmd.turn('z', 16)
    cmd.movie.add_roll(4.0, axis='y', start=1)

    DEBUG = _DEBUG
    cmd.mplay()


cmd.extend('hello_revodesign', __east_egg)
