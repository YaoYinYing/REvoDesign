# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


import itertools
import math
from unittest.mock import patch

import numpy as np
import pytest
from pymol import cgo, cmd

from REvoDesign.tools.cgo_utils import (
    Arrow,
    Color,
    Cone,
    Cube,
    Cylinder,
    Doughnut,
    Ellipse,
    Ellipsoid,
    GraphicObject,
    GraphicObjectCollection,
    LineVertex,
    Point,
    Polygon,
    Polyhedron,
    PolyLines,
    PseudoBezier,
    PseudoCurve,
    RoundedRectangle,
    Sausage,
    Sphere,
    Square,
    TextBoard,
    TriangleSimple,
    __easter_egg,
    not_none_float,
)


@pytest.mark.parametrize(
    "args, expected",
    [
        ((None, None, None), 0.0),  # All arguments are None
        ((None, 3.14, None), 3.14),  # First non-None argument is a valid float
        ((None, "42.0", None), 42.0),  # First non-None argument is a string that can be converted to a float
        ((None, "not_a_number", 3.14), 3.14),  # First non-None argument is a string that cannot be converted to a float
        (("a", "b", "c"), 0.0),  # All non-None arguments are strings that cannot be converted to a float
        (("100", 200, "300"), 100.0),  # Mixed types where the first valid float is returned
        ((1.0,), 1.0),  # Single valid float
        (("not_a_number",), 0.0),  # Single non-convertible string
        (("5.5",), 5.5),  # Single convertible string
        ((None,), 0.0),  # Single None
    ],
)
def test_not_none_float(args, expected):
    """Test the not_none_float function with various input scenarios."""
    assert not_none_float(*args) == expected


points = [
    (Point(1, 2, 3), Point(4, 5, 6)),
    (Point(-1, -2, -3), Point(1, 2, 3)),
    (Point(0, 0, 0), Point(1, 1, 1)),
]


@pytest.mark.parametrize("point1, point2", points)
def test_add(point1, point2):
    result = point1 + point2
    expected = Point(point1.x + point2.x, point1.y + point2.y, point1.z + point2.z)
    assert result == expected


@pytest.mark.parametrize("point1, point2", points)
def test_sub(point1, point2):
    result = point1 - point2
    expected = Point(point1.x - point2.x, point1.y - point2.y, point1.z - point2.z)
    assert result == expected


@pytest.mark.parametrize("point, scalar", [(Point(1, 2, 3), 2), (Point(-1, -2, -3), 3)])
def test_truediv(point, scalar):
    result = point / scalar
    expected = Point(point.x / scalar, point.y / scalar, point.z / scalar)
    assert result == expected


@pytest.mark.parametrize("point, scalar", [(Point(1, 2, 3), 2), (Point(-1, -2, -3), 3)])
def test_mul(point, scalar):
    result = point * scalar
    expected = Point(point.x * scalar, point.y * scalar, point.z * scalar)
    assert result == expected


@pytest.mark.parametrize("point1, point2", points)
def test_dot(point1, point2):
    result = Point.dot(point1, point2)
    expected = np.dot(point1.array, point2.array)
    assert result == expected


@pytest.mark.parametrize("point1, point2", points)
def test_cross(point1, point2):
    result = Point.cross(point1, point2)
    expected = Point.from_array(np.cross(point1.array, point2.array))
    assert result == expected


@pytest.mark.parametrize(
    "point, x, y, z",
    [
        (Point(1, 2, 3), 4, 5, 6),
        (Point(-1, -2, -3), 1, 2, 3),
        (Point(0, 0, 0), 1, 1, 1),
        (Point(1, 2, 3), None, None, None),
    ],
)
def test_move(point, x, y, z):
    result = point.move(x, y, z)
    expected_x = x if x is not None else point.x
    expected_y = y if y is not None else point.y
    expected_z = z if z is not None else point.z
    expected = Point(expected_x, expected_y, expected_z)
    assert result == expected


@pytest.mark.parametrize(
    "points",
    [
        [Point(1, 2, 3), Point(4, 5, 6)],
        [Point(-1, -2, -3), Point(1, 2, 3)],
        [Point(0, 0, 0), Point(1, 1, 1)],
    ],
)
def test_as_arrays(points):
    result = Point.as_arrays(points)
    expected = np.concatenate([point.array for point in points])
    assert np.array_equal(result, expected)


@pytest.mark.parametrize(
    "points",
    [
        [Point(1, 2, 3), Point(4, 5, 6)],
        [Point(-1, -2, -3), Point(1, 2, 3)],
        [Point(0, 0, 0), Point(1, 1, 1)],
    ],
)
def test_as_vertexes(points):
    result = Point.as_vertexes(points)
    expected = np.concatenate([point.as_vertex for point in points])
    assert np.array_equal(result, expected)


@pytest.mark.parametrize("point1, point2", points)
def test_delta_xyz(point1, point2):
    result = point1.delta_xyz(point2)
    expected = point2.array - point1.array
    assert np.array_equal(result, expected)


@pytest.mark.parametrize("point1, point2", points)
def test_center_xyz(point1, point2):
    result = point1.center_xyz(point2)
    expected = (point2.array - point1.array) / 2
    assert np.array_equal(result, expected)


@pytest.mark.parametrize("point1, point2", points)
def test_distance_to(point1, point2):
    result = point1.distance_to(point2)
    expected = np.linalg.norm(point2.array - point1.array).astype(float)
    assert result == expected


@pytest.mark.parametrize(
    "color_name, alpha, expected_rgb",
    [
        ("r", 1.0, np.array([1.0, 0.0, 0.0])),
        ("b", 0.5, np.array([0.0, 0.0, 1.0])),
        ("g", 0.75, np.array([0.0, 0.5, 0.0])),
        ("white", 1.0, np.array([1.0, 1.0, 1.0])),
        ("black", 0.25, np.array([0.0, 0.0, 0.0])),
    ],
)
def test_color_array(color_name, alpha, expected_rgb):
    color = Color(name=color_name, alpha=alpha)
    assert np.allclose(color.array, expected_rgb, rtol=1e-2)


@pytest.mark.parametrize(
    "color_name, alpha, expected_rgba",
    [
        ("r", 1.0, np.array([1.0, 0.0, 0.0, 1.0])),
        ("b", 0.5, np.array([0.0, 0.0, 1.0, 0.5])),
        ("g", 0.75, np.array([0.0, 0.5, 0.0, 0.75])),
        ("white", 1.0, np.array([1.0, 1.0, 1.0, 1.0])),
        ("black", 0.25, np.array([0.0, 0.0, 0.0, 0.25])),
    ],
)
def test_color_array_alpha(color_name, alpha, expected_rgba):
    color = Color(name=color_name, alpha=alpha)
    assert np.allclose(color.array_alpha, expected_rgba, rtol=1e-2)


@pytest.mark.parametrize(
    "colors, expected_cgos",
    [
        (
            [Color("r", 1.0), Color("b", 0.5)],
            np.concatenate(
                [
                    np.array([cgo.ALPHA, 1.0, cgo.COLOR, 1.0, 0.0, 0.0]),
                    np.array([cgo.ALPHA, 0.5, cgo.COLOR, 0.0, 0.0, 1.0]),
                ]
            ),
        ),
        (
            [Color("g", 0.75), Color("white", 1.0)],
            np.concatenate(
                [
                    np.array([cgo.ALPHA, 0.75, cgo.COLOR, 0.0, 0.5, 0.0]),
                    np.array([cgo.ALPHA, 1.0, cgo.COLOR, 1.0, 1.0, 1.0]),
                ]
            ),
        ),
    ],
)
def test_color_as_cgos(colors, expected_cgos):
    result = Color.as_cgos(colors)
    assert np.allclose(result, expected_cgos, rtol=1e-2)


@pytest.mark.parametrize(
    "name, expected_call_args",
    [
        ("object1", ("object1",)),
        ("object2", ("object2",)),
    ],
)
def test_load_as(name, expected_call_args):
    with patch("REvoDesign.tools.cgo_utils.cmd") as mock_cmd:
        mock_cmd.get_names.return_value = [name]
        graphic_object = GraphicObject()
        graphic_object._data = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]

        graphic_object.load_as(name)

        mock_cmd.delete.assert_called_once_with(name)
        mock_cmd.load_cgo.assert_called_once_with(graphic_object.data, *expected_call_args)


@pytest.mark.parametrize(
    "name, existing_names, expected_delete_calls",
    [
        ("object1", ["object1"], 1),
        ("object2", ["object2"], 1),
        ("object3", [], 0),
    ],
)
def test_load_as_delete_calls(name, existing_names, expected_delete_calls):
    with patch("REvoDesign.tools.cgo_utils.cmd") as mock_cmd:
        mock_cmd.get_names.return_value = existing_names
        graphic_object = GraphicObject()
        graphic_object._data = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]

        graphic_object.load_as(name)

        assert mock_cmd.delete.call_count == expected_delete_calls
        mock_cmd.load_cgo.assert_called_once_with(graphic_object.data, name)


@pytest.mark.parametrize(
    "control_points, color, steps, expected_vertices",
    [
        ([Point(0, 0, 0), Point(1, 1, 1)], "r", 2, [Point(0, 0, 0), Point(1, 1, 1)]),
        ([Point(0, 0, 0), Point(1, 1, 1), Point(2, 2, 2)], "b", 3, [Point(0, 0, 0), Point(1, 1, 1), Point(2, 2, 2)]),
    ],
)
def test_rebuild(control_points, color, steps, expected_vertices):
    with patch.object(PseudoCurve, "sample", return_value=expected_vertices):
        pseudo_curve = PseudoCurve(control_points=control_points, color=color, steps=steps)
        pseudo_curve.rebuild()

        expected_cgo = []
        if color is not None:
            expected_cgo.extend(Color(color).as_cgo)
        expected_cgo.extend(Point.as_vertexes(expected_vertices))

        assert np.allclose(pseudo_curve.data, expected_cgo)


@pytest.mark.parametrize(
    "control_points, num_min, num_max, expected_exception",
    [
        ([Point(0, 0, 0)], 2, None, ValueError),
        ([Point(0, 0, 0), Point(1, 1, 1), Point(2, 2, 2)], None, 2, ValueError),
        ([Point(0, 0, 0), Point(1, 1, 1)], 2, 3, None),
    ],
)
def test_check_control_points(control_points, num_min, num_max, expected_exception):
    with patch.object(PseudoCurve, "sample", return_value=control_points):
        pseudo_curve = PseudoCurve(control_points=control_points)
        if expected_exception:
            with pytest.raises(expected_exception):
                pseudo_curve.check_control_points(num_min=num_min, num_max=num_max)
        else:
            pseudo_curve.check_control_points(num_min=num_min, num_max=num_max)


@pytest.mark.parametrize(
    "control_points, steps, expected_points",
    [
        (
            [Point(0, 0, 0), Point(1, 0, 0), Point(1, 1, 0), Point(0, 1, 0)],
            1,
            [Point(0.0, 0.0, 0.0), Point(0.0, 1.0, 0.0)],
        ),
        (
            [Point(0, 0, 0), Point(0, 1, 0), Point(1, 1, 0), Point(1, 0, 0)],
            2,
            [Point(0.0, 0.0, 0.0), Point(0.5, 0.75, 0.0), Point(1.0, 0.0, 0.0)],
        ),
    ],
)
def test_pseudo_bezier_sample(control_points, steps, expected_points):
    bezier = PseudoBezier(control_points, steps=steps)
    sampled_points = bezier.sample()
    assert sampled_points == expected_points


@pytest.mark.parametrize(
    "point, width, color",
    [
        (Point(1.0, 2.0, 3.0), 2.5, "red"),
        (Point(4.0, 5.0, 6.0), None, "blue"),
        (Point(7.0, 8.0, 9.0), 1.5, None),
        (Point(10.0, 11.0, 12.0), None, None),
    ],
)
def test_line_vertex_rebuild(point, width, color):
    lv = LineVertex(point, width=width, color=color)
    lv.rebuild()
    expected_data = []

    if width:
        expected_data.extend([cgo.LINEWIDTH, width])

    if color:
        expected_data.extend(Color(color).as_cgo)

    if isinstance(point, Point):
        expected_data.extend(point.as_vertex)
    elif isinstance(point, PseudoCurve):
        expected_data.extend(point.data)

    assert lv._data == expected_data


@pytest.mark.parametrize(
    "points, width, color, expected",
    [
        (
            [Point(1.0, 2.0, 3.0), Point(4.0, 5.0, 6.0)],
            2.5,
            "red",
            (
                LineVertex(Point(1.0, 2.0, 3.0), width=2.5, color="red"),
                LineVertex(Point(4.0, 5.0, 6.0), width=2.5, color="red"),
            ),
        ),
        (
            [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)],
            None,
            "blue",
            (
                LineVertex(Point(1.0, 2.0, 3.0), width=None, color="blue"),
                LineVertex(Point(4.0, 5.0, 6.0), width=None, color="blue"),
            ),
        ),
        (
            [Point(7.0, 8.0, 9.0), (10.0, 11.0, 12.0)],
            1.5,
            None,
            (
                LineVertex(Point(7.0, 8.0, 9.0), width=1.5, color=None),
                LineVertex(Point(10.0, 11.0, 12.0), width=1.5, color=None),
            ),
        ),
    ],
)
def test_line_vertex_from_points(points, width, color, expected):
    result = LineVertex.from_points(points, width=width, color=color)
    assert result == expected


@pytest.mark.parametrize(
    "center, radius, color, expected_data",
    [
        (Point(1.0, 2.0, 3.0), 5.0, "r", [*Color("r").as_cgo, cgo.SPHERE, 1.0, 2.0, 3.0, 5.0]),
        (Point(0.0, 0.0, 0.0), 1.0, "b", [*Color("b").as_cgo, cgo.SPHERE, 0.0, 0.0, 0.0, 1.0]),
        (Point(-1.0, -2.0, -3.0), 2.0, "g", [*Color("g").as_cgo, cgo.SPHERE, -1.0, -2.0, -3.0, 2.0]),
        (Point(4.0, 5.0, 6.0), 3.0, "y", [*Color("y").as_cgo, cgo.SPHERE, 4.0, 5.0, 6.0, 3.0]),
    ],
)
def test_sphere_rebuild(center, radius, color, expected_data):
    sphere = Sphere(center=center, radius=radius, color=color)
    sphere.rebuild()
    assert sphere._data == expected_data


@pytest.mark.parametrize(
    "point1, point2, radius, color1, color2, expected_data",
    [
        (
            Point(0.0, 0.0, 0.0),
            Point(1.0, 1.0, 1.0),
            1.0,
            "violet",
            "cyan",
            [cgo.CYLINDER, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, *Color("violet").array, *Color("cyan").array],
        ),
        (
            Point(2.0, 2.0, 2.0),
            Point(3.0, 3.0, 3.0),
            2.0,
            "red",
            "blue",
            [cgo.CYLINDER, 2.0, 2.0, 2.0, 3.0, 3.0, 3.0, 2.0, *Color("red").array, *Color("blue").array],
        ),
        (
            Point(-1.0, -1.0, -1.0),
            Point(0.0, 0.0, 0.0),
            0.5,
            "green",
            "yellow",
            [cgo.CYLINDER, -1.0, -1.0, -1.0, 0.0, 0.0, 0.0, 0.5, *Color("green").array, *Color("yellow").array],
        ),
        (
            Point(4.0, 4.0, 4.0),
            Point(5.0, 5.0, 5.0),
            1.5,
            "orange",
            "purple",
            [cgo.CYLINDER, 4.0, 4.0, 4.0, 5.0, 5.0, 5.0, 1.5, *Color("orange").array, *Color("purple").array],
        ),
    ],
)
def test_cylinder_rebuild(point1, point2, radius, color1, color2, expected_data):
    cylinder = Cylinder(point1=point1, point2=point2, radius=radius, color1=color1, color2=color2)
    cylinder.rebuild()
    assert cylinder._data == expected_data


@pytest.mark.parametrize(
    "p1, p2, radius, color_1, color_2, expected_data",
    [
        (
            Point(0.0, 0.0, 0.0),
            Point(1.0, 1.0, 1.0),
            1.0,
            "red",
            "blue",
            [cgo.SAUSAGE, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, *Color("red").array, *Color("blue").array],
        ),
        (
            Point(2.0, 2.0, 2.0),
            Point(3.0, 3.0, 3.0),
            2.0,
            "green",
            "yellow",
            [cgo.SAUSAGE, 2.0, 2.0, 2.0, 3.0, 3.0, 3.0, 2.0, *Color("green").array, *Color("yellow").array],
        ),
        (
            Point(-1.0, -1.0, -1.0),
            Point(0.0, 0.0, 0.0),
            0.5,
            "orange",
            "purple",
            [cgo.SAUSAGE, -1.0, -1.0, -1.0, 0.0, 0.0, 0.0, 0.5, *Color("orange").array, *Color("purple").array],
        ),
        (
            Point(4.0, 4.0, 4.0),
            Point(5.0, 5.0, 5.0),
            1.5,
            "cyan",
            "magenta",
            [cgo.SAUSAGE, 4.0, 4.0, 4.0, 5.0, 5.0, 5.0, 1.5, *Color("cyan").array, *Color("magenta").array],
        ),
    ],
)
def test_sausage_rebuild(p1, p2, radius, color_1, color_2, expected_data):
    sausage = Sausage(p1=p1, p2=p2, radius=radius, color_1=color_1, color_2=color_2)
    sausage.rebuild()
    assert sausage._data == expected_data


@pytest.mark.parametrize(
    "center, normal, radius, color, cradius, samples, csamples",
    [
        (Point(0.0, 0.0, 0.0), Point(0.0, 0.0, 1.0), 1.0, "red", 0.25, 20, 20),
        (Point(1.0, 1.0, 1.0), Point(1.0, 0.0, 0.0), 2.0, "blue", 0.5, 30, 30),
        (Point(-1.0, -1.0, -1.0), Point(0.0, 1.0, 0.0), 0.5, "green", 0.1, 15, 15),
        (Point(2.0, 2.0, 2.0), Point(0.0, 0.0, -1.0), 1.5, "yellow", 0.3, 25, 25),
    ],
)
def test_doughnut_rebuild(center, normal, radius, color, cradius, samples, csamples):
    doughnut = Doughnut(
        center=center, normal=normal, radius=radius, color=color, cradius=cradius, samples=samples, csamples=csamples
    )
    doughnut.rebuild()
    expected_data = doughnut._data
    assert isinstance(expected_data, list)
    assert len(expected_data) > 0
    assert expected_data[0] == cgo.BEGIN
    assert expected_data[1] == cgo.TRIANGLE_STRIP
    assert expected_data[2] == cgo.COLOR


@pytest.mark.parametrize(
    "tip, base_center, radius_tip, radius_base, color_tip, color_base, caps, expected_data",
    [
        (
            Point(0.0, 0.0, 0.0),
            Point(1.0, 1.0, 1.0),
            0.1,
            0.5,
            "red",
            "blue",
            (1, 0),
            [cgo.CONE, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 0.1, 0.5, *Color("red").array, *Color("blue").array, 1, 0],
        ),
        (
            Point(2.0, 2.0, 2.0),
            Point(3.0, 3.0, 3.0),
            0.2,
            0.6,
            "green",
            "yellow",
            (0, 1),
            [cgo.CONE, 2.0, 2.0, 2.0, 3.0, 3.0, 3.0, 0.2, 0.6, *Color("green").array, *Color("yellow").array, 0, 1],
        ),
        (
            Point(-1.0, -1.0, -1.0),
            Point(0.0, 0.0, 0.0),
            0.3,
            0.7,
            "orange",
            "purple",
            (1, 1),
            [cgo.CONE, -1.0, -1.0, -1.0, 0.0, 0.0, 0.0, 0.3, 0.7, *Color("orange").array, *Color("purple").array, 1, 1],
        ),
        (
            Point(4.0, 4.0, 4.0),
            Point(5.0, 5.0, 5.0),
            0.4,
            0.8,
            "cyan",
            "magenta",
            (0, 0),
            [cgo.CONE, 4.0, 4.0, 4.0, 5.0, 5.0, 5.0, 0.4, 0.8, *Color("cyan").array, *Color("magenta").array, 0, 0],
        ),
    ],
)
def test_cone_rebuild(tip, base_center, radius_tip, radius_base, color_tip, color_base, caps, expected_data):
    cone = Cone(
        tip=tip,
        base_center=base_center,
        radius_tip=radius_tip,
        radius_base=radius_base,
        color_tip=color_tip,
        color_base=color_base,
        caps=caps,
    )
    cone.rebuild()
    assert cone._data == expected_data


@pytest.mark.parametrize(
    "vertex_a, vertex_b, vertex_c, color_a, color_b, color_c, expected_data",
    [
        (
            Point(1.0, 0.0, 0.0),
            Point(0.0, 1.0, 0.0),
            Point(0.0, 0.0, 1.0),
            "red",
            "green",
            "blue",
            [
                cgo.BEGIN,
                cgo.TRIANGLES,
                *Color("red").as_cgo,
                *Point(1.0, 0.0, 0.0).as_vertex,
                *Color("green").as_cgo,
                *Point(0.0, 1.0, 0.0).as_vertex,
                *Color("blue").as_cgo,
                *Point(0.0, 0.0, 1.0).as_vertex,
                cgo.END,
            ],
        ),
        (
            Point(2.0, 2.0, 2.0),
            Point(3.0, 3.0, 3.0),
            Point(4.0, 4.0, 4.0),
            "cyan",
            "magenta",
            "yellow",
            [
                cgo.BEGIN,
                cgo.TRIANGLES,
                *Color("cyan").as_cgo,
                *Point(2.0, 2.0, 2.0).as_vertex,
                *Color("magenta").as_cgo,
                *Point(3.0, 3.0, 3.0).as_vertex,
                *Color("yellow").as_cgo,
                *Point(4.0, 4.0, 4.0).as_vertex,
                cgo.END,
            ],
        ),
        (
            Point(-1.0, -1.0, -1.0),
            Point(0.0, 0.0, 0.0),
            Point(1.0, 1.0, 1.0),
            "white",
            "black",
            "gray",
            [
                cgo.BEGIN,
                cgo.TRIANGLES,
                *Color("white").as_cgo,
                *Point(-1.0, -1.0, -1.0).as_vertex,
                *Color("black").as_cgo,
                *Point(0.0, 0.0, 0.0).as_vertex,
                *Color("gray").as_cgo,
                *Point(1.0, 1.0, 1.0).as_vertex,
                cgo.END,
            ],
        ),
    ],
)
def test_triangle_simple_rebuild(vertex_a, vertex_b, vertex_c, color_a, color_b, color_c, expected_data):
    triangle = TriangleSimple(
        vertex_a=vertex_a, vertex_b=vertex_b, vertex_c=vertex_c, color_a=color_a, color_b=color_b, color_c=color_c
    )
    triangle.rebuild()
    assert triangle._data == expected_data


@pytest.mark.parametrize(
    "corner_a, corner_b, corner_c, corner_d, color_a, color_b, color_c, color_d, expected_data",
    [
        (
            Point(0.0, 0.0, 0.0),
            Point(1.0, 0.0, 0.0),
            Point(1.0, 1.0, 0.0),
            Point(0.0, 1.0, 0.0),
            "red",
            "green",
            "blue",
            "yellow",
            [
                cgo.BEGIN,
                cgo.TRIANGLES,
                *Color("red").as_cgo,
                *Point(0.0, 0.0, 0.0).as_vertex,
                *Color("green").as_cgo,
                *Point(1.0, 0.0, 0.0).as_vertex,
                *Color("blue").as_cgo,
                *Point(1.0, 1.0, 0.0).as_vertex,
                *Color("red").as_cgo,
                *Point(0.0, 0.0, 0.0).as_vertex,
                *Color("blue").as_cgo,
                *Point(1.0, 1.0, 0.0).as_vertex,
                *Color("yellow").as_cgo,
                *Point(0.0, 1.0, 0.0).as_vertex,
                cgo.END,
            ],
        ),
        (
            Point(1.0, 1.0, 1.0),
            Point(2.0, 1.0, 1.0),
            Point(2.0, 2.0, 1.0),
            Point(1.0, 2.0, 1.0),
            "cyan",
            "magenta",
            "yellow",
            "orange",
            [
                cgo.BEGIN,
                cgo.TRIANGLES,
                *Color("cyan").as_cgo,
                *Point(1.0, 1.0, 1.0).as_vertex,
                *Color("magenta").as_cgo,
                *Point(2.0, 1.0, 1.0).as_vertex,
                *Color("yellow").as_cgo,
                *Point(2.0, 2.0, 1.0).as_vertex,
                *Color("cyan").as_cgo,
                *Point(1.0, 1.0, 1.0).as_vertex,
                *Color("yellow").as_cgo,
                *Point(2.0, 2.0, 1.0).as_vertex,
                *Color("orange").as_cgo,
                *Point(1.0, 2.0, 1.0).as_vertex,
                cgo.END,
            ],
        ),
        (
            Point(-1.0, -1.0, -1.0),
            Point(0.0, -1.0, -1.0),
            Point(0.0, 0.0, -1.0),
            Point(-1.0, 0.0, -1.0),
            "white",
            "black",
            "gray",
            "purple",
            [
                cgo.BEGIN,
                cgo.TRIANGLES,
                *Color("white").as_cgo,
                *Point(-1.0, -1.0, -1.0).as_vertex,
                *Color("black").as_cgo,
                *Point(0.0, -1.0, -1.0).as_vertex,
                *Color("gray").as_cgo,
                *Point(0.0, 0.0, -1.0).as_vertex,
                *Color("white").as_cgo,
                *Point(-1.0, -1.0, -1.0).as_vertex,
                *Color("gray").as_cgo,
                *Point(0.0, 0.0, -1.0).as_vertex,
                *Color("purple").as_cgo,
                *Point(-1.0, 0.0, -1.0).as_vertex,
                cgo.END,
            ],
        ),
    ],
)
def test_square_rebuild(corner_a, corner_b, corner_c, corner_d, color_a, color_b, color_c, color_d, expected_data):
    square = Square(
        corner_a=corner_a,
        corner_b=corner_b,
        corner_c=corner_c,
        corner_d=corner_d,
        color_a=color_a,
        color_b=color_b,
        color_c=color_c,
        color_d=color_d,
    )
    square.rebuild()
    assert square._data == expected_data


@pytest.mark.parametrize(
    "width, color, points, line_type, expected_data",
    [
        (
            2.0,
            "red",
            [LineVertex(Point(0.0, 0.0, 0.0)), LineVertex(Point(1.0, 1.0, 1.0)), LineVertex(Point(2.0, 2.0, 2.0))],
            "LINE_STRIP",
            [cgo.LINEWIDTH, 2.0, *Color("red").as_cgo, cgo.BEGIN, cgo.LINE_STRIP]
            + [*Point(0.0, 0.0, 0.0).as_vertex]
            + [*Point(1.0, 1.0, 1.0).as_vertex]
            + [*Point(2.0, 2.0, 2.0).as_vertex]
            + [cgo.END],
        ),
        (
            1.5,
            "blue",
            [
                LineVertex(Point(0.0, 0.0, 0.0), color="green"),
                LineVertex(Point(1.0, 1.0, 1.0), color="yellow"),
                LineVertex(Point(2.0, 2.0, 2.0), color="golden"),
            ],
            "LINE_LOOP",
            [cgo.LINEWIDTH, 1.5, *Color("blue").as_cgo, cgo.BEGIN, cgo.LINE_LOOP]
            + [*Color("green").as_cgo, *Point(0.0, 0.0, 0.0).as_vertex]
            + [*Color("yellow").as_cgo, *Point(1.0, 1.0, 1.0).as_vertex]
            + [*Color("golden").as_cgo, *Point(2.0, 2.0, 2.0).as_vertex]
            + [cgo.END],
        ),
        (
            3.0,
            "green",
            [
                LineVertex(Point(0.0, 0.0, 0.0), color="yellow"),
                LineVertex(Point(1.0, 1.0, 1.0), width=4.0),
                LineVertex(Point(2.0, 2.0, 2.0)),
            ],
            "TRIANGLE_STRIP",
            [cgo.LINEWIDTH, 3.0, *Color("green").as_cgo, cgo.BEGIN, cgo.TRIANGLE_STRIP]
            + [*Color("yellow").as_cgo, *Point(0.0, 0.0, 0.0).as_vertex]
            + [cgo.LINEWIDTH, 4.0, *Point(1.0, 1.0, 1.0).as_vertex]
            + [*Point(2.0, 2.0, 2.0).as_vertex]
            + [cgo.END],
        ),
    ],
)
def test_poly_lines_rebuild(width, color, points, line_type, expected_data):
    poly_lines = PolyLines(width=width, color=color, points=points, line_type=line_type)
    poly_lines.rebuild()
    assert poly_lines._data == expected_data


@pytest.mark.parametrize(
    "start, point_to, radius, header_height, header_ratio, color_header, color_tail, expected_data",
    [
        (
            Point(0.0, 0.0, 0.0),
            Point(1.0, 0.0, 0.0),
            0.1,
            0.25,
            1.618,
            "red",
            "white",
            lambda start, point_to, radius, header_height, header_ratio, color_header, color_tail: GraphicObjectCollection(
                [
                    Cylinder(
                        start,
                        start + (point_to - start) * (1 - header_height / point_to.distance_to(start)),
                        radius,
                        color_tail,
                        color_tail,
                    ),
                    Cone(
                        point_to,
                        start + (point_to - start) * (1 - header_height / point_to.distance_to(start)),
                        0.0,
                        radius * header_ratio,
                        color_header,
                        color_header,
                        (1, 1),
                    ),
                ]
            ).data,
        ),
        (
            Point(1.0, 1.0, 1.0),
            Point(2.0, 2.0, 2.0),
            0.2,
            0.3,
            1.5,
            "blue",
            "green",
            lambda start, point_to, radius, header_height, header_ratio, color_header, color_tail: GraphicObjectCollection(
                [
                    Cylinder(
                        start,
                        start + (point_to - start) * (1 - header_height / point_to.distance_to(start)),
                        radius,
                        color_tail,
                        color_tail,
                    ),
                    Cone(
                        point_to,
                        start + (point_to - start) * (1 - header_height / point_to.distance_to(start)),
                        0.0,
                        radius * header_ratio,
                        color_header,
                        color_header,
                        (1, 1),
                    ),
                ]
            ).data,
        ),
        (
            Point(-1.0, -1.0, -1.0),
            Point(0.0, 0.0, 0.0),
            0.05,
            0.1,
            1.4,
            "yellow",
            "cyan",
            lambda start, point_to, radius, header_height, header_ratio, color_header, color_tail: GraphicObjectCollection(
                [
                    Cylinder(
                        start,
                        start + (point_to - start) * (1 - header_height / point_to.distance_to(start)),
                        radius,
                        color_tail,
                        color_tail,
                    ),
                    Cone(
                        point_to,
                        start + (point_to - start) * (1 - header_height / point_to.distance_to(start)),
                        0.0,
                        radius * header_ratio,
                        color_header,
                        color_header,
                        (1, 1),
                    ),
                ]
            ).data,
        ),
        (
            Point(2.0, 2.0, 2.0),
            Point(3.0, 3.0, 3.0),
            0.15,
            0.2,
            1.7,
            "magenta",
            "orange",
            lambda start, point_to, radius, header_height, header_ratio, color_header, color_tail: GraphicObjectCollection(
                [
                    Cylinder(
                        start,
                        start + (point_to - start) * (1 - header_height / point_to.distance_to(start)),
                        radius,
                        color_tail,
                        color_tail,
                    ),
                    Cone(
                        point_to,
                        start + (point_to - start) * (1 - header_height / point_to.distance_to(start)),
                        0.0,
                        radius * header_ratio,
                        color_header,
                        color_header,
                        (1, 1),
                    ),
                ]
            ).data,
        ),
    ],
)
def test_arrow_rebuild(start, point_to, radius, header_height, header_ratio, color_header, color_tail, expected_data):
    arrow = Arrow(
        start=start,
        point_to=point_to,
        radius=radius,
        header_height=header_height,
        header_ratio=header_ratio,
        color_header=color_header,
        color_tail=color_tail,
    )
    arrow.rebuild()
    expected = expected_data(start, point_to, radius, header_height, header_ratio, color_header, color_tail)

    assert np.allclose(arrow._data, expected, rtol=1e-05)


@pytest.mark.parametrize(
    "center, axis1, axis2, width, height, radius, color, line_width, steps, expected_data",
    [
        (
            Point(0.0, 0.0, 0.0),
            Point(1.0, 0.0, 0.0),
            Point(0.0, 1.0, 0.0),
            2.0,
            1.0,
            0.2,
            "red",
            2.0,
            50,
            lambda center, axis1, axis2, width, height, radius, color, line_width, steps: _build_rounded_rectangle_data(
                center, axis1, axis2, width, height, radius, color, line_width, steps
            ),
        ),
        (
            Point(1.0, 1.0, 1.0),
            Point(1.0, 0.0, 0.0),
            Point(0.0, 1.0, 0.0),
            3.0,
            2.0,
            0.3,
            "blue",
            1.5,
            50,
            lambda center, axis1, axis2, width, height, radius, color, line_width, steps: _build_rounded_rectangle_data(
                center, axis1, axis2, width, height, radius, color, line_width, steps
            ),
        ),
        (
            Point(-1.0, -1.0, -1.0),
            Point(1.0, 0.0, 0.0),
            Point(0.0, 1.0, 0.0),
            1.5,
            1.0,
            0.1,
            "green",
            2.5,
            50,
            lambda center, axis1, axis2, width, height, radius, color, line_width, steps: _build_rounded_rectangle_data(
                center, axis1, axis2, width, height, radius, color, line_width, steps
            ),
        ),
        (
            Point(2.0, 2.0, 2.0),
            Point(1.0, 0.0, 0.0),
            Point(0.0, 1.0, 0.0),
            4.0,
            3.0,
            0.4,
            "yellow",
            1.0,
            50,
            lambda center, axis1, axis2, width, height, radius, color, line_width, steps: _build_rounded_rectangle_data(
                center, axis1, axis2, width, height, radius, color, line_width, steps
            ),
        ),
    ],
)
def test_rounded_rectangle_rebuild(
    center, axis1, axis2, width, height, radius, color, line_width, steps, expected_data
):
    rounded_rectangle = RoundedRectangle(
        center=center,
        axis1=axis1,
        axis2=axis2,
        width=width,
        height=height,
        radius=radius,
        color=color,
        line_width=line_width,
        steps=steps,
    )
    rounded_rectangle.rebuild()
    expected = expected_data(center, axis1, axis2, width, height, radius, color, line_width, steps)
    assert rounded_rectangle._data == expected


def _build_rounded_rectangle_data(center, axis1, axis2, width, height, radius, color, line_width, steps):
    radius = min(width / 2, radius)
    half_w = width / 2
    half_h = height / 2
    r = radius
    k = 0.5522847498  # constant for approximating a quarter circle with a cubic Bezier

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

    def local_to_global(u, v):
        global_coord = center.array + u * axis1.array + v * axis2.array
        return Point(global_coord[0], global_coord[1], global_coord[2])

    bottom_right_corner = PseudoBezier(
        control_points=[
            local_to_global(*edge_bottom_end),
            local_to_global(*cp1_br),
            local_to_global(*cp2_br),
            local_to_global(*edge_right_start),
        ],
        color=color,
        steps=steps,
    )
    top_right_corner = PseudoBezier(
        control_points=[
            local_to_global(*edge_right_end),
            local_to_global(*cp1_tr),
            local_to_global(*cp2_tr),
            local_to_global(*edge_top_start),
        ],
        color=color,
        steps=steps,
    )
    top_left_corner = PseudoBezier(
        control_points=[
            local_to_global(*edge_top_end),
            local_to_global(*cp1_tl),
            local_to_global(*cp2_tl),
            local_to_global(*edge_left_start),
        ],
        color=color,
        steps=steps,
    )
    bottom_left_corner = PseudoBezier(
        control_points=[
            local_to_global(*edge_left_end),
            local_to_global(*cp1_bl),
            local_to_global(*cp2_bl),
            local_to_global(*edge_bottom_start),
        ],
        color=color,
        steps=steps,
    )

    vertices = [
        LineVertex(local_to_global(*edge_bottom_start)),
        LineVertex(local_to_global(*edge_bottom_end)),
        LineVertex(bottom_right_corner),
        LineVertex(local_to_global(*edge_right_end)),
        LineVertex(top_right_corner),
        LineVertex(local_to_global(*edge_top_end)),
        LineVertex(top_left_corner),
        LineVertex(local_to_global(*edge_left_end)),
        LineVertex(bottom_left_corner),
    ]

    poly = PolyLines(width=line_width, color=color, points=vertices, line_type="LINE_LOOP")
    poly.rebuild()
    return poly._data


@pytest.mark.parametrize(
    "center, axis1, axis2, major_radius, minor_radius, color, line_width, steps, expected_data",
    [
        (
            Point(0.0, 0.0, 0.0),
            Point(1.0, 0.0, 0.0),
            Point(0.0, 1.0, 0.0),
            2.0,
            1.0,
            "red",
            2.0,
            50,
            lambda center, axis1, axis2, major_radius, minor_radius, color, line_width, steps: _build_ellipse_data(
                center, axis1, axis2, major_radius, minor_radius, color, line_width, steps
            ),
        ),
        (
            Point(1.0, 1.0, 1.0),
            Point(1.0, 0.0, 0.0),
            Point(0.0, 1.0, 0.0),
            3.0,
            2.0,
            "blue",
            1.5,
            50,
            lambda center, axis1, axis2, major_radius, minor_radius, color, line_width, steps: _build_ellipse_data(
                center, axis1, axis2, major_radius, minor_radius, color, line_width, steps
            ),
        ),
        (
            Point(-1.0, -1.0, -1.0),
            Point(1.0, 0.0, 0.0),
            Point(0.0, 1.0, 0.0),
            1.5,
            0.5,
            "green",
            2.5,
            50,
            lambda center, axis1, axis2, major_radius, minor_radius, color, line_width, steps: _build_ellipse_data(
                center, axis1, axis2, major_radius, minor_radius, color, line_width, steps
            ),
        ),
        (
            Point(2.0, 2.0, 2.0),
            Point(1.0, 0.0, 0.0),
            Point(0.0, 1.0, 0.0),
            4.0,
            3.0,
            "yellow",
            1.0,
            50,
            lambda center, axis1, axis2, major_radius, minor_radius, color, line_width, steps: _build_ellipse_data(
                center, axis1, axis2, major_radius, minor_radius, color, line_width, steps
            ),
        ),
    ],
)
def test_ellipse_rebuild(center, axis1, axis2, major_radius, minor_radius, color, line_width, steps, expected_data):
    ellipse = Ellipse(
        center=center,
        axis1=axis1,
        axis2=axis2,
        major_radius=major_radius,
        minor_radius=minor_radius,
        color=color,
        line_width=line_width,
        steps=steps,
    )
    ellipse.rebuild()
    expected = expected_data(center, axis1, axis2, major_radius, minor_radius, color, line_width, steps)
    assert ellipse._data == expected


def _build_ellipse_data(center, axis1, axis2, major_radius, minor_radius, color, line_width, steps):
    t_values = np.linspace(0, 2 * math.pi, steps + 1)
    points = []

    def local_to_global(u, v):
        global_coord = center.array + u * axis1.array + v * axis2.array
        return Point(global_coord[0], global_coord[1], global_coord[2])

    for t in t_values:
        u = major_radius * math.cos(t)
        v = minor_radius * math.sin(t)
        points.append(local_to_global(u, v))

    vertices = [LineVertex(pt) for pt in points]
    poly = PolyLines(width=line_width, color=color, points=vertices, line_type="LINE_LOOP")
    poly.rebuild()
    return poly._data


@pytest.mark.parametrize(
    "objects, force_to_rebuild, expected_data",
    [
        # Test case 1: Single Sphere object, no force rebuild
        (
            [Sphere(center=Point(0.0, 0.0, 0.0), radius=1.0, color="red")],
            False,
            [
                *Color("red").as_cgo,
                cgo.SPHERE,
                0.0,
                0.0,
                0.0,
                1.0,
            ],
        ),
        # Test case 2: Multiple objects, force rebuild
        (
            [
                Sphere(center=Point(0.0, 0.0, 0.0), radius=1.0, color="red"),
                Sphere(center=Point(1.0, 1.0, 1.0), radius=2.0, color="blue"),
            ],
            True,
            [
                *Color("red").as_cgo,
                cgo.SPHERE,
                0.0,
                0.0,
                0.0,
                1.0,
                *Color("blue").as_cgo,
                cgo.SPHERE,
                1.0,
                1.0,
                1.0,
                2.0,
            ],
        ),
        # Test case 3: Empty collection
        ([], False, []),
        # Test case 4: Collection with one rebuilt object and one not rebuilt
        (
            [
                Sphere(center=Point(0.0, 0.0, 0.0), radius=1.0, color="green"),
                Sphere(center=Point(2.0, 2.0, 2.0), radius=3.0, color="yellow"),
            ],
            False,
            [
                *Color("green").as_cgo,
                cgo.SPHERE,
                0.0,
                0.0,
                0.0,
                1.0,
                *Color("yellow").as_cgo,
                cgo.SPHERE,
                2.0,
                2.0,
                2.0,
                3.0,
            ],
        ),
    ],
)
def test_graphic_object_collection_rebuild(objects, force_to_rebuild, expected_data):
    collection = GraphicObjectCollection(objects=objects, force_to_rebuild=force_to_rebuild)
    collection.rebuild()
    assert collection._data == expected_data


def test_easter_egg_rein():
    cmd.reinitialize()
    __easter_egg()
    cmd.refresh()

    objs = cmd.get_names()
    assert objs == ["APTX-4869"], "Easter egg should be added in blank session"

    cmd.reinitialize()


def test_easter_egg_busy():
    cmd.reinitialize()
    cmd.fetch("1SUO")
    cmd.refresh()

    __easter_egg()
    cmd.refresh()

    objs = cmd.get_names()
    assert objs == ["1SUO"]
    assert "APTX-4869" not in objs, "Easter egg should not be loaded when the session is busy"

    cmd.reinitialize()


def test_sphere_load():
    cmd.reinitialize()
    sphere = Sphere(center=Point(0, 0, 0), radius=10, color="cyan")
    sphere.load_as("mysphere")

    cyl = Cylinder()
    cyl.load_as("my_cyl")


def test_doughnut_load():
    cmd.reinitialize()
    Doughnut(samples=100).load_as("my_treasure")


def test_cone_load():
    cmd.reinitialize()
    for i, j in itertools.product(range(2), repeat=2):
        Cone(
            tip=Point(0, 0, 1.4),
            base_center=Point(0, 0, 0),
            radius_tip=0.5,
            radius_base=1.5,
            color_base="golden",
            color_tip="sand_brown",
            caps=(
                i,
                j,
            ),
        ).load_as(f"dyamond_{i},{j}")


def test_cube_load():
    cmd.reinitialize()

    Cube(wire_frame=True).load_as("a_colorful_cube")
    Cube(wire_frame=False).load_as("a_colorful_solid_cube")
    Cube(wire_frame=True, color_w="yellow", color_x="yellow", color_y="yellow", color_z="yellow").load_as(
        "a_yellow_box"
    )

    Cube(wire_frame=True, color_w="white", color_x="white", color_y="white", color_z="white").load_as("solid_box")

    Cube(wire_frame=True, color_w="black", color_x="black", color_y="black", color_z="black").load_as("a_black_box")


def test_square_load():
    cmd.reinitialize()
    Square().load_as("a_square")


def test_polylines_load():
    cmd.reinitialize()

    PolyLines(
        2.0,
        "yellow",
        [
            LineVertex(Point(0, 0, 0)),
            LineVertex(Point(0, 0, 1)),
            LineVertex(Point(0, 1, 0)),
            LineVertex(Point(1, 0, 0)),
            LineVertex(Point(1, 1, 2)),
        ],
    ).load_as("yellow_line_strip")

    PolyLines(
        2.0,
        "red",
        [
            LineVertex(Point(0, 0, 0)),
            LineVertex(Point(0, 0, 1)),
            LineVertex(Point(0, 1, 0)),
            LineVertex(Point(1, 0, 0)),
            LineVertex(Point(1, 1, 2)),
        ],
        line_type="LINE_LOOP",
    ).load_as("red_line_loop")

    PolyLines(
        2.0,
        "cyan",
        [
            LineVertex(Point(0, 0, 0)),
            LineVertex(Point(0, 0, 1)),
            LineVertex(Point(0, 1, 0)),
        ],
        line_type="TRIANGLE_STRIP",
    ).load_as("cyan_trangle_shape")

    PolyLines(
        2.0,
        "violet",
        [
            LineVertex(Point(0, 0, 0)),
            LineVertex(Point(0, 1, 0)),
            LineVertex(Point(1, 0, 0)),
            LineVertex(Point(1, 1, 0)),
        ],
        line_type="TRIANGLE_STRIP",
    ).load_as("violet_square_shape")
    PolyLines(
        2.0,
        "pink",
        [  # continous triangles
            LineVertex(Point(0, 0, 0)),  # -\  triangle # 1
            LineVertex(Point(0, 1, 0)),  # |-'  -\  triangle # 2
            LineVertex(Point(1, 1, 0)),  # -/       |-'  -\  triangle # 3
            LineVertex(Point(1, 0, 0)),  # -/       |-'
            LineVertex(Point(1, 1, 1)),  # -/
        ],
        line_type="TRIANGLE_STRIP",
    ).load_as("pink_3_tri_shape")

    PolyLines(
        2.0,
        "white",
        LineVertex.from_points(
            (Point(0, 1, 0), Point(1, 2, 0), Point(2, 3, 0), Point(0, 0.5, 0), Point(-0.3, 0.5, 0), Point(0, 0, 0))
        ),
        line_type="TRIANGLE_FAN",
    ).load_as("white_square_fan")

    PolyLines(
        2.0,
        "white",
        LineVertex.from_points((Point(0, 1, 0), Point(1, 1, 0), Point(1, 0, 0), Point(0, 0, 0))),
        line_type="LINE_LOOP",
    ).load_as("white_square")

    PolyLines(
        2.0,
        "golden",
        [
            LineVertex(Point(-1, 1, 0)),  # left top
            LineVertex(Point(0, 0, 1.4)),  # tip
            LineVertex(Point(1, 1, 0)),  # right top
            LineVertex(Point(1, -1, 0)),  # right bottom
            LineVertex(Point(0, 0, 1.4)),  # tip again
            LineVertex(Point(-1, -1, 0)),  # left bottom
            LineVertex(Point(-1, 1, 0)),  # left top back
        ],
        line_type="TRIANGLE_STRIP",
    ).load_as("pyramid")

    PolyLines(
        4.0,
        "white",
        [
            LineVertex(Point(-1, 1, 0)),
            LineVertex(Point(0, 0, 1.4)),
            LineVertex(Point(1, 1, 0)),
            LineVertex(Point(1, -1, 0)),
            LineVertex(Point(0, 0, 1.4)),
            LineVertex(Point(-1, -1, 0)),
            LineVertex(Point(-1, 1, 0)),
        ],
        line_type="LINE_LOOP",
    ).load_as("pyramid_curve")


def test_sausage_load():
    cmd.reinitialize()
    Sausage(p1=Point(0, 0, 1), p2=Point(0, 0, 2), radius=0.5, color_1="red", color_2="white").load_as("tasty_sausage")


def test_arrow_load():
    cmd.reinitialize()

    Arrow(Point(1, 2, 3), Point(4, 5, 7), 0.5, 2).load_as("my_arrow")

    Arrow(Point(0, 0, 0), Point(4, 5, 7), 0.5, 2).load_as("my_zero_arrow")

    Arrow(Point(4, 5, 7), Point(10, 2, 3), 0.5, 4, 2).load_as("my_spike")


def test_rect_load():
    cmd.reinitialize()

    # Create a 3D rounded rectangle with specified parameters
    rounded_rect = RoundedRectangle(
        center=Point(0, 0, 0),
        axis1=Point(1, 0, 0),  # Local X-axis,
        axis2=Point(0, 1, 0),  # Local Y-axis,
        width=5,
        height=5,
        radius=3,
        color="green",
        line_width=3,
        steps=20,  # Increase for smoother rounded corners
    )

    # Rebuild the object to compute its CGO data
    rounded_rect.rebuild()
    rounded_rect.load_as("rounded_rect_rounder")


def test_ellipse_load():
    cmd.reinitialize()
    ellipse = Ellipse(
        center=Point(0, 0, 0),
        axis1=Point(1, 2, 3),  # Local X-axis (major axis direction)
        axis2=Point(3, 1, -1),  # Local Y-axis,
        major_radius=5,
        minor_radius=2,
        color="blue",
        line_width=2,
        steps=50,  # More steps for smoother ellipse
    )
    ellipse.load_as("my_ellipse")
    cmd.reinitialize()


def test_ellispsoid():
    cmd.reinitialize()

    ellipsoid = Ellipsoid(
        center=Point(0, 0, 0), radius_x=1, radius_y=1, radius_z=1, color="green", steps_theta=20, steps_phi=30
    )
    ellipsoid.load_as("my_ellispsoid")
    cmd.reinitialize()


def test_polygon():
    cmd.reinitialize()
    vertices = [Point(0, 0, 0), Point(1, 0, 0), Point(1.5, 1, 0), Point(0.5, 1.5, 0), Point(-0.5, 1, 0)]
    poly = Polygon(vertices=vertices, color="red")
    poly.rebuild()
    poly.load_as("my_polygon")
    cmd.reinitialize()


def test_polyhedron():
    cmd.reinitialize()
    # Define the vertices of a cube.
    vertices = [
        Point(-1, -1, -1),  # 0
        Point(1, -1, -1),  # 1
        Point(1, 1, -1),  # 2
        Point(-1, 1, -1),  # 3
        Point(-1, -1, 1),  # 4
        Point(1, -1, 1),  # 5
        Point(1, 1, 1),  # 6
        Point(-1, 1, 1),  # 7
    ]
    # Define the faces of the cube (each face as a list of vertex indices).
    faces = [
        [0, 1, 2, 3],  # bottom face
        [4, 5, 6, 7],  # top face
        [0, 1, 5, 4],  # front face
        [1, 2, 6, 5],  # right face
        [2, 3, 7, 6],  # back face
        [3, 0, 4, 7],  # left face
    ]
    # Create the polyhedron with a cyan color.
    cube = Polyhedron(vertices=vertices, faces=faces, color="cyan")
    cube.rebuild()
    cube.load_as("my_polyhedron")
    cmd.reinitialize()


@pytest.fixture
def ensure_font_file():
    import pooch

    return pooch.retrieve(
        url="https://nutshell-api.yaoyy.moe/simhei.ttf",
        known_hash="md5:1054d571c8a003c497366a95c11b5760",
        fname="simhei.ttf",
        path="../tests/data/",
    )


def test_text_cgo(ensure_font_file):
    cmd.reinitialize()
    text = "Detective Conan\n\nSilver Bullet\n\nCool Kid"

    TextBoard(text=text, font_path=ensure_font_file, width=1.5, space=10).load_as("silver_bullet")

    cmd.reinitialize()
