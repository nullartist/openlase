"""
OpenLase Web - Laser Renderer

This module provides laser rendering functionality similar to libol.c,
but designed for the web interface and Helios DAC output.

Copyright (C) 2024

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 2.1 or version 3.
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional, Callable
from .helios_output import LaserPoint, normalize_to_helios, color_to_rgb

# Constants
SMALL_Z = 0.00001  # Small Z value to avoid division by zero
DEFAULT_FLATNESS = 0.00001  # Default flatness for bezier curves
DEFAULT_SNAP = 0.00001  # Default snap distance


@dataclass
class RenderParams:
    """Rendering parameters for laser output."""
    rate: int = 30000  # Points per second
    on_speed: float = 0.02  # Line drawing speed
    off_speed: float = 0.05  # Blanking travel speed
    start_wait: int = 8  # Wait points at start
    start_dwell: int = 3  # Dwell points at start of line
    curve_dwell: int = 0  # Dwell at curves
    corner_dwell: int = 6  # Dwell at corners
    end_dwell: int = 3  # Dwell at end of line
    end_wait: int = 7  # Wait points at end
    curve_angle: float = 0.866  # cos(30 degrees)
    flatness: float = DEFAULT_FLATNESS
    snap: float = DEFAULT_SNAP
    render_flags: int = 0


@dataclass
class Point:
    """Internal point representation."""
    x: float
    y: float
    z: float = 0.0
    color: int = 0xFFFFFF


@dataclass
class Object:
    """A drawable object consisting of points."""
    points: List[Point] = field(default_factory=list)
    bbox: List[List[float]] = field(default_factory=lambda: [[-1, -1], [1, 1]])


class LaserRenderer:
    """
    Laser renderer that converts drawing commands to laser points.
    Similar to libol functionality but in pure Python.
    """

    # Primitive types
    LINESTRIP = 0
    BEZIERSTRIP = 1
    POINTS = 2

    # Colors
    C_RED = 0xFF0000
    C_GREEN = 0x00FF00
    C_BLUE = 0x0000FF
    C_WHITE = 0xFFFFFF
    C_BLACK = 0x000000

    def __init__(self, params: Optional[RenderParams] = None):
        self.params = params or RenderParams()
        self.objects: List[Object] = []
        self.current_object: Optional[Object] = None
        self.primitive = self.LINESTRIP
        self.points_count = 0

        # Matrix stack for 2D transformations
        self.mtx2d = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        self.mtx2d_stack = []

        # Matrix stack for 3D transformations
        self.mtx3d = [
            [1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ]
        self.mtx3d_stack = []

        # Color stack
        self.current_color = self.C_WHITE
        self.color_stack = []

        # Drawing state
        self.last_point = Point(0, 0, 0, 0)
        self.last_slope = Point(0, 0, 0, 0)
        self.bezier_state = 0
        self.bezier_c1 = Point(0, 0)
        self.bezier_c2 = Point(0, 0)

    def reset(self):
        """Reset the renderer state."""
        self.objects = []
        self.current_object = None
        self.load_identity()
        self.load_identity_3()
        self.reset_color()

    def load_identity(self):
        """Load identity 2D matrix."""
        self.mtx2d = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]

    def push_matrix(self):
        """Push 2D matrix onto stack."""
        self.mtx2d_stack.append([row[:] for row in self.mtx2d])

    def pop_matrix(self):
        """Pop 2D matrix from stack."""
        if self.mtx2d_stack:
            self.mtx2d = self.mtx2d_stack.pop()

    def mult_matrix(self, m: List[float]):
        """Multiply 2D matrix."""
        if len(m) == 9:
            m = [m[0:3], m[3:6], m[6:9]]
        new = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
        for i in range(3):
            for j in range(3):
                for k in range(3):
                    new[i][j] += self.mtx2d[i][k] * m[k][j]
        self.mtx2d = new

    def rotate(self, theta: float):
        """Rotate 2D by theta radians."""
        c, s = math.cos(theta), math.sin(theta)
        self.mult_matrix([c, -s, 0, s, c, 0, 0, 0, 1])

    def translate(self, x: float, y: float):
        """Translate 2D."""
        self.mult_matrix([1, 0, 0, 0, 1, 0, x, y, 1])

    def scale(self, sx: float, sy: float):
        """Scale 2D."""
        self.mult_matrix([sx, 0, 0, 0, sy, 0, 0, 0, 1])

    def load_identity_3(self):
        """Load identity 3D matrix."""
        self.mtx3d = [
            [1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ]

    def push_matrix_3(self):
        """Push 3D matrix onto stack."""
        self.mtx3d_stack.append([row[:] for row in self.mtx3d])

    def pop_matrix_3(self):
        """Pop 3D matrix from stack."""
        if self.mtx3d_stack:
            self.mtx3d = self.mtx3d_stack.pop()

    def mult_matrix_3(self, m: List[float]):
        """Multiply 3D matrix."""
        if len(m) == 16:
            m = [m[0:4], m[4:8], m[8:12], m[12:16]]
        new = [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
        for i in range(4):
            for j in range(4):
                for k in range(4):
                    new[i][j] += self.mtx3d[i][k] * m[k][j]
        self.mtx3d = new

    def rotate_3x(self, theta: float):
        """Rotate around X axis."""
        c, s = math.cos(theta), math.sin(theta)
        self.mult_matrix_3([
            1, 0, 0, 0,
            0, c, s, 0,
            0, -s, c, 0,
            0, 0, 0, 1
        ])

    def rotate_3y(self, theta: float):
        """Rotate around Y axis."""
        c, s = math.cos(theta), math.sin(theta)
        self.mult_matrix_3([
            c, 0, -s, 0,
            0, 1, 0, 0,
            s, 0, c, 0,
            0, 0, 0, 1
        ])

    def rotate_3z(self, theta: float):
        """Rotate around Z axis."""
        c, s = math.cos(theta), math.sin(theta)
        self.mult_matrix_3([
            c, s, 0, 0,
            -s, c, 0, 0,
            0, 0, 1, 0,
            0, 0, 0, 1
        ])

    def translate_3(self, x: float, y: float, z: float):
        """Translate 3D."""
        self.mult_matrix_3([
            1, 0, 0, 0,
            0, 1, 0, 0,
            0, 0, 1, 0,
            x, y, z, 1
        ])

    def scale_3(self, sx: float, sy: float, sz: float):
        """Scale 3D."""
        self.mult_matrix_3([
            sx, 0, 0, 0,
            0, sy, 0, 0,
            0, 0, sz, 0,
            0, 0, 0, 1
        ])

    def perspective(self, fovy: float, aspect: float, z_near: float, z_far: float):
        """Set up perspective projection."""
        ymax = z_near * math.tan(fovy * math.pi / 360.0)
        ymin = -ymax
        xmin = ymin * aspect
        xmax = ymax * aspect
        self.frustum(xmin, xmax, ymin, ymax, z_near, z_far)

    def frustum(self, left: float, right: float, bottom: float, top: float,
                near: float, far: float):
        """Set up frustum projection."""
        m = [
            (2 * near) / (right - left), 0, 0, 0,
            0, (2 * near) / (top - bottom), 0, 0,
            (right + left) / (right - left), (top + bottom) / (top - bottom),
            -(far + near) / (far - near), -1,
            0, 0, (-2 * far * near) / (far - near), 0
        ]
        self.mult_matrix_3(m)

    def reset_color(self):
        """Reset to white color."""
        self.current_color = self.C_WHITE

    def mult_color(self, color: int):
        """Multiply current color."""
        r1 = (self.current_color >> 16) & 0xFF
        g1 = (self.current_color >> 8) & 0xFF
        b1 = self.current_color & 0xFF
        r2 = (color >> 16) & 0xFF
        g2 = (color >> 8) & 0xFF
        b2 = color & 0xFF
        r = (r1 * r2) // 255
        g = (g1 * g2) // 255
        b = (b1 * b2) // 255
        self.current_color = (r << 16) | (g << 8) | b

    def push_color(self):
        """Push color onto stack."""
        self.color_stack.append(self.current_color)

    def pop_color(self):
        """Pop color from stack."""
        if self.color_stack:
            self.current_color = self.color_stack.pop()

    def transform_vertex(self, x: float, y: float) -> tuple:
        """Apply 2D transformation."""
        nx = self.mtx2d[0][0] * x + self.mtx2d[0][1] * y + self.mtx2d[0][2]
        ny = self.mtx2d[1][0] * x + self.mtx2d[1][1] * y + self.mtx2d[1][2]
        nw = self.mtx2d[2][0] * x + self.mtx2d[2][1] * y + self.mtx2d[2][2]
        if nw != 0:
            return nx / nw, ny / nw
        return nx, ny

    def transform_vertex_3(self, x: float, y: float, z: float) -> tuple:
        """Apply 3D transformation."""
        w = 1.0
        px = self.mtx3d[0][0] * x + self.mtx3d[0][1] * y + self.mtx3d[0][2] * z + self.mtx3d[0][3] * w
        py = self.mtx3d[1][0] * x + self.mtx3d[1][1] * y + self.mtx3d[1][2] * z + self.mtx3d[1][3] * w
        pz = self.mtx3d[2][0] * x + self.mtx3d[2][1] * y + self.mtx3d[2][2] * z + self.mtx3d[2][3] * w
        pw = self.mtx3d[3][0] * x + self.mtx3d[3][1] * y + self.mtx3d[3][2] * z + self.mtx3d[3][3] * w
        if pw != 0:
            return px / pw, py / pw, pz / pw
        return px, py, pz

    def begin(self, primitive: int):
        """Begin a new drawing primitive."""
        if self.current_object:
            return
        self.current_object = Object()
        self.primitive = primitive
        self.points_count = 0
        self.bezier_state = 0

    def vertex(self, x: float, y: float, color: int):
        """Add a 2D vertex."""
        self.vertex_2z(x, y, 0, color)

    def vertex_3(self, x: float, y: float, z: float, color: int):
        """Add a 3D vertex."""
        x, y, z = self.transform_vertex_3(x, y, z)
        if z == 0:
            z = 0.00001
        self.vertex_2z(x, y, 1.0 / z, color)

    def vertex_2z(self, x: float, y: float, z: float, color: int):
        """Add a vertex with explicit Z."""
        if not self.current_object:
            return

        # Apply color multiplication
        r1 = (color >> 16) & 0xFF
        g1 = (color >> 8) & 0xFF
        b1 = color & 0xFF
        r2 = (self.current_color >> 16) & 0xFF
        g2 = (self.current_color >> 8) & 0xFF
        b2 = self.current_color & 0xFF
        color = ((r1 * r2 // 255) << 16) | ((g1 * g2 // 255) << 8) | (b1 * b2 // 255)

        # Apply 2D transformation
        x, y = self.transform_vertex(x, y)

        if self.primitive == self.LINESTRIP:
            self._line_to(x, y, z, color)
        elif self.primitive == self.BEZIERSTRIP:
            self._bezier_to(x, y, color)
        elif self.primitive == self.POINTS:
            self._point_to(x, y, z, color)

    def _line_to(self, x: float, y: float, z: float, color: int):
        """Draw a line to the given point."""
        if self.points_count == 0:
            self.current_object.points.append(Point(x, y, z, color))
            self.points_count += 1
            self.last_point = Point(x, y, z, color)
            return

        # Add dwell points
        dwell = self._get_dwell(x, y)
        for _ in range(dwell):
            self.current_object.points.append(Point(
                self.last_point.x, self.last_point.y,
                self.last_point.z, self.last_point.color
            ))

        # Interpolate points
        dx = x - self.last_point.x
        dy = y - self.last_point.y
        dz = z - self.last_point.z
        distance = max(abs(dx), abs(dy))
        num_points = max(1, math.ceil(distance / self.params.on_speed))

        for i in range(1, num_points + 1):
            t = i / num_points
            self.current_object.points.append(Point(
                self.last_point.x + dx * t,
                self.last_point.y + dy * t,
                self.last_point.z + dz * t,
                color
            ))

        self.last_slope = self.last_point
        self.last_point = Point(x, y, z, color)
        self.points_count += 1

    def _get_dwell(self, x: float, y: float) -> int:
        """Calculate dwell time at current point."""
        if self.points_count == 1:
            return self.params.start_dwell
        return self.params.corner_dwell

    def _bezier_to(self, x: float, y: float, color: int):
        """Add a bezier control point."""
        if self.points_count == 0:
            self.current_object.points.append(Point(x, y, 0, color))
            self.points_count += 1
            self.last_point = Point(x, y, 0, color)
            return

        if self.bezier_state == 0:
            self.bezier_c1 = Point(x, y, 0, color)
            self.bezier_state = 1
        elif self.bezier_state == 1:
            self.bezier_c2 = Point(x, y, 0, color)
            self.bezier_state = 2
        else:
            # Draw bezier curve
            self._draw_bezier(self.bezier_c1.x, self.bezier_c1.y,
                              self.bezier_c2.x, self.bezier_c2.y, x, y, color)
            self.last_point = Point(x, y, 0, color)
            self.bezier_state = 0
            self.points_count += 1

    def _draw_bezier(self, x1: float, y1: float, x2: float, y2: float,
                     x3: float, y3: float, color: int, depth: int = 0):
        """Recursively draw a bezier curve."""
        if depth > 100:
            return

        x0, y0 = self.last_point.x, self.last_point.y

        # Check if subdivision is needed
        dx = x3 - x0
        dy = y3 - y0
        distance = max(abs(dx), abs(dy))

        subdivide = False
        if distance > self.params.on_speed:
            subdivide = True
        else:
            ux = 3.0 * x1 - 2.0 * x0 - x3
            uy = 3.0 * y1 - 2.0 * y0 - y3
            vx = 3.0 * x2 - 2.0 * x3 - x0
            vy = 3.0 * y2 - 2.0 * y3 - y0
            ux, uy, vx, vy = ux * ux, uy * uy, vx * vx, vy * vy
            if ux + uy > self.params.flatness or vx + vy > self.params.flatness:
                subdivide = True

        if subdivide:
            # de Casteljau subdivision at t=0.5
            mcx = (x1 + x2) * 0.5
            mcy = (y1 + y2) * 0.5
            ax1 = (x0 + x1) * 0.5
            ay1 = (y0 + y1) * 0.5
            ax2 = (ax1 + mcx) * 0.5
            ay2 = (ay1 + mcy) * 0.5
            bx2 = (x2 + x3) * 0.5
            by2 = (y2 + y3) * 0.5
            bx1 = (bx2 + mcx) * 0.5
            by1 = (by2 + mcy) * 0.5
            xm = (ax2 + bx1) * 0.5
            ym = (ay2 + by1) * 0.5
            self._draw_bezier(ax1, ay1, ax2, ay2, xm, ym, color, depth + 1)
            self.last_point = Point(xm, ym, 0, color)
            self._draw_bezier(bx1, by1, bx2, by2, x3, y3, color, depth + 1)
        else:
            self.current_object.points.append(Point(x3, y3, 0, color))
            self.last_point = Point(x3, y3, 0, color)

    def _point_to(self, x: float, y: float, z: float, color: int):
        """Add a point."""
        self.current_object.points.append(Point(x, y, z, color))
        if self.points_count == 0:
            for _ in range(self.params.start_dwell):
                self.current_object.points.append(Point(x, y, z, color))
        self.points_count += 1

    def end(self):
        """End current drawing primitive."""
        if not self.current_object:
            return
        if self.points_count < 2:
            self.current_object = None
            return

        # Add end dwell
        if self.current_object.points:
            last = self.current_object.points[-1]
            for _ in range(self.params.end_dwell):
                self.current_object.points.append(Point(last.x, last.y, last.z, last.color))

        self.objects.append(self.current_object)
        self.current_object = None

    def rect(self, x1: float, y1: float, x2: float, y2: float, color: int):
        """Draw a rectangle."""
        self.begin(self.LINESTRIP)
        self.vertex(x1, y1, color)
        self.vertex(x1, y2, color)
        self.vertex(x2, y2, color)
        self.vertex(x2, y1, color)
        self.vertex(x1, y1, color)
        self.end()

    def line(self, x1: float, y1: float, x2: float, y2: float, color: int):
        """Draw a line."""
        self.begin(self.LINESTRIP)
        self.vertex(x1, y1, color)
        self.vertex(x2, y2, color)
        self.end()

    def dot(self, x: float, y: float, samples: int, color: int):
        """Draw a dot."""
        self.begin(self.POINTS)
        for _ in range(samples):
            self.vertex(x, y, color)
        self.end()

    def render_frame(self) -> List[LaserPoint]:
        """
        Render all objects to laser points and reset for next frame.
        Returns list of LaserPoint for the Helios DAC.
        """
        output_points = []
        last_point = LaserPoint(2048, 2048, 0, 0, 0)

        for obj in self.objects:
            if not obj.points:
                continue

            # Move to first point (blanking)
            first = obj.points[0]
            hx, hy = normalize_to_helios(first.x, first.y)

            # Calculate travel distance
            dx = hx - last_point.x
            dy = hy - last_point.y
            distance = math.sqrt(dx * dx + dy * dy)
            travel_points = max(1, int(distance * self.params.off_speed * 100))

            # Blanking travel
            for i in range(travel_points):
                t = i / travel_points
                output_points.append(LaserPoint(
                    int(last_point.x + dx * t),
                    int(last_point.y + dy * t),
                    0, 0, 0  # Blanked
                ))

            # Wait points at start
            for _ in range(self.params.start_wait):
                output_points.append(LaserPoint(hx, hy, 0, 0, 0))

            # Draw object points
            for point in obj.points:
                hx, hy = normalize_to_helios(point.x, point.y)
                r, g, b = color_to_rgb(point.color)
                output_points.append(LaserPoint(hx, hy, r, g, b))
                last_point = LaserPoint(hx, hy, r, g, b)

            # Wait points at end
            for _ in range(self.params.end_wait):
                output_points.append(LaserPoint(last_point.x, last_point.y, 0, 0, 0))

        # Reset for next frame
        self.objects = []
        return output_points


# Convenience functions matching OpenLase API
_renderer: Optional[LaserRenderer] = None


def init():
    """Initialize the renderer."""
    global _renderer
    _renderer = LaserRenderer()


def get_renderer() -> LaserRenderer:
    """Get the current renderer instance."""
    global _renderer
    if _renderer is None:
        init()
    return _renderer


def load_identity():
    get_renderer().load_identity()


def push_matrix():
    get_renderer().push_matrix()


def pop_matrix():
    get_renderer().pop_matrix()


def rotate(theta: float):
    get_renderer().rotate(theta)


def translate(x: float, y: float):
    get_renderer().translate(x, y)


def scale(sx: float, sy: float):
    get_renderer().scale(sx, sy)


def load_identity_3():
    get_renderer().load_identity_3()


def push_matrix_3():
    get_renderer().push_matrix_3()


def pop_matrix_3():
    get_renderer().pop_matrix_3()


def rotate_3x(theta: float):
    get_renderer().rotate_3x(theta)


def rotate_3y(theta: float):
    get_renderer().rotate_3y(theta)


def rotate_3z(theta: float):
    get_renderer().rotate_3z(theta)


def translate_3(x: float, y: float, z: float):
    get_renderer().translate_3(x, y, z)


def scale_3(sx: float, sy: float, sz: float):
    get_renderer().scale_3(sx, sy, sz)


def perspective(fovy: float, aspect: float, z_near: float, z_far: float):
    get_renderer().perspective(fovy, aspect, z_near, z_far)


def begin(primitive: int):
    get_renderer().begin(primitive)


def vertex(x: float, y: float, color: int):
    get_renderer().vertex(x, y, color)


def vertex_3(x: float, y: float, z: float, color: int):
    get_renderer().vertex_3(x, y, z, color)


def end():
    get_renderer().end()


def rect(x1: float, y1: float, x2: float, y2: float, color: int):
    get_renderer().rect(x1, y1, x2, y2, color)


def line(x1: float, y1: float, x2: float, y2: float, color: int):
    get_renderer().line(x1, y1, x2, y2, color)


def render_frame() -> List[LaserPoint]:
    return get_renderer().render_frame()
