"""
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



"""

# TODO: move as a standalone package, maybe `pymol-cgo-utils`?
# i dont want to maintain such code w/i this package
import datetime
import itertools
import math
import string
from abc import abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import cached_property
from typing import Literal

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


# name: hsv imutable dicts
BASE_COLORS: immutabledict[str, str] = immutabledict(
    {
        name: webcolors.rgb_to_hex(tuple(map(lambda x: int(255 * x), value)))
        for name, value in _cdata.BASE_COLORS.items()
    }
)  # type: ignore
TABLEAU_COLORS: immutabledict[str, str] = immutabledict(
    {name.lstrip("tab:"): value for name, value in _cdata.TABLEAU_COLORS.items()}
)
CSS4_COLORS: immutabledict[str, str] = immutabledict(_cdata.CSS4_COLORS)
XKCD_COLORS: immutabledict[str, str] = immutabledict(
    {name.lstrip("xkcd:").replace(" ", "_"): value for name, value in _cdata.XKCD_COLORS.items()}
)

# color tables
COLOR_TABLES = (
    BASE_COLORS,
    TABLEAU_COLORS,
    CSS4_COLORS,
    XKCD_COLORS,
)


def not_none_float(*args: float | None):
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
            print(f"Skip {idx} ({float_in}): {e}")
    # Return the default value 0.0 if no valid float can be found
    return 0.0


@dataclass(frozen=True)
class Point:
    """
    A Point vector object in PyMOL's coordinate system
    This class represents a point in 3D space with coordinates (x, y, z).
    It provides methods to convert the point to a numpy array, and to generate CGO commands for vertices and normals.
    """

    x: float
    y: float
    z: float

    def __add__(self, other: "Point") -> "Point":
        """
        Add two points together.
        """
        return Point.from_array(self.array + other.array)

    def __sub__(self, other: "Point"):
        return Point.from_array(self.array - other.array)

    def __truediv__(self, other: float) -> "Point":
        """
        Divide a point by a scalar.
        """
        return Point.from_array(self.array / other)

    def __mul__(self, other: float) -> "Point":
        """
        Multiply a point by a scalar.
        """
        return Point.from_array(self.array * other)

    @property
    def copy(self):
        """
        Return a copy of the point.
        """
        return Point.from_array(self.array)

    @classmethod
    def dot(cls, point1: "Point", point2: "Point") -> float:
        return np.dot(point1.array, point2.array)

    @classmethod
    def cross(cls, point1: "Point", point2: "Point"):
        return cls.from_array(np.cross(point1.array, point2.array))

    @cached_property
    def array(self) -> np.ndarray:
        """
        Convert the point to a numpy array
        This method converts the point's coordinates into a numpy array, facilitating subsequent vector operations.
        """
        return np.array([self.x, self.y, self.z])

    @cached_property
    def as_vertex(self):
        """
        Generate a CGO vertex command for the point
        This method inserts the point's coordinates into a CGO vertex command, used for rendering in PyMOL.
        """
        return np.insert(cgo.VERTEX, 1, self.array)

    @cached_property
    def as_normal(self):
        """
        Generate a CGO normal command for the point
        This method inserts the point's coordinates into a CGO normal command, used for specifying normals in PyMOL.
        """
        return np.insert(cgo.NORMAL, 1, self.array)

    def move(self, x: float | None = None, y: float | None = None, z: float | None = None) -> "Point":
        """
        Move the point
        This method allows the point to be moved along the x, y, and z axes. If a coordinate is not provided, the original value is used.

        Parameters:
        - x: Optional[float] = None, the new x-coordinate, if not provided, the original x-coordinate is used
        - y: Optional[float] = None, the new y-coordinate, if not provided, the original y-coordinate is used
        - z: Optional[float] = None, the new z-coordinate, if not provided, the original z-coordinate is used

        Returns:
        - Point: The new point after moving
        """
        return Point(not_none_float(x, self.x), not_none_float(y, self.y), not_none_float(z, self.z))

    @staticmethod
    def as_arrays(points: Iterable["Point"]):
        """
        Convert a collection of points to a numpy array
        This static method converts a collection of Point objects into a single numpy array, facilitating batch processing.

        Parameters:
        - points: Iterable['Point'], a collection of Point objects

        Returns:
        - np.ndarray: A numpy array containing the coordinates of all points
        """
        return np.concatenate(tuple(point.array for point in points))

    @staticmethod
    def as_vertexes(points: Iterable["Point"]):
        """
        Convert a collection of points to CGO vertex commands
        This static method converts a collection of Point objects into CGO vertex commands, used for batch rendering in PyMOL.

        Parameters:
        - points: Iterable['Point'], a collection of Point objects

        Returns:
        - np.ndarray: A numpy array containing the CGO vertex commands for all points
        """
        return np.concatenate(tuple(point.as_vertex for point in points))

    def delta_xyz(self, point: "Point") -> np.ndarray:
        return point.array - self.array

    def center_xyz(self, point: "Point") -> np.ndarray:
        return (point.array - self.array) / 2

    def distance_to(self, point: "Point") -> float:
        """
        Euclidean distance from a point to this Point.

        Parameters:
        - point: Point, a target point object.

        Returns:
        - float: The Euclidean distance
        """
        return np.linalg.norm(point.array - self.array).astype(float)

    @classmethod
    def from_array(cls, array: np.ndarray) -> "Point":
        """
        Create a Point object from a NumPy array.
        """
        return cls(*array)

    @classmethod
    def from_atom(cls, atom: str) -> "Point":
        """
        Create a Point object from a PyMOL atom.
        """
        return cls(*cmd.get_coords(atom)[0])

    @classmethod
    def from_com(cls, selection: str = "(all)") -> "Point":
        """
        Calculate the center of mass of a selection.

        Parameters:
        - selection: str, a PyMOL selection string.

        Returns:
        - Point: The center of mass as a Point object.
        """
        return cls(*cmd.centerofmass(selection))


@dataclass(frozen=True)
class Color:
    """
    Represents a color, including its name and alpha value.

    Attributes:
        name (str): The name of the color.
        alpha (float): The alpha value of the color, default is 1.0 for full opacity.
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

        # Check if the color name starts with '#', indicating a hexadecimal color
        if name.startswith("#"):
            if DEBUG:
                print(f"[DEBUG] {name} has a hexadecimal format")
            return np.array(webcolors.hex_to_rgb(name), dtype=float) / 255

        # Check if the color name contains a comma, indicating a RGB color in `255,255,255` format
        if "," in name:
            try:
                assumed_rgb = [int(x) for x in name.split(",")[:3]]
                if DEBUG:
                    print(f"[DEBUG] {name} is assumed to be RGB: {assumed_rgb=}")
                return np.array(assumed_rgb, dtype=float) / 255
            except Exception as e:
                raise ValueError(f"{name} is not a valid RGB color") from e

        # Iterate through the color tables to find a match
        for cdict in COLOR_TABLES:
            if name not in cdict:
                continue
            if DEBUG:
                print(f"[DEBUG] {name}: {cdict[name]}")
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
    def as_arrays(colors: Iterable["Color"]):
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
    def as_cgos(colors: Iterable["Color"]):
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
        return np.concatenate((np.array([cgo.ALPHA, self.alpha, cgo.COLOR]), self.array))


@dataclass
class GraphicObject:
    """
    A base class representing a graphic object, providing methods to rebuild and load graphic data.
    """

    def rebuild(self):
        """
        Rebuild the CGO data.
        """
        self._data: list[float] = []

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
            print(f"[DEBUG]: {self.__class__.__name__}: \n{self.data}")
        cmd.load_cgo(self.data, name, *args, **kwargs)


# ------------------------------------------------------------------
# Pseudocurve Base Class
# ------------------------------------------------------------------


@dataclass
class PseudoCurve(GraphicObject):
    """
    Pseudocurve base class, from which all pseudocurves (Bezier, Catmull-Rom,
    B-Spline, Hermite, Arc, NURBS) inherit. Implements the sample method to
    calculate discrete sampling points of the curve.

    Attributes:
        control_points (List[Point]): A list of control points used to define the curve.
        color (Optional[str]): The color of the curve (optional).
        steps (int): The number of segments the curve is divided into for drawing (default is 50).
    """

    control_points: list[Point]
    color: str | None = None
    steps: int = 50

    def check_control_points(
        self, num_min: int | None = None, num_max: int | None = None, attr_name: str = "control_points"
    ):
        """
        Check if the number of control points meets the minimum and maximum requirements.

        Arguments:
            num_min (int): The minimum number of control points required.
            num_max (int): The maximum number of control points allowed.
            attr_name (str): The name of the attribute containing the control points.
        """
        len_cp = len(getattr(self, attr_name))
        if num_min and len_cp < num_min:
            raise ValueError(f"Number of Control Points mismatch. Required {num_min} as minimum but got {len_cp}")
        if num_max and len_cp > num_max:
            raise ValueError(f"Number of Control Points mismatch. Required {num_max} as maximum but got {len_cp}")

    @abstractmethod
    def sample(self) -> list["Point"]:
        """
        Abstract method sample, used to calculate the discrete sampling points of the curve.

        Returns:
            List["Point"]: A list of sampling points, containing a series of points that make up the curve.
        """

    def rebuild(self) -> None:
        """
        Rebuild method, used to rebuild the curve object based on sampling points.

        This method first calls the sample method to get a list of sampling points, then builds
        a CGO (Crystallographic Object) list based on these points.
        If the color attribute exists, the color information is added to the CGO object.
        Finally, the CGO object is assigned to the _data attribute of the instance, for subsequent
        processing or rendering.
        """
        vertices_points = self.sample()  # Call the sample method to get a list of sampling points
        cgo_obj = []
        if self.color is not None:
            cgo_obj.extend(Color(self.color).as_cgo)  # Add color information if available
        cgo_obj.extend(Point.as_vertexes(vertices_points))  # Convert sampling points to CGO vertex format
        self._data = cgo_obj


# ------------------------------------------------------------------
# PseudoBezier Implementation
# ------------------------------------------------------------------


@dataclass
class PseudoBezier(PseudoCurve):
    """
    PseudoBezier pseudocurve implementation using the Bezier curve formula with four control points.
    """

    def sample(self) -> list[Point]:
        self.check_control_points(4, 4)
        control_points = self.control_points
        n = len(control_points) - 1
        points = []
        # Use numpy linspace for t values in [0, 1]
        t_values = np.linspace(0, 1, self.steps + 1)
        for t in t_values:
            x = y = z = 0.0
            for j, cp in enumerate(control_points):
                bernstein = math.comb(n, j) * (t**j) * ((1 - t) ** (n - j))
                x += cp.x * bernstein
                y += cp.y * bernstein
                z += cp.z * bernstein
            points.append(Point(x, y, z))
        return points


# ------------------------------------------------------------------
# PseudoCatmullRom Implementation
# ------------------------------------------------------------------


@dataclass
class PseudoCatmullRom(PseudoCurve):
    """
    PseudoCatmullRom pseudocurve implementation using the Catmull-Rom spline formula.
    This curve passes through all the control points and requires at least 4 control points.
    """

    def sample(self) -> list[Point]:
        self.check_control_points(num_min=4)
        points = []
        # Iterate through segments defined by 4 consecutive control points
        for i in range(1, len(self.control_points) - 2):
            P0 = self.control_points[i - 1]
            P1 = self.control_points[i]
            P2 = self.control_points[i + 1]
            P3 = self.control_points[i + 2]
            t_values = np.linspace(0, 1, self.steps)
            for t in t_values:
                t2 = t * t
                t3 = t2 * t
                x = 0.5 * (
                    (2 * P1.x)
                    + (-P0.x + P2.x) * t
                    + (2 * P0.x - 5 * P1.x + 4 * P2.x - P3.x) * t2
                    + (-P0.x + 3 * P1.x - 3 * P2.x + P3.x) * t3
                )
                y = 0.5 * (
                    (2 * P1.y)
                    + (-P0.y + P2.y) * t
                    + (2 * P0.y - 5 * P1.y + 4 * P2.y - P3.y) * t2
                    + (-P0.y + 3 * P1.y - 3 * P2.y + P3.y) * t3
                )
                z = 0.5 * (
                    (2 * P1.z)
                    + (-P0.z + P2.z) * t
                    + (2 * P0.z - 5 * P1.z + 4 * P2.z - P3.z) * t2
                    + (-P0.z + 3 * P1.z - 3 * P2.z + P3.z) * t3
                )
                points.append(Point(x, y, z))
        # Append the second-to-last control point to ensure correct termination.
        points.append(self.control_points[-2])
        return points


# ------------------------------------------------------------------
# PseudoBSpline Implementation
# ------------------------------------------------------------------


@dataclass
class PseudoBSpline(PseudoCurve):
    """
    PseudoBSpline pseudocurve implementation using a B-Spline algorithm.

    Attributes:
        degree (int): Degree of the B-Spline curve (default is 3).
        knots (Optional[List[float]]): Knot vector. If not provided, a uniform clamped knot vector is generated.
    """

    degree: int = 3
    knots: list[float] | None = None

    def sample(self) -> list[Point]:
        from scipy.interpolate import BSpline

        n = len(self.control_points) - 1
        p = self.degree
        # Generate a uniform clamped knot vector if not provided.
        if self.knots is None:
            self.knots = [0.0] * (p + 1) + list(range(1, n - p + 1)) + [n - p + 1] * (p + 1)
        # Convert control points to a NumPy array of shape (n+1, 3)
        ctrl_pts = np.array([[pt.x, pt.y, pt.z] for pt in self.control_points])
        u_start = self.knots[p]
        u_end = self.knots[n + 1]
        u_vals = np.linspace(u_start, u_end, self.steps + 1)
        bspline = BSpline(self.knots, ctrl_pts, p)
        spline_pts = bspline(u_vals)
        return [Point(x, y, z) for x, y, z in spline_pts]


# ------------------------------------------------------------------
# PseudoHermite Implementation
# ------------------------------------------------------------------


@dataclass
class PseudoHermite(PseudoCurve):
    """
    PseudoHermite pseudocurve implementation using Hermite interpolation.

    Attributes:
        control_points (List[Point]): Exactly 2 control points (start and end).
        tangents (List[Point]): Two tangent vectors corresponding to the control points.
    """

    tangents: list[Point] = field(default_factory=list)

    def sample(self) -> list[Point]:
        self.check_control_points(2, 2)
        self.check_control_points(2, 2, "tangents")
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


# ------------------------------------------------------------------
# PseudoArc Implementation
# ------------------------------------------------------------------


@dataclass
class PseudoArc(PseudoCurve):
    """
    PseudoArc pseudocurve implementation for drawing an arc.

    Attributes:
        control_points (List[Point]): Expects a single control point representing the center.
        radius (float): The radius of the arc.
        angles (List[float]): A list with two elements [start_angle, end_angle] in radians.
    """

    radius: float = 0.0
    angles: list[float] = field(default_factory=lambda: [0.0, 0.0])

    def sample(self) -> list[Point]:
        self.check_control_points(1, 1)
        self.check_control_points(2, 2, "angles")
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


# ------------------------------------------------------------------
# PseudoNURBS Implementation
# ------------------------------------------------------------------


@dataclass
class PseudoNURBS(PseudoCurve):
    """
    PseudoNURBS pseudocurve implementation using Non-Uniform Rational B-Splines.

    Attributes:
        weights (List[float]): Weights corresponding to each control point.
        degree (int): Degree of the NURBS curve (default is 3).
        knots (Optional[List[float]]): Knot vector. If not provided, a uniform clamped knot vector is generated.
    """

    weights: list[float] = field(default_factory=list)
    degree: int = 3
    knots: list[float] | None = None

    def sample(self) -> list[Point]:
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

    def basis(self, i: int, p: int, u: float, knots: list[float]) -> float:
        """
        Recursive Cox-de Boor basis function.
        """
        if p == 0:
            if knots[i] <= u < knots[i + 1]:
                return 1.0
            # Handle special case when u equals the last knot
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
    """
    Represents a line vertex, inheriting from GraphicObject.

    This class is used to define a line drawing element, which can be a point or a Bezier curve, and can include line width and color attributes.

    Attributes:
    - point: A Point or Bezier instance, representing the starting point or control point of the line.
    - width: An optional float, representing the line width. If not provided, the default is None.
    - color: An optional string, representing the line color. If not provided, the default is None.
    """

    point: Point | PseudoCurve
    width: float | None = None
    color: str | None = None

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
        elif isinstance(self.point, PseudoCurve):
            self._data.extend(self.point.data)
        else:
            # Currently, only Point type is supported. If another type is encountered, raise an exception
            raise NotImplementedError("this curve is not currently supported")

    @classmethod
    def from_points(
        cls, points: Iterable[Point | Iterable[float]], width: float | None = None, color: str | None = None
    ) -> tuple["LineVertex", ...]:
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
    color: str = "w"

    def rebuild(self):
        """
        Rebuilds the sphere's data representation using CGO (Chimera Graphics Object) format.

        This method constructs the sphere's data by combining the color information and the sphere's geometric properties.
        """
        self._data = [
            *Color(self.color).as_cgo,  # Convert color to CGO format and unpack it into the data list
            cgo.SPHERE,  # Specify the CGO object type as SPHERE
            *self.center.array,  # Unpack the center coordinates into the data list
            self.radius,  # Add the radius to the data list
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
    color1: str = "violet"
    color2: str = "cyan"

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
            *Color(self.color_2).array,
        ]


@dataclass
class Doughnut(GraphicObject):  # Torus
    center: Point = Point(0.0, 0.0, 0.0)
    normal: Point = Point(0.0, 0.0, 1.0)
    radius: float = 1.0
    color: str = "w"
    cradius: float = 0.25
    samples: int = 20
    csamples: int = 20

    # from pymol.cgobuilder.Torus
    def rebuild(self) -> None:
        """
        Rebuilds torus
        """
        obj = []

        axis = cpv.cross_product(self.normal.array, (0.0, 0.0, 1.0))
        angle = -cpv.get_angle(self.normal.array, (0.0, 0.0, 1.0))
        matrix = cpv.rotation_matrix(angle, cpv.normalize(axis))

        def obj_vertex(x, y, z):
            return [cgo.VERTEX] + cpv.add(self.center.array, cpv.transform(matrix, [x, y, z]))

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
                    obj_normal(
                        (r + rr * c_v) * c_w - (r + cr * c_v) * c_w,
                        (r + rr * c_v) * s_w - (r + cr * c_v) * s_w,
                        (rr * s_v - cr * s_v),
                    )
                )
                obj.extend(obj_vertex((r + cr * c_v) * c_w, (r + cr * c_v) * s_w, cr * s_v))
                obj.extend(
                    obj_normal(
                        (r + rr * c_vdv) * c_wdw - (r + cr * c_vdv) * c_wdw,
                        (r + rr * c_vdv) * s_wdw - (r + cr * c_vdv) * s_wdw,
                        rr * s_vdv - cr * s_vdv,
                    )
                )
                obj.extend(obj_vertex((r + cr * c_vdv) * c_wdw, (r + cr * c_vdv) * s_wdw, cr * s_vdv))
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

    color_tip: str = "w"
    color_base: str = "g"

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
            self.radius_tip,
            self.radius_base,
            *Color(self.color_tip).array,
            *Color(self.color_base).array,
            *self.caps,
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

    color_a: str = "r"
    color_b: str = "g"
    color_c: str = "b"

    def rebuild(self):
        """
        Rebuilds the internal data representation of the triangle by combining
        the arrays of vertices, normals, and colors.
        """
        self._data = [
            *Point.as_arrays((self.vertex_a, self.vertex_b, self.vertex_c)),
            *Point.as_arrays((self.normal_a, self.normal_b, self.normal_c)),
            *Color.as_arrays((Color(self.color_a), Color(self.color_b), Color(self.color_c))),
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

    color_a: str = "r"
    color_b: str = "g"
    color_c: str = "b"

    def rebuild(self):
        """
        Rebuilds the triangle's data representation using the specified vertices and colors.
        """
        self._data = [
            cgo.BEGIN,
            cgo.TRIANGLES,
            # Add the color and vertex data for the first point
            *Color(self.color_a).as_cgo,
            *self.vertex_a.as_vertex,
            # Add the color and vertex data for the second point
            *Color(self.color_b).as_cgo,
            *self.vertex_b.as_vertex,
            # Add the color and vertex data for the third point
            *Color(self.color_c).as_cgo,
            *self.vertex_c.as_vertex,
            cgo.END,
        ]


@dataclass
class Cube(GraphicObject):
    """
    Cubic box with edges aligned with axes


    """

    p1: Point = Point(0, 0, 0)
    p2: Point = Point(1, 1, 1)

    color_w: str = "yellow"

    color_x: str = "red"
    color_y: str = "green"
    color_z: str = "blue"

    wire_frame: bool = True
    linewidth: float = 2

    def _rebuild_wireframe(self):

        self._data = [
            cgo.LINEWIDTH,
            float(self.linewidth),
            cgo.BEGIN,
            cgo.LINES,
        ]

        for i, j in itertools.combinations("xyz", r=2):
            for _i, _j in itertools.product(
                (getattr(self.p1, i), getattr(self.p2, i)), (getattr(self.p1, j), getattr(self.p2, j))
            ):
                move_dict = {i: _i, j: _j}
                self._data.extend(
                    [
                        *Color(getattr(self, f'color_{"xyz".replace(i, "").replace(j, "")}')).as_cgo,
                        *self.p1.move(**move_dict).as_vertex,
                        *self.p2.move(**move_dict).as_vertex,
                    ]
                )

        self._data.append(cgo.END)

    def _rebuild_solid(self):
        """
        用 6 个 Square，合并出一个立方体(或长方体)外表。
        """

        # 简易函数：构造一个纯色的 Square（四个角都用 self.color）
        def make_face(a: Point, b: Point, c: Point, d: Point) -> list[float]:
            face = Square(
                corner_a=a,
                corner_b=b,
                corner_c=c,
                corner_d=d,
                # 给四个角都指定同一个颜色 => 整个面都是 uniform color
                color_a=self.color_w,
                color_b=self.color_x,
                color_c=self.color_y,
                color_d=self.color_z,
            )
            face.rebuild()
            return face.data

        # 获取 8 个顶点的 (x,y,z) 各种组合
        x1, y1, z1 = self.p1.x, self.p1.y, self.p1.z
        x2, y2, z2 = self.p2.x, self.p2.y, self.p2.z

        # 面 1: x = x1
        #   A=(x1,y1,z1), B=(x1,y1,z2), C=(x1,y2,z2), D=(x1,y2,z1)
        face1_data = make_face(Point(x1, y1, z1), Point(x1, y1, z2), Point(x1, y2, z2), Point(x1, y2, z1))
        # 面 2: x = x2
        #   A=(x2,y1,z1), B=(x2,y2,z1), C=(x2,y2,z2), D=(x2,y1,z2)
        face2_data = make_face(Point(x2, y1, z1), Point(x2, y2, z1), Point(x2, y2, z2), Point(x2, y1, z2))
        # 面 3: y = y1
        #   A=(x1,y1,z1), B=(x2,y1,z1), C=(x2,y1,z2), D=(x1,y1,z2)
        face3_data = make_face(Point(x1, y1, z1), Point(x2, y1, z1), Point(x2, y1, z2), Point(x1, y1, z2))
        # 面 4: y = y2
        #   A=(x1,y2,z1), B=(x1,y2,z2), C=(x2,y2,z2), D=(x2,y2,z1)
        face4_data = make_face(Point(x1, y2, z1), Point(x1, y2, z2), Point(x2, y2, z2), Point(x2, y2, z1))
        # 面 5: z = z1
        #   A=(x1,y1,z1), B=(x1,y2,z1), C=(x2,y2,z1), D=(x2,y1,z1)
        face5_data = make_face(Point(x1, y1, z1), Point(x1, y2, z1), Point(x2, y2, z1), Point(x2, y1, z1))
        # 面 6: z = z2
        #   A=(x1,y1,z2), B=(x2,y1,z2), C=(x2,y2,z2), D=(x1,y2,z2)
        face6_data = make_face(Point(x1, y1, z2), Point(x2, y1, z2), Point(x2, y2, z2), Point(x1, y2, z2))

        # 将 6 个面的 CGO 数据合并
        self._data = face1_data + face2_data + face3_data + face4_data + face5_data + face6_data

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

    color_a: str = "r"
    color_b: str = "g"
    color_c: str = "b"
    color_d: str = "y"

    def rebuild(self):
        """
        Rebuilds the square object's drawing data.

        This method initializes a graphic object drawing data (_data) by defining the vertices and colors of the triangles that make up the square.
        It uses the Color utility class to handle color conversion and the Point class for vertex coordinates.
        """
        # Start drawing, defining the drawing mode as triangles
        self._data = [
            cgo.BEGIN,
            cgo.TRIANGLES,
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
            cgo.END,
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
    line_type: Literal["LINE_STRIP", "LINE_LOOP", "TRIANGLE_STRIP", "TRIANGLE_FAN"] = "LINE_STRIP"

    def rebuild(self):
        """
        Rebuilds the line data.

        This method initializes the line drawing data, including setting the line width, color, and type, and updates the data for each vertex.
        """
        # Initialize the line drawing data, including line width and color
        self._data = [
            cgo.LINEWIDTH,
            self.width,
            *Color(self.color).as_cgo,
            cgo.BEGIN,
            getattr(cgo, self.line_type),
        ]
        # Update the data for each vertex
        for pv in self.points:
            self._data.extend([*pv.data])

        self._data.append(cgo.END)


@dataclass
class Arrow(GraphicObject):
    """
    Represents an arrow object for visualization in PyMOL, with properties for start and end points, line width, and color.
    """

    start: Point  # the start point of the arrow
    point_to: Point  # the tip of the arrow
    radius: float = 0.1  # cylinder width
    header_height: float = 0.25
    header_ratio: float = 1.618

    # colors
    color_header: str = "red"
    color_tail: str = "white"

    @property
    def cone_base_r(self):
        """
        Calculates and returns the diameter of the cone base.

        Returns:
            float: The diameter of the cone base.
        """
        return self.radius * self.header_ratio  # cone base diameter

    @property
    def cyl_length(self) -> float:
        """
        Calculates the length of the arrow's cylinder.
        """
        return max(self.point_to.distance_to(self.start) - self.header_height, 0)

    @cached_property
    def joint(self):
        return self.start + (self.point_to - self.start) * self.cyl_length / self.point_to.distance_to(self.start)

    def rebuild(self):
        go = GraphicObjectCollection(
            [
                Cylinder(self.start, self.joint, self.radius, self.color_tail, self.color_tail),
                Cone(self.point_to, self.joint, 0.0, self.cone_base_r, self.color_header, self.color_header, (1, 1)),
            ]
        )
        go.rebuild()
        self._data = go.data


# --- RoundedRectangle3D Implementation ---
@dataclass
class RoundedRectangle(GraphicObject):
    """
    Represents a rounded rectangle in 3D space using a combination of straight edges
    and cubic Bezier curves for the rounded corners.

    The rectangle is defined in a plane specified by a center point and two orthonormal axes.

    Attributes:
        center (Point): The center of the rectangle.
        axis1 (Point): A unit vector representing the rectangle's local X-axis.
        axis2 (Point): A unit vector representing the rectangle's local Y-axis.
        width (float): The full width of the rectangle.
        height (float): The full height of the rectangle.
        radius (float): The radius of the rounded corners.
        color (str): The outline color.
        line_width (float): The width of the outline.
        steps (int): Number of segments used to approximate each corner.
    """

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
        """
        Convert local (u, v) coordinates to global 3D coordinates.
        """
        global_coord = self.center.array + u * self.axis1.array + v * self.axis2.array
        return Point(global_coord[0], global_coord[1], global_coord[2])

    def rebuild(self) -> None:
        self.radius = min(self.width / 2, self.radius)
        # Half dimensions
        half_w = self.width / 2
        half_h = self.height / 2
        r = self.radius
        k = 0.5522847498  # constant for approximating a quarter circle with a cubic Bezier

        # Define local 2D coordinates (in the rectangle's plane) for the four edges (after corner inset)
        edge_bottom_start = (-half_w + r, -half_h)
        edge_bottom_end = (half_w - r, -half_h)
        edge_right_start = (half_w, -half_h + r)
        edge_right_end = (half_w, half_h - r)
        edge_top_start = (half_w - r, half_h)
        edge_top_end = (-half_w + r, half_h)
        edge_left_start = (-half_w, half_h - r)
        edge_left_end = (-half_w, -half_h + r)

        # Define control points for rounded corners (using cubic Bezier approximation)
        # Bottom-right corner (from edge_bottom_end to edge_right_start)
        cp1_br = (edge_bottom_end[0] + k * r, edge_bottom_end[1])
        cp2_br = (edge_right_start[0], edge_right_start[1] - k * r)
        # Top-right corner (from edge_right_end to edge_top_start)
        cp1_tr = (edge_right_end[0], edge_right_end[1] + k * r)
        cp2_tr = (edge_top_start[0] + k * r, edge_top_start[1])
        # Top-left corner (from edge_top_end to edge_left_start)
        cp1_tl = (edge_top_end[0] - k * r, edge_top_end[1])
        cp2_tl = (edge_left_start[0], edge_left_start[1] + k * r)
        # Bottom-left corner (from edge_left_end to edge_bottom_start)
        cp1_bl = (edge_left_end[0], edge_left_end[1] - k * r)
        cp2_bl = (edge_bottom_start[0] - k * r, edge_bottom_start[1])

        # Create PseudoBezier objects for each corner (convert local coords to global)
        bottom_right_corner = PseudoBezier(
            control_points=[
                self.local_to_global(*edge_bottom_end),
                self.local_to_global(*cp1_br),
                self.local_to_global(*cp2_br),
                self.local_to_global(*edge_right_start),
            ],
            color=self.color,
            steps=self.steps,
        )
        top_right_corner = PseudoBezier(
            control_points=[
                self.local_to_global(*edge_right_end),
                self.local_to_global(*cp1_tr),
                self.local_to_global(*cp2_tr),
                self.local_to_global(*edge_top_start),
            ],
            color=self.color,
            steps=self.steps,
        )
        top_left_corner = PseudoBezier(
            control_points=[
                self.local_to_global(*edge_top_end),
                self.local_to_global(*cp1_tl),
                self.local_to_global(*cp2_tl),
                self.local_to_global(*edge_left_start),
            ],
            color=self.color,
            steps=self.steps,
        )
        bottom_left_corner = PseudoBezier(
            control_points=[
                self.local_to_global(*edge_left_end),
                self.local_to_global(*cp1_bl),
                self.local_to_global(*cp2_bl),
                self.local_to_global(*edge_bottom_start),
            ],
            color=self.color,
            steps=self.steps,
        )

        # Assemble the vertices in order (using LineVertex to wrap both Points and PseudoBezier objects)
        vertices = [
            LineVertex(self.local_to_global(*edge_bottom_start)),  # start of bottom edge
            LineVertex(self.local_to_global(*edge_bottom_end)),  # end of bottom edge
            LineVertex(bottom_right_corner),  # bottom-right corner arc
            LineVertex(self.local_to_global(*edge_right_end)),  # end of right edge
            LineVertex(top_right_corner),  # top-right corner arc
            LineVertex(self.local_to_global(*edge_top_end)),  # end of top edge
            LineVertex(top_left_corner),  # top-left corner arc
            LineVertex(self.local_to_global(*edge_left_end)),  # end of left edge
            LineVertex(bottom_left_corner),  # bottom-left corner arc
        ]

        # Build a closed polyline (LINE_LOOP) from these vertices.
        poly = PolyLines(width=self.line_width, color=self.color, points=vertices, line_type="LINE_LOOP")
        poly.rebuild()
        self._data = poly._data


@dataclass
class Ellipse(GraphicObject):
    """
    Represents an ellipse in 3D space.

    Attributes:
        center (Point): The center of the ellipse.
        axis1 (Point): A unit vector representing the ellipse's local X-axis (direction of the major axis).
        axis2 (Point): A unit vector representing the ellipse's local Y-axis.
        major_radius (float): The radius along the major axis.
        minor_radius (float): The radius along the minor axis.
        color (str): The outline color.
        line_width (float): The width of the outline.
        steps (int): The number of segments used to approximate the ellipse (default is 50).
    """

    center: Point
    axis1: Point
    axis2: Point
    major_radius: float
    minor_radius: float
    color: str
    line_width: float
    steps: int = 50

    def local_to_global(self, u: float, v: float) -> Point:
        """
        Convert local (u, v) coordinates (in the ellipse's plane) to global 3D coordinates.
        """
        global_coord = self.center.array + u * self.axis1.array + v * self.axis2.array
        return Point(global_coord[0], global_coord[1], global_coord[2])

    def rebuild(self) -> None:
        """
        Rebuilds the ellipse object by sampling points along the ellipse's circumference and
        assembling them into a closed polyline.
        """
        # Sample angles from 0 to 2π
        t_values = np.linspace(0, 2 * math.pi, self.steps + 1)
        points = []
        # Parametric equation of an ellipse: (major_radius * cos(t), minor_radius * sin(t))
        for t in t_values:
            u = self.major_radius * math.cos(t)
            v = self.minor_radius * math.sin(t)
            points.append(self.local_to_global(u, v))
        # Wrap the points in LineVertex objects
        vertices = [LineVertex(pt) for pt in points]
        # Build a closed polyline (LINE_LOOP) for the ellipse
        poly = PolyLines(width=self.line_width, color=self.color, points=vertices, line_type="LINE_LOOP")
        poly.rebuild()
        self._data = poly.data


# --- Ellipsoid Implementation ---
@dataclass
class Ellipsoid(GraphicObject):
    """
    Represents an ellipsoid in 3D space as a triangle mesh.

    Attributes:
        center (Point): The center of the ellipsoid.
        radius_x (float): Radius along the x-axis.
        radius_y (float): Radius along the y-axis.
        radius_z (float): Radius along the z-axis.
        color (str): The color of the ellipsoid.
        steps_theta (int): Number of subdivisions along the polar angle (theta).
        steps_phi (int): Number of subdivisions along the azimuthal angle (phi).
    """

    center: Point
    radius_x: float
    radius_y: float
    radius_z: float
    color: str
    steps_theta: int = 50
    steps_phi: int = 50

    def rebuild(self) -> None:
        """
        Rebuilds the ellipsoid by generating a triangle mesh using its parametric equations.
        The resulting CGO data is stored in self._data.
        """
        # Generate parameter grids using numpy (vectorized)
        theta = np.linspace(0, math.pi, self.steps_theta + 1)  # polar angle
        phi = np.linspace(0, 2 * math.pi, self.steps_phi + 1)  # azimuthal angle
        # Create meshgrid (theta: rows, phi: columns)
        theta_grid, phi_grid = np.meshgrid(theta, phi, indexing="ij")

        # Compute x, y, z coordinates using vectorized operations
        x = self.center.x + self.radius_x * np.sin(theta_grid) * np.cos(phi_grid)
        y = self.center.y + self.radius_y * np.sin(theta_grid) * np.sin(phi_grid)
        z = self.center.z + self.radius_z * np.cos(theta_grid)

        # Stack to form an array of points with shape (steps_theta+1, steps_phi+1, 3)
        vertices_grid = np.stack((x, y, z), axis=-1)

        # Build triangle mesh from the vertex grid
        triangles = []
        for i in range(self.steps_theta):
            for j in range(self.steps_phi):
                # Each quad is formed by 4 vertices:
                p0 = Point(*vertices_grid[i, j])
                p1 = Point(*vertices_grid[i + 1, j])
                p2 = Point(*vertices_grid[i + 1, j + 1])
                p3 = Point(*vertices_grid[i, j + 1])
                # Split the quad into two triangles:
                triangles.append([p0, p1, p2])
                triangles.append([p0, p2, p3])

        # Assemble CGO object
        cgo_obj = []
        # Add color information if specified
        cgo_obj.extend(Color(self.color).as_cgo)
        # Begin triangle drawing mode
        cgo_obj.extend([cgo.BEGIN, cgo.TRIANGLES])
        # Add all triangle vertices to the CGO object
        for tri in triangles:
            for vertex in tri:
                cgo_obj.extend(vertex.as_vertex)
        cgo_obj.append(cgo.END)
        self._data = cgo_obj


# --- Polygon Implementation ---
@dataclass
class Polygon(GraphicObject):
    """
    Represents a filled polygon in 3D space.

    Attributes:
        vertices (List[Point]): A list of points that define the polygon's perimeter (in order).
        color (str): The fill color of the polygon.
    """

    vertices: list[Point]
    color: str

    def rebuild(self) -> None:
        """
        Rebuilds the polygon object by creating a CGO triangle fan from the vertices.
        """
        cgo_obj = []
        # Add color information if available.
        cgo_obj.extend(Color(self.color).as_cgo)
        # Begin triangle fan drawing mode.
        cgo_obj.extend([cgo.BEGIN, cgo.TRIANGLE_FAN])
        # Add each vertex to the CGO object.
        for vertex in self.vertices:
            cgo_obj.extend(vertex.as_vertex)
        # End the drawing.
        cgo_obj.append(cgo.END)
        self._data = cgo_obj


# --- Polyhedron Implementation ---


@dataclass
class Polyhedron(GraphicObject):
    """
    Represents a polyhedron in 3D space defined by vertices and faces.

    Attributes:
        vertices (List[Point]): A list of vertices of the polyhedron.
        faces (List[List[int]]): A list of faces, each face is a list of indices (into the vertices list).
        color (str): The fill color of the polyhedron.
    """

    vertices: list[Point]
    faces: list[list[int]]
    color: str

    def rebuild(self) -> None:
        """
        Rebuilds the polyhedron by creating a CGO object.
        Each face is drawn as a triangle fan to fill the polygon.
        """
        cgo_obj = []
        # Add color info
        cgo_obj.extend(Color(self.color).as_cgo)
        # For each face, generate a triangle fan
        for face in self.faces:
            if len(face) < 3:
                continue  # Skip degenerate faces
            cgo_obj.extend([cgo.BEGIN, cgo.TRIANGLE_FAN])
            # Add vertices from the face
            for idx in face:
                vertex = self.vertices[idx]
                cgo_obj.extend(vertex.as_vertex)
            cgo_obj.append(cgo.END)
        self._data = cgo_obj


def to3d(pt):
    """
    Ensures that the given point (tuple or list) has three components.
    If it only has two, append 0.0 for the z-coordinate.
    """
    pt = tuple(pt)
    if len(pt) == 2:
        return pt + (0.0,)
    return pt


def sample_quadratic_bezier(p0, p1, p2, num=10):
    """
    Samples a quadratic Bézier curve defined by p0, p1, and p2.
    Ensures that each point is represented as a 3D coordinate (z=0 if not provided).

    Args:
        p0: Starting point (iterable of 2 or 3 floats).
        p1: Control point (iterable of 2 or 3 floats).
        p2: Ending point (iterable of 2 or 3 floats).
        num (int): Number of samples.

    Returns:
        List of (x, y, z) tuples representing sampled points along the curve.
    """

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
        pt = (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t**2 * p2
        pts.append(tuple(pt))
    return pts


# --- Custom Pen for Collecting Glyph Outlines ---


class PolygonPen:
    """
    A custom pen that collects glyph outlines as contours (lists of Points).
    Implements the FontTools pen interface.
    """

    def __init__(self, sample_num: int = 10):
        self.contours: list[list[Point]] = []
        self.current_contour: list[Point] = []
        self.sample_num = sample_num

    def moveTo(self, pt):
        # pt is a tuple (x, y) or (x, y, z)
        p = Point(*to3d(pt))
        self.current_contour = [p]

    def lineTo(self, pt):
        p = Point(*to3d(pt))
        self.current_contour.append(p)

    def qCurveTo(self, *points):
        # points: a sequence of points (tuples). The last may be None.
        pts = list(points)
        if pts[-1] is None:
            pts = pts[:-1]
        start = self.current_contour[-1]
        # For each quadratic segment, sample points along the curve.
        # For simplicity, assume pairs of (control, end). If multiple controls, chain them.
        for i in range(0, len(pts) - 1, 2):
            control = pts[i]
            end = pts[i + 1]
            sampled = sample_quadratic_bezier(start.array, control, end, num=self.sample_num)
            # Append sampled points (skip the first to avoid duplication)
            for coord in sampled[1:]:
                self.current_contour.append(Point(coord[0], coord[1], coord[2]))
            # Update start for potential chaining using to3d helper
            start = Point(*to3d(end))
        # Optionally, do nothing else here.

    def closePath(self):
        if self.current_contour:
            self.contours.append(self.current_contour)
            self.current_contour = []

    def endPath(self):
        self.closePath()


# --- TextCharPolygon: Convert a Character to Polygonal Outlines ---
@dataclass
class TextCharPolygon(GraphicObject):
    """
    Represents a character as polygon outlines extracted from a font file.

    Attributes:
        char (str): The character to render.
        font_path (str): Path to a TrueType (or similar) font file.
        color (str): The outline color.
        scale (float): Scaling factor for the glyph.
        offset (Optional[Point]): An optional offset to apply.

        width (float): The width of the character.
        format (str): the implementation format of the polygon data.
            - 'LINE_LOOP': use line loop to draw the wireframe
            - 'SAUSAGE': use sausage to draw the wireframe

        sample_num: The number of samples to use for the polygon approximation in Bezeir sampling
    """

    char: str
    font_path: str
    color: str
    scale: float = 1.0
    offset: Point | None = None

    width: float = 1.0
    format: Literal["LINE_LOOP", "SAUSAGE", "TRIANGLE_FAN"] = "LINE_LOOP"
    sample_num: int = 10

    def rebuild(self) -> None:
        # Open the font and get the glyph for the character.
        font = TTFont(self.font_path)
        cmap = font["cmap"].getBestCmap()  # type: ignore # Map from Unicode codepoints to glyph names
        glyph_name = cmap.get(ord(self.char))
        if glyph_name is None:
            raise ValueError(f"Glyph for character '{self.char}' not found in {self.font_path}")
        glyph_set = font.getGlyphSet()
        glyph = glyph_set[glyph_name]
        # Use our custom pen to collect the outline.
        pen = PolygonPen(sample_num=self.sample_num)
        glyph.draw(pen)
        # Get the raw contours (each a list of Points)
        polygons = pen.contours

        # Apply scale and offset
        scaled_polygons: list[list[Point]] = []
        for contour in polygons:
            scaled_contour: list[Point] = []
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

        # Build a CGO object: for simplicity, we'll output each contour as a closed polyline.
        cgo_obj = []
        cgo_obj.extend(Color(self.color).as_cgo)
        if self.format == "LINE_LOOP":
            for contour in scaled_polygons:
                # Ensure the contour is closed.
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
        elif self.format == "SAUSAGE":
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
            raise NotImplementedError(f"{self.format} is not support.")

        self._data = cgo_obj


@dataclass
class TextBoard(GraphicObject):
    text: str
    font_path: str

    start_point: Point = Point(0, 0, 0)

    color: str = "random"

    scale: float = 0.1
    offset = Point(0, 0, 0)
    width: float = 5
    space: float = 100
    format: Literal["LINE_LOOP", "SAUSAGE", "TRIANGLE_FAN"] = "SAUSAGE"
    sample_num: int = 5

    def rebuild(self):
        import random

        if self.color == "random":
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

            if char != "\n":
                curser_point = curser_point.move(x=curser_point.x + space)
            else:
                curser_point = curser_point.move(x=origin_point.x, y=curser_point.y - self.space * 2)
                continue

            goc.objects.append(
                TextCharPolygon(
                    char=char,
                    font_path=self.font_path,
                    color=c,
                    scale=self.scale,
                    offset=curser_point,
                    width=self.width,
                    format="SAUSAGE",
                    sample_num=self.sample_num,
                )
            )

        goc.rebuild()

        self._data = goc.data


# # --- Helper functions to build specific Platonic solids ---

# def build_tetrahedron(center: Point, size: float):
#     """
#     Builds a tetrahedron (4 faces, all triangular).
#     Uses vertices (1,1,1), (1,-1,-1), (-1,1,-1), (-1,-1,1) scaled so that edge length equals size.
#     """
#     # For the tetrahedron defined by these 4 vertices, the edge length is 2√2.
#     scale = size / (2 * math.sqrt(2))
#     verts = [
#         Point(center.x + scale *  1, center.y + scale *  1, center.z + scale *  1),
#         Point(center.x + scale *  1, center.y + scale * -1, center.z + scale * -1),
#         Point(center.x + scale * -1, center.y + scale *  1, center.z + scale * -1),
#         Point(center.x + scale * -1, center.y + scale * -1, center.z + scale *  1)
#     ]
#     faces = [
#         [0, 1, 2],
#         [0, 3, 1],
#         [0, 2, 3],
#         [1, 3, 2]
#     ]
#     return verts, faces

# def build_cube(center: Point, size: float):
#     """
#     Builds a cube (6 faces, each a square).
#     The cube edge length is 'size'.
#     """
#     s = size / 2
#     verts = [
#         Point(center.x - s, center.y - s, center.z - s),  # 0
#         Point(center.x + s, center.y - s, center.z - s),  # 1
#         Point(center.x - s, center.y + s, center.z - s),  # 2
#         Point(center.x + s, center.y + s, center.z - s),  # 3
#         Point(center.x - s, center.y - s, center.z + s),  # 4
#         Point(center.x + s, center.y - s, center.z + s),  # 5
#         Point(center.x - s, center.y + s, center.z + s),  # 6
#         Point(center.x + s, center.y + s, center.z + s)   # 7
#     ]
#     faces = [
#         [0, 1, 3, 2],  # bottom
#         [4, 5, 7, 6],  # top
#         [0, 1, 5, 4],  # front
#         [1, 3, 7, 5],  # right
#         [3, 2, 6, 7],  # back
#         [2, 0, 4, 6]   # left
#     ]
#     return verts, faces

# def build_octahedron(center: Point, size: float):
#     """
#     Builds an octahedron (8 faces, all triangular).
#     Standard vertices are (±1,0,0), (0,±1,0), (0,0,±1). For these, the edge length is √2.
#     """
#     scale = size / math.sqrt(2)
#     verts = [
#         Point(center.x + scale, center.y, center.z),    # 0
#         Point(center.x - scale, center.y, center.z),    # 1
#         Point(center.x, center.y + scale, center.z),    # 2
#         Point(center.x, center.y - scale, center.z),    # 3
#         Point(center.x, center.y, center.z + scale),    # 4
#         Point(center.x, center.y, center.z - scale)     # 5
#     ]
#     faces = [
#         [0, 2, 4],
#         [2, 1, 4],
#         [1, 3, 4],
#         [3, 0, 4],
#         [0, 2, 5],
#         [2, 1, 5],
#         [1, 3, 5],
#         [3, 0, 5]
#     ]
#     return verts, faces

# def build_icosahedron(center: Point, size: float):
#     """
#     Builds an icosahedron (20 faces, all triangular).
#     Standard coordinates (before scaling) for an icosahedron:
#       (0, ±1, ±phi), (±1, ±phi, 0), (±phi, 0, ±1)
#     For these coordinates the edge length is 2, so we scale by size/2.
#     """
#     phi = (1 + math.sqrt(5)) / 2
#     verts_raw = [
#         (0,  1,  phi),
#         (0,  1, -phi),
#         (0, -1,  phi),
#         (0, -1, -phi),
#         (1,  phi, 0),
#         (1, -phi, 0),
#         (-1,  phi, 0),
#         (-1, -phi, 0),
#         (phi, 0,  1),
#         (phi, 0, -1),
#         (-phi, 0,  1),
#         (-phi, 0, -1)
#     ]
#     scale = size / 2  # since standard edge length is 2
#     verts = [Point(center.x + scale * x, center.y + scale * y, center.z + scale * z) for (x, y, z) in verts_raw]
#     faces = [
#         [0, 8, 4],
#         [0, 4, 6],
#         [0, 6, 10],
#         [0, 10, 2],
#         [0, 2, 8],
#         [8, 2, 5],
#         [8, 5, 9],
#         [8, 9, 4],
#         [4, 9, 1],
#         [4, 1, 6],
#         [6, 1, 11],
#         [6, 11, 10],
#         [10, 11, 3],
#         [10, 3, 2],
#         [2, 3, 5],
#         [5, 3, 7],
#         [5, 7, 9],
#         [9, 7, 1],
#         [1, 7, 11],
#         [11, 7, 3]
#     ]
#     return verts, faces

# def build_dodecahedron(center: Point, size: float):
#     """
#     Builds a dodecahedron (12 faces, each a regular pentagon).
#     Its construction is more involved. Here, we provide a placeholder indicating that
#     a robust dodecahedron implementation is not provided.
#     """
#     raise NotImplementedError("Dodecahedron construction is not implemented in this example.")

# # --- RegularPolyhedron Class ---

# @dataclass
# class RegularPolyhedron(GraphicObject):
#     """
#     Represents a regular polyhedron with parametric input.

#     Parameters:
#         n (int): Number of faces (allowed: 4, 6, 8, 12, or 20).
#         center (Point): The center of the polyhedron.
#         size (float): The edge length (size of each face).
#         color (str): The color of the polyhedron.
#     """
#     n: int
#     center: Point
#     size: float
#     color: str = "white"

#     _vertices: List[Point] = None
#     _faces: List[List[int]] = None

#     def rebuild(self) -> None:
#         if self.n == 4:
#             self._vertices, self._faces = build_tetrahedron(self.center, self.size)
#         elif self.n == 6:
#             self._vertices, self._faces = build_cube(self.center, self.size)
#         elif self.n == 8:
#             self._vertices, self._faces = build_octahedron(self.center, self.size)
#         elif self.n == 20:
#             self._vertices, self._faces = build_icosahedron(self.center, self.size)
#         elif self.n == 12:
#             self._vertices, self._faces = build_dodecahedron(self.center, self.size)
#         else:
#             raise ValueError("Regular polyhedron with n faces not supported. Allowed values: 4, 6, 8, 12, 20.")

#         # Build CGO object by triangulating each face (using a triangle fan)
#         cgo_obj = []
#         cgo_obj.extend(Color(self.color).as_cgo)
#         for face in self._faces:
#             if len(face) < 3:
#                 continue
#             cgo_obj.extend([cgo.BEGIN, cgo.TRIANGLE_FAN])
#             for idx in face:
#                 cgo_obj.extend(self._vertices[idx].as_vertex)
#             cgo_obj.append(cgo.END)
#         self._data = cgo_obj


@dataclass
class GraphicObjectCollection(GraphicObject):
    """
    A collection class for GraphicObject, which contains multiple graphic objects.

    Attributes:
        objects (List[GraphicObject]): A list of GraphicObject instances.
        force_to_rebuild (bool): Whether to rebuild everything before merging data.
    """

    objects: list[GraphicObject]
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
        for go_idx, go in enumerate(self.objects):
            # Print the addition information of the graphic object
            print(f"Adding: #{go_idx} ({go.__class__.__name__})")
            # If forced to rebuild, call the rebuild method on the graphic object
            if self.force_to_rebuild:
                go.rebuild()
        # Iterate through each graphic object in the collection
        self._data.extend(tree.flatten([go.data for go in self.objects]))


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

# Arrow(
#     Point(1, 2, 3),
#     Point(4,5, 7),
#     .5,2
# ).load_as('my_arrow')

# Arrow(
#     Point(0, 0, 0),
#     Point(4,5, 7),
#     .5,2
# ).load_as('my_zero_arrow')


# Arrow(
#     Point(4,5,7),
#     Point(10,2, 3),
#     .5,4,2
# ).load_as('my_spike')

# Define the center and the local axes (unit vectors in the rectangle's plane)


# # Create a 3D rounded rectangle with specified parameters
# rounded_rect = RoundedRectangle(
#     center=Point(0, 0, 0),
#     axis1=Point(1, 0, 0),  # Local X-axis,
#     axis2=Point(0, 1, 0),  # Local Y-axis,
#     width=5,
#     height=5,
#     radius=3,
#     color='green',
#     line_width=3,
#     steps=20  # Increase for smoother rounded corners
# )

# # Rebuild the object to compute its CGO data
# rounded_rect.rebuild()
# rounded_rect.load_as('rounded_rect_rounder')

# # Create an Ellipse3D: major_radius = 5, minor_radius = 3, with blue outline and line width of 2.
# ellipse = Ellipse(
#     center=Point(0, 0, 0),
#     axis1=Point(1, 2, 3), # Local X-axis (major axis direction)
#     axis2=Point(3, 1, -1),  # Local Y-axis,
#     major_radius=5,
#     minor_radius=2,
#     color='blue',
#     line_width=2,
#     steps=50  # More steps for smoother ellipse
# )

# ellipse.load_as('my_ellipse')


# ellipsoid = Ellipsoid(
#     center=Point(0, 0, 0),
#     radius_x=1,
#     radius_y=1,
#     radius_z=1,
#     color='green',
#     steps_theta=20,
#     steps_phi=30
# )
# ellipsoid.load_as('my_ellispsoid')

# vertices = [
#     Point(0, 0, 0),
#     Point(1, 0, 0),
#     Point(1.5, 1, 0),
#     Point(0.5, 1.5, 0),
#     Point(-0.5, 1, 0)
# ]
# poly = Polygon(vertices=vertices, color='red')
# poly.rebuild()
# poly.load_as('my_polygon')


# # Define the vertices of a cube.
# vertices = [
#     Point(-1, -1, -1),  # 0
#     Point( 1, -1, -1),  # 1
#     Point( 1,  1, -1),  # 2
#     Point(-1,  1, -1),  # 3
#     Point(-1, -1,  1),  # 4
#     Point( 1, -1,  1),  # 5
#     Point( 1,  1,  1),  # 6
#     Point(-1,  1,  1)   # 7
# ]
# Define the faces of the cube (each face as a list of vertex indices).
# faces = [
#     [0, 1, 2, 3],  # bottom face
#     [4, 5, 6, 7],  # top face
#     [0, 1, 5, 4],  # front face
#     [1, 2, 6, 5],  # right face
#     [2, 3, 7, 6],  # back face
#     [3, 0, 4, 7]   # left face
# ]
# # Create the polyhedron with a cyan color.
# cube = Polyhedron(vertices=vertices, faces=faces, color='cyan')
# cube.rebuild()
# cube.load_as('my_polyhedron')

# for (_,n), (_,c) in zip(enumerate([4, 6, 8, 20]), enumerate('rgby')):
#     center = Point(0, 0, 0)
#     cube = RegularPolyhedron(n=n, center=center, size=2, color=c)

#     cube.load_as(f'my_{n}_{c}_polyhedron')


# def test_text():
#     import random
#     # Specify a TTF font file path (update this path to one available on your system)
# font_path = "/Library/Fonts/Microsoft/Microsoft Yahei.ttf"  # e.g.,
# "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

#     for (idx, c ), (_, color)in zip(enumerate('APTX-4869'), enumerate(random.sample(list(CSS4_COLORS.keys()),100))):
#         text_char = TextCharPolygon(
#             char=c,
#             font_path=font_path,
#             color=color,
#             scale=0.1,
#             offset=Point(0+idx*150, 0, 0),
#             width=5,
#             format='SAUSAGE',
#             sample_num=5
#         )
#         text_char.rebuild()
#         text_char.load_as(f"my_text_char_{idx}")

#     cmd.zoom()

# with timing('writing'):
#     test_text()

# font_path = "/Users/yyy/Downloads/simhei.ttf"
# text='Silver Bullet\n\nCool Kid'


# TextBoard(
#     text=text,
#     font_path=font_path,
#     width=1.5, space=10
# ).load_as('silver_bullet')


# also a quick demo to construct complicated cgo object
def __easter_egg():
    if any(not n.startswith("_") for n in cmd.get_names()):
        # silently do nothing if the session is currently in use
        return

    # if the date is December 24-25th, show a Christmas tree
    today = datetime.date.today()
    # print(f'Today is {today}')
    if today.month == 12 and today.day in (24, 25, 26, 27, 28):
        return _dec25tree()
    return _aptx4869()

def _aptx4869():
    """
    There is always only one truth!

    真しん実じつはいつもひとつ!
    """
    

    poision = GraphicObjectCollection(
        [
            # the APTX-4869 capsule
            # white part
            Sphere(center=Point(-2, 0, 0), radius=1, color="white"),
            Cylinder(Point(-2, 0, 0), Point(0.5, 0, 0), radius=1, color1="white", color2="white"),
            # red part that covers the white part
            Cylinder(Point(0, 0, 0), Point(2, 0, 0), radius=1.015, color1="red", color2="red"),
            Sphere(center=Point(2, 0, 0), radius=1.015, color="red"),
            # printed curves (text container) on the surface
            PolyLines(
                5,
                "black",
                [
                    LineVertex(Point(-1.6, 0.5, 0.9)),  # left top
                    LineVertex(Point(1.6, 0.5, 0.9)),  # right top
                    LineVertex(
                        PseudoBezier(
                            [
                                Point(1.6, 0.5, 0.9),  # right top
                                Point(2.2, 0.5, 1.08),  # control point to make Bezier curve
                                Point(2.2, -0.5, 1.08),  # control point to make Bezier curve
                                Point(1.6, -0.5, 0.9),
                            ]  # right bottom
                        )
                    ),
                    LineVertex(Point(1.6, -0.5, 0.9)),  # right bottom
                    LineVertex(Point(-1.6, -0.5, 0.9)),  # left bottom
                    LineVertex(
                        PseudoBezier(
                            [
                                Point(-1.6, -0.5, 0.9),  # left bottom
                                Point(-2.2, -0.5, 1.05),  # control point to make Bezier curve
                                Point(-2.2, 0.5, 1.05),  # control point to make Bezier curve
                                Point(-1.6, 0.5, 0.9),
                            ]  # left top
                        )
                    ),
                ],
                line_type="LINE_LOOP",
            ),
        ]
    )

    # Printed text on the capsule
    cgo.cyl_text(
        poision.data,
        plain,
        Point(-1.5, -0.25, 1.01).array,
        "APTX-4869",
        0.03,
        axes=[Point(0.5, 0, 0).array, Point(0, 0.5, 0).array, Point(0, 0, 0.5).array],
        color=Color("black").array,
    )

    # from ..shortcuts.tools.vina_tools import showaxes

    # showaxes()
    poision.load_as("APTX-4869")

    cmd.turn("z", 16)

    cmd.zoom("APTX-4869", 0)
    cmd.movie.add_roll(8, loop=0, axis="y", start=1)

    cmd.set("movie_fps", 90)

    print(__easter_egg.__doc__)
    cmd.mplay()


def _dec25tree():
    """
    A Christmas tree to celebrate the holiday season!
    """
    def make_bulb(x, y, color):
        # calculate z coordinate on the cone surface
        z = 5 - (5 / 2) * math.sqrt(x**2 + y**2)
        return Sphere(center=Point(x, y, z), radius=.2, color=color)
        
    tree = GraphicObjectCollection(
        [
            # tree leaves
            Cone(
                tip=Point(0, 0, 5),
                base_center=Point(0, 0, 0),
                radius_tip=0,
                radius_base=2,
                color_base="forest_green",
                color_tip="forest_green",
                caps=(1, 0),
            ),
            # tree trunk
            Cylinder(
                Point(0, 0, -1),
                Point(0, 0, 0),
                radius=0.3,
                color1="brown",
                color2="brown",
            ),
            # bulbs on the tree
            Sphere(center=Point(1.3, 1.2, 1), radius=.2, color="red"),
            Sphere(center=Point(-0.6, 0.95, 2), radius=.2, color="yellow"),
            Sphere(center=Point(0.3, -0.6, 3), radius=.2, color="blue"),
            Sphere(center=Point(-0.4, -0.7  , 3), radius=.2, color="green"),
            Sphere(center=Point(0.7, -0.9, 2), radius=.2, color="orange"),
            Sphere(center=Point(-1.3, -1.2, 1), radius=.2, color="purple"),
            Sphere(center=Point(0.8, -0.9, 1.5), radius=.2, color="pink"),
            # star on the top
            Cone(
                tip=Point(0, 0, 6),
                base_center=Point(0, 0, 5),
                radius_tip=0,
                radius_base=0.5,
                color_base="gold",
                color_tip="gold",
                caps=(1, 0),
            ),
        ]
    )
    tree.load_as("revodesign_christmas_tree")
    cmd.zoom("revodesign_christmas_tree", 2)
    print(_dec25tree.__doc__)
    cmd.mplay()


cmd.extend("hello_revodesign", __easter_egg)
