import numpy as np
from REvoDesign.tools.cgo_utils import Point, Color, not_none_float, __easter_egg, GraphicObject, PseudoCurve, PseudoBezier, LineVertex, Sphere, Cylinder, Sausage, Square, TriangleSimple, Doughnut,Cone, Triangle, Line, Lines, PolyLines, Cube,Arrow,  RoundedRectangle, Ellipse, GraphicObjectCollection,COLOR_TABLES
import pytest
from unittest.mock import MagicMock, patch

from pymol import cgo


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
    ]
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

@pytest.mark.parametrize("point, x, y, z", [
    (Point(1, 2, 3), 4, 5, 6),
    (Point(-1, -2, -3), 1, 2, 3),
    (Point(0, 0, 0), 1, 1, 1),
    (Point(1, 2, 3), None, None, None),
])
def test_move(point, x, y, z):
    result = point.move(x, y, z)
    expected_x = x if x is not None else point.x
    expected_y = y if y is not None else point.y
    expected_z = z if z is not None else point.z
    expected = Point(expected_x, expected_y, expected_z)
    assert result == expected

@pytest.mark.parametrize("points", [
    [Point(1, 2, 3), Point(4, 5, 6)],
    [Point(-1, -2, -3), Point(1, 2, 3)],
    [Point(0, 0, 0), Point(1, 1, 1)],
])
def test_as_arrays(points):
    result = Point.as_arrays(points)
    expected = np.concatenate([point.array for point in points])
    assert np.array_equal(result, expected)

@pytest.mark.parametrize("points", [
    [Point(1, 2, 3), Point(4, 5, 6)],
    [Point(-1, -2, -3), Point(1, 2, 3)],
    [Point(0, 0, 0), Point(1, 1, 1)],
])
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
    ]
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
    ]
)
def test_color_array_alpha(color_name, alpha, expected_rgba):
    color = Color(name=color_name, alpha=alpha)
    assert np.allclose(color.array_alpha, expected_rgba, rtol=1e-2)

@pytest.mark.parametrize(
    "colors, expected_cgos",
    [
        (
            [Color("r", 1.0), Color("b", 0.5)],
            np.concatenate([
                np.array([cgo.ALPHA,1.0, cgo.COLOR, 1.0, 0.0, 0.0]),
                np.array([cgo.ALPHA,0.5, cgo.COLOR, 0.0, 0.0, 1.0])
            ])
        ),
        (
            [Color("g", 0.75), Color("white", 1.0)],
            np.concatenate([
                np.array([cgo.ALPHA,0.75, cgo.COLOR, 0.0, 0.5, 0.0]),
                np.array([cgo.ALPHA, 1.0, cgo.COLOR, 1.0, 1.0, 1.0])
            ])
        )
    ]
)
def test_color_as_cgos(colors, expected_cgos):
    result = Color.as_cgos(colors)
    assert np.allclose(result, expected_cgos, rtol=1e-2)



@pytest.mark.parametrize(
    "name, debug_points, expected_call_args",
    [
        ("object1", False, ("object1",)),
        ("object2", True, ("object2",)),
    ]
)
def test_load_as(name, debug_points, expected_call_args):
    with patch('REvoDesign.tools.cgo_utils.cmd') as mock_cmd:
        mock_cmd.get_names.return_value = [name]
        graphic_object = GraphicObject()
        graphic_object._data = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]

        graphic_object.load_as(name, debug_points)

        mock_cmd.delete.assert_called_once_with(name)
        mock_cmd.load_cgo.assert_called_once_with(graphic_object.data, *expected_call_args)

@pytest.mark.parametrize(
    "name, debug_points, existing_names, expected_delete_calls",
    [
        ("object1", False, ["object1"], 1),
        ("object2", True, ["object2"], 1),
        ("object3", False, [], 0),
    ]
)
def test_load_as_delete_calls(name, debug_points, existing_names, expected_delete_calls):
    with patch('REvoDesign.tools.cgo_utils.cmd') as mock_cmd:
        mock_cmd.get_names.return_value = existing_names
        graphic_object = GraphicObject()
        graphic_object._data = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]

        graphic_object.load_as(name, debug_points)

        assert mock_cmd.delete.call_count == expected_delete_calls
        mock_cmd.load_cgo.assert_called_once_with(graphic_object.data, name)



@pytest.mark.parametrize(
    "control_points, color, steps, expected_vertices",
    [
        ([Point(0, 0, 0), Point(1, 1, 1)], "r", 2, [Point(0, 0, 0), Point(1, 1, 1)]),
        ([Point(0, 0, 0), Point(1, 1, 1), Point(2, 2, 2)], "b", 3, [Point(0, 0, 0), Point(1, 1, 1), Point(2, 2, 2)]),
    ]
)
def test_rebuild(control_points, color, steps, expected_vertices):
    with patch.object(PseudoCurve, 'sample', return_value=expected_vertices):
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
    ]
)
def test_check_control_points(control_points, num_min, num_max, expected_exception):
    with patch.object(PseudoCurve, 'sample', return_value=control_points):
        pseudo_curve = PseudoCurve(control_points=control_points)
        if expected_exception:
            with pytest.raises(expected_exception):
                pseudo_curve.check_control_points(num_min=num_min, num_max=num_max)
        else:
            pseudo_curve.check_control_points(num_min=num_min, num_max=num_max)


