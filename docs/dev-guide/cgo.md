# CGO — Compiled Graphics Objects

CGO (Compiled Graphics Objects) is PyMOL's low-level drawing API. It produces
OpenGL primitives — lines, spheres, cylinders, cones, text — as flat lists of
floats that PyMOL renders as custom visual objects. REvoDesign wraps this in a
high-level Python API (`REvoDesign.tools.cgo_utils`) for programmatic 3D
graphics.

## Why CGO?

CGO objects are rendered as PyMOL objects — you can zoom, rotate, clip, and
color them like any molecule. They're used throughout REvoDesign for:

- **GREMLIN co-evolution edges** — cylinders connecting residue pairs
- **QButtonMatrix** — interactive residue grids in the GUI
- **Axes, arrows, and annotations** — 3D visual aids in PyMOL
- **Text boards and labels** — protein annotations in the viewer

## Two Ways to Use CGO

### 1. Raw CGO (PyMOL primitives)

Build a list of floats using `pymol.cgo` constants and pass to `cmd.load_cgo()`:

```python
from pymol.cgo import *
from pymol import cmd

obj = [
    LINEWIDTH, 3.0,
    BEGIN, LINES,
    COLOR,   1.0, 0.0, 0.0,   # red
    VERTEX,  0.0, 0.0, 0.0,   # from origin
    VERTEX,  5.0, 0.0, 0.0,   # to (5, 0, 0)
    COLOR,   0.0, 0.0, 1.0,   # blue
    VERTEX,  0.0, 0.0, 0.0,
    VERTEX,  0.0, 5.0, 0.0,   # to (0, 5, 0)
    END
]
cmd.load_cgo(obj, 'my_axes')
```

This is precise but verbose and error-prone — every value is a magic float.

### 2. REvoDesign `cgo_utils` (high-level API)

Use dataclass-based primitives that generate CGO floats internally:

```python
from REvoDesign.tools.cgo_utils import Point, Color, Sphere, Cylinder, Arrow
from pymol import cmd

# Build objects
sphere = Sphere(center=Point(0, 0, 0), radius=2.0, color='red')
cyl = Cylinder(Point(0, 0, 0), Point(5, 0, 0), radius=0.5,
               color1='red', color2='blue')

# Load into PyMOL
sphere.load_as('my_sphere')
cyl.load_as('my_cylinder')
```

The class's `rebuild()` method constructs the raw float list; `load_as(name)`
deletes any existing object with that name and calls `cmd.load_cgo()`.

## CGO Primitives Reference

These are the raw `pymol.cgo` constants. Each is a float. Primitives that
take arguments read the next N floats from the list.

### Structure Directives

| Constant | Value | Purpose |
|----------|-------|---------|
| `BEGIN` | 2.0 | Start a drawing group — followed by a primitive type |
| `END` | 3.0 | End the current drawing group |
| `STOP` | 0.0 | Terminate the CGO list |
| `NULL` | 1.0 | No-op placeholder |

### Drawing Primitives (used with `BEGIN`/`END`)

| Constant | Value | Draws |
|----------|-------|-------|
| `POINTS` | 0.0 | Individual dots at each `VERTEX` |
| `LINES` | 1.0 | Pairs of vertices as separate line segments |
| `LINE_LOOP` | 2.0 | Connected line loop (closes back to first) |
| `LINE_STRIP` | 3.0 | Connected line strip (no closure) |
| `TRIANGLES` | 4.0 | Groups of 3 vertices as triangles |
| `TRIANGLE_STRIP` | 5.0 | Strip of connected triangles |
| `TRIANGLE_FAN` | 6.0 | Fan of triangles from first vertex |

### Vertex and Appearance

```
VERTEX,  x, y, z          — position (used inside BEGIN/END)
COLOR,   r, g, b          — RGB color (0.0–1.0 per channel)
NORMAL,  nx, ny, nz       — surface normal for lighting
LINEWIDTH, w              — line thickness (GL renderer: before BEGIN only)
DOTWIDTH, w               — point diameter (raytracer)
WIDTHSCALE, s             — point zoom-scaling for raytracer
```

### Standalone Primitives (no `BEGIN`/`END` needed)

```
SPHERE,  x, y, z, radius
CYLINDER, x1,y1,z1, x2,y2,z2, radius, r1,g1,b1, r2,g2,b2
CONE,     x1,y1,z1, x2,y2,z2, r1,r2, r1,g1,b1, r2,g2,b2, cap1,cap2
SAUSAGE,  x1,y1,z1, x2,y2,z2, radius, r,g,b, r,g,b  (like cylinder, single color pair)
TRIANGLE, x1,y1,z1, x2,y2,z2, x3,y3,z3,
          nx1,ny1,nz1, nx2,ny2,nz2, nx3,ny3,nz3,
          r1,g1,b1, r2,g2,b2, r3,g3,b3
ALPHA_TRIANGLE — triangle with alpha blending
ELLIPSOID, x1,y1,z1, x2,y2,z2, radius1,radius2  (two focal points)
```

### Lighting

```
LIGHTING, flag    — 0x0B50 (global lighting toggle)
ALPHA, value      — global alpha transparency
```

### Text (raw CGO)

```
FONT,      font_id    — select font (5 = plain, 7 = serif, etc.)
FONT_SCALE, scale     — text size multiplier
FONT_VERTEX, x,y,z    — text anchor position
FONT_AXES,  x1,y1,z1, x2,y2,z2  — text orientation axes
CHAR, char_code       — single character (ASCII int)
```

## Examples: Raw CGO

### Multi-color line strip

```python
from pymol.cgo import *
from pymol import cmd

obj = [BEGIN, LINE_STRIP]
for i in range(10):
    y = 1.0 if i % 2 == 0 else -1.0
    obj.extend([COLOR, (i+1)/10.0, (i+1)/10.0, 0.0])
    obj.extend([VERTEX, float(i), y, 0.0])
obj.append(END)
cmd.load_cgo(obj, 'zigzag')
```

### Coordinate axes with cones

```python
from pymol.cgo import *
from pymol import cmd

w, l, h = 0.06, 0.75, 0.25
d = w * 1.618

axes = [
    CYLINDER, 0,0,0, l,0,0, w,  1,0,0, 1,0,0,    # X axis: red
    CYLINDER, 0,0,0, 0,l,0, w,  0,1,0, 0,1,0,    # Y axis: green
    CYLINDER, 0,0,0, 0,0,l, w,  0,0,1, 0,0,1,    # Z axis: blue
    CONE, l,0,0, h+l,0,0, d,0,  1,0,0, 1,0,0, 1,1,
    CONE, 0,l,0, 0,h+l,0, d,0,  0,1,0, 0,1,0, 1,1,
    CONE, 0,0,l, 0,0,h+l, d,0,  0,0,1, 0,0,1, 1,1,
]
cmd.load_cgo(axes, 'axes')
```

## REvoDesign `cgo_utils` API

The `REvoDesign.tools.cgo_utils` module provides typed, composable primitives.
All inherit from `GraphicObject`.

### Point and Color

```python
from REvoDesign.tools.cgo_utils import Point, Color

p = Point(1.0, 2.0, 3.0)
p.array           # np.array([1., 2., 3.])
p.as_vertex       # [VERTEX, 1.0, 2.0, 3.0]
p + p             # Point(2.0, 4.0, 6.0)
p * 2             # Point(2.0, 4.0, 6.0)

Point.dot(a, b)   # dot product
Point.cross(a, b) # cross product
Point.from_array(np.array([1,2,3]))  # from numpy

c = Color('red')
c.as_cgo          # [COLOR, 1.0, 0.0, 0.0]
c.hex             # '#ff0000'
Color.from_cgo([COLOR, 0.0, 1.0, 0.0])  # from raw CGO
```

Available color tables: `BASE_COLORS`, `TABLEAU_COLORS`, `CSS4_COLORS`, `XKCD_COLORS`.

### Shapes

```python
from REvoDesign.tools.cgo_utils import Sphere, Cylinder, Cone, Arrow, Sausage, Doughnut

# Sphere at (1,2,3) with radius 2.0
Sphere(Point(1, 2, 3), radius=2.0, color='red').load_as('s')

# Cylinder from A to B with per-endpoint colors
Cylinder(Point(0,0,0), Point(5,0,0), radius=0.5,
         color1='red', color2='blue').load_as('cyl')

# Arrow (cylinder + cone tip)
Arrow(Point(0,0,0), Point(5,0,0), shaft_radius=0.3,
      head_radius=0.8, head_length=1.2, color='green').load_as('arrow')

# Torus (doughnut) at origin, R=3, r=1
Doughnut(center=Point(0,0,0), major_radius=3.0, minor_radius=1.0,
         color='yellow').load_as('torus')
```

### Polygons and Solids

```python
from REvoDesign.tools.cgo_utils import (
    Triangle, TriangleSimple, Cube, Square, Polygon, Polyhedron,
    Ellipse, Ellipsoid, RoundedRectangle,
)
```

### PolyLines

Draws connected line segments through a list of points:

```python
from REvoDesign.tools.cgo_utils import PolyLines, Point

points = [Point(i, i % 2, 0) for i in range(10)]
PolyLines(points, color='cyan', linewidth=3.0).load_as('zigzag')
```

### Curves

```python
from REvoDesign.tools.cgo_utils import (
    PseudoBezier, PseudoCatmullRom, PseudoBSpline,
    PseudoHermite, PseudoArc, PseudoNURBS,
)

# Bézier with 4 control points
ctrl = [Point(0,0,0), Point(2,3,0), Point(4,-1,0), Point(6,2,0)]
bezier = PseudoBezier(ctrl, color='orange', steps=100)
bezier.load_as('bezier_curve')
```

All curves inherit from `PseudoCurve(GraphicObject)` and share the pattern:
`control_points` + `color` + `steps` → `sample()` → `rebuild()` → `load_as()`.

### Text

```python
from REvoDesign.tools.cgo_utils import TextBoard, Point

TextBoard("Hello REvoDesign", position=Point(0, 0, 0),
          color='white', scale=1.0).load_as('label')
```

### GraphicObjectCollection

Combine multiple objects into one:

```python
from REvoDesign.tools.cgo_utils import GraphicObjectCollection

collection = GraphicObjectCollection([
    Sphere(Point(0,0,0), 1.0, 'red'),
    Sphere(Point(3,0,0), 0.5, 'blue'),
    Cylinder(Point(0,0,0), Point(3,0,0), 0.2, 'white', 'white'),
])
collection.load_as('dumbbell')
```

## Pattern: Build, Rebuild, Load

Every `GraphicObject` follows this lifecycle:

```
__init__()          # store typed parameters
  → __post_init__() # call rebuild()
    → rebuild()     # set self._data = [<raw CGO floats>]
      → load_as()   # cmd.delete(name) + cmd.load_cgo(self.data, name)
```

Override `rebuild()` to generate custom CGO:

```python
@dataclass
class Cross(GraphicObject):
    center: Point = Point(0, 0, 0)
    size: float = 1.0
    color: str = 'white'

    def rebuild(self):
        c = self.center
        s = self.size / 2
        self._data = [
            *Color(self.color).as_cgo,
            cgo.BEGIN, cgo.LINES,
            cgo.VERTEX, c.x-s, c.y,   c.z,
            cgo.VERTEX, c.x+s, c.y,   c.z,
            cgo.VERTEX, c.x,   c.y-s, c.z,
            cgo.VERTEX, c.x,   c.y+s, c.z,
            cgo.END,
        ]

Cross(Point(5,5,0), size=4.0, color='yellow').load_as('my_cross')
```

## Color System

`Color(name)` resolves named colors from four tables searched in order:

1. `BASE_COLORS` — matplotlib base (r, g, b, c, m, y, k, w)
2. `TABLEAU_COLORS` — `tab:blue`, `tab:orange`, etc.
3. `CSS4_COLORS` — all 148 CSS4 named colors
4. `XKCD_COLORS` — 949 crowd-sourced color names (e.g., `xkcd:burnt_sienna`)

```python
Color('red').array       # (1.0, 0.0, 0.0)
Color('tab:blue').hex    # '#1f77b4'
Color('#ff0000').as_cgo  # [COLOR, 1.0, 0.0, 0.0]
```

## Common Pitfalls

1. **LINEWIDTH position**: The GL renderer only honors `LINEWIDTH` before
   `BEGIN`. The raytracer honors it anywhere (even between vertices). For
   consistent results, place line widths before `BEGIN`.

2. **Duplicate names**: `load_as(name)` deletes any existing PyMOL object
   with that name before loading. This avoids the "name already exists" error
   but means you can't have two CGO objects with the same name.

3. **Points render differently**: Points are squares in the interactive GL
   viewport but rendered as spheres in ray-traced images. Use `DOTWIDTH` +
   `WIDTHSCALE` for consistent appearance.

4. **Color interpolation**: Between a `BEGIN`/`END` block, color changes
   between vertices are linearly interpolated — useful for gradients. For
   solid-color segments, set the same color for both endpoints.

5. **No CGO object updates**: To modify a CGO object after loading, delete
   it (`cmd.delete(name)`) and reload with updated data. There is no
   in-place update mechanism.

## API Reference

Full class listing at [Tools API Reference](../api/tools.md) — see the CGO
Utilities section for `Point`, `Color`, `GraphicObject`, and all shape/curve
classes.
