"""
OpenLase Web - Pattern Generator

This module provides various laser pattern generators for demonstration
and creative use.

Copyright (C) 2024

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 2.1 or version 3.
"""

import math
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Callable
from .laser_renderer import LaserRenderer, LaserPoint, RenderParams


@dataclass
class PatternConfig:
    """Configuration for a pattern."""
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)


class PatternGenerator:
    """Base class for pattern generators."""

    def __init__(self):
        self.renderer = LaserRenderer()
        self.start_time = time.time()
        self.params = RenderParams()

    def get_time(self) -> float:
        """Get elapsed time since start."""
        return time.time() - self.start_time

    def reset_time(self):
        """Reset the time counter."""
        self.start_time = time.time()

    def generate(self) -> List[LaserPoint]:
        """Generate a frame of the pattern. Override in subclasses."""
        raise NotImplementedError

    @classmethod
    def get_config(cls) -> PatternConfig:
        """Get pattern configuration. Override in subclasses."""
        return PatternConfig(
            name="Base Pattern",
            description="Base pattern class"
        )


class RotatingCubePattern(PatternGenerator):
    """3D rotating cube pattern."""

    def __init__(self, color: int = 0xFFFFFF, speed: float = 1.0):
        super().__init__()
        self.color = color
        self.speed = speed

    def generate(self) -> List[LaserPoint]:
        t = self.get_time() * self.speed

        self.renderer.reset()
        self.renderer.load_identity_3()
        self.renderer.load_identity()
        self.renderer.perspective(60, 1, 1, 100)
        self.renderer.translate_3(0, 0, -3)

        # Rainbow color cycling
        hue = (t * 50) % 360
        color = self._hsv_to_rgb(hue, 1.0, 1.0)

        for i in range(2):
            self.renderer.scale_3(0.6, 0.6, 0.6)
            self.renderer.rotate_3z(t * math.pi * 0.1)
            self.renderer.rotate_3y(t * math.pi * 0.8)
            self.renderer.rotate_3x(t * math.pi * 0.73)

            # Draw cube edges
            self.renderer.begin(LaserRenderer.LINESTRIP)
            self.renderer.vertex_3(-1, -1, -1, color)
            self.renderer.vertex_3(1, -1, -1, color)
            self.renderer.vertex_3(1, 1, -1, color)
            self.renderer.vertex_3(-1, 1, -1, color)
            self.renderer.vertex_3(-1, -1, -1, color)
            self.renderer.vertex_3(-1, -1, 1, color)
            self.renderer.end()

            self.renderer.begin(LaserRenderer.LINESTRIP)
            self.renderer.vertex_3(1, 1, 1, color)
            self.renderer.vertex_3(-1, 1, 1, color)
            self.renderer.vertex_3(-1, -1, 1, color)
            self.renderer.vertex_3(1, -1, 1, color)
            self.renderer.vertex_3(1, 1, 1, color)
            self.renderer.vertex_3(1, 1, -1, color)
            self.renderer.end()

            self.renderer.begin(LaserRenderer.LINESTRIP)
            self.renderer.vertex_3(1, -1, -1, color)
            self.renderer.vertex_3(1, -1, 1, color)
            self.renderer.end()

            self.renderer.begin(LaserRenderer.LINESTRIP)
            self.renderer.vertex_3(-1, 1, 1, color)
            self.renderer.vertex_3(-1, 1, -1, color)
            self.renderer.end()

        return self.renderer.render_frame()

    def _hsv_to_rgb(self, h: float, s: float, v: float) -> int:
        """Convert HSV to RGB color value."""
        h = h % 360
        c = v * s
        x = c * (1 - abs((h / 60) % 2 - 1))
        m = v - c

        if h < 60:
            r, g, b = c, x, 0
        elif h < 120:
            r, g, b = x, c, 0
        elif h < 180:
            r, g, b = 0, c, x
        elif h < 240:
            r, g, b = 0, x, c
        elif h < 300:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x

        r = int((r + m) * 255)
        g = int((g + m) * 255)
        b = int((b + m) * 255)
        return (r << 16) | (g << 8) | b

    @classmethod
    def get_config(cls) -> PatternConfig:
        return PatternConfig(
            name="Rotating Cube",
            description="A colorful 3D rotating cube",
            parameters={
                "speed": {"type": "float", "min": 0.1, "max": 5.0, "default": 1.0}
            }
        )


class SpiralPattern(PatternGenerator):
    """Animated spiral pattern."""

    def __init__(self, arms: int = 3, rotations: int = 3, speed: float = 1.0):
        super().__init__()
        self.arms = arms
        self.rotations = rotations
        self.speed = speed

    def generate(self) -> List[LaserPoint]:
        t = self.get_time() * self.speed
        self.renderer.reset()

        for arm in range(self.arms):
            arm_offset = (2 * math.pi * arm) / self.arms + t
            hue = (arm * 120 + t * 30) % 360
            color = self._hsv_to_rgb(hue, 1.0, 1.0)

            self.renderer.begin(LaserRenderer.LINESTRIP)
            for i in range(100):
                angle = arm_offset + i * 0.1 * self.rotations
                radius = i * 0.01
                x = math.cos(angle) * radius
                y = math.sin(angle) * radius
                self.renderer.vertex(x, y, color)
            self.renderer.end()

        return self.renderer.render_frame()

    def _hsv_to_rgb(self, h: float, s: float, v: float) -> int:
        h = h % 360
        c = v * s
        x = c * (1 - abs((h / 60) % 2 - 1))
        m = v - c

        if h < 60:
            r, g, b = c, x, 0
        elif h < 120:
            r, g, b = x, c, 0
        elif h < 180:
            r, g, b = 0, c, x
        elif h < 240:
            r, g, b = 0, x, c
        elif h < 300:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x

        r = int((r + m) * 255)
        g = int((g + m) * 255)
        b = int((b + m) * 255)
        return (r << 16) | (g << 8) | b

    @classmethod
    def get_config(cls) -> PatternConfig:
        return PatternConfig(
            name="Spiral",
            description="Animated multi-arm spiral",
            parameters={
                "arms": {"type": "int", "min": 1, "max": 10, "default": 3},
                "rotations": {"type": "int", "min": 1, "max": 10, "default": 3},
                "speed": {"type": "float", "min": 0.1, "max": 5.0, "default": 1.0}
            }
        )


class WavePattern(PatternGenerator):
    """Animated wave pattern."""

    def __init__(self, waves: int = 3, amplitude: float = 0.3, speed: float = 1.0):
        super().__init__()
        self.waves = waves
        self.amplitude = amplitude
        self.speed = speed

    def generate(self) -> List[LaserPoint]:
        t = self.get_time() * self.speed
        self.renderer.reset()

        for wave in range(self.waves):
            y_offset = -0.6 + (wave * 0.6)
            phase = wave * math.pi / 2
            hue = (wave * 120 + t * 50) % 360
            color = self._hsv_to_rgb(hue, 1.0, 1.0)

            self.renderer.begin(LaserRenderer.LINESTRIP)
            for i in range(100):
                x = -0.9 + i * 0.018
                y = y_offset + math.sin(x * 6 + t * 3 + phase) * self.amplitude
                self.renderer.vertex(x, y, color)
            self.renderer.end()

        return self.renderer.render_frame()

    def _hsv_to_rgb(self, h: float, s: float, v: float) -> int:
        h = h % 360
        c = v * s
        x = c * (1 - abs((h / 60) % 2 - 1))
        m = v - c

        if h < 60:
            r, g, b = c, x, 0
        elif h < 120:
            r, g, b = x, c, 0
        elif h < 180:
            r, g, b = 0, c, x
        elif h < 240:
            r, g, b = 0, x, c
        elif h < 300:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x

        r = int((r + m) * 255)
        g = int((g + m) * 255)
        b = int((b + m) * 255)
        return (r << 16) | (g << 8) | b

    @classmethod
    def get_config(cls) -> PatternConfig:
        return PatternConfig(
            name="Wave",
            description="Animated sine waves",
            parameters={
                "waves": {"type": "int", "min": 1, "max": 10, "default": 3},
                "amplitude": {"type": "float", "min": 0.1, "max": 0.5, "default": 0.3},
                "speed": {"type": "float", "min": 0.1, "max": 5.0, "default": 1.0}
            }
        )


class CirclePattern(PatternGenerator):
    """Simple circle pattern."""

    def __init__(self, radius: float = 0.7, segments: int = 100, 
                 rotating: bool = True, speed: float = 1.0):
        super().__init__()
        self.radius = radius
        self.segments = segments
        self.rotating = rotating
        self.speed = speed

    def generate(self) -> List[LaserPoint]:
        t = self.get_time() * self.speed if self.rotating else 0
        self.renderer.reset()

        hue = (t * 60) % 360
        color = self._hsv_to_rgb(hue, 1.0, 1.0)

        self.renderer.begin(LaserRenderer.LINESTRIP)
        for i in range(self.segments + 1):
            angle = (i / self.segments) * 2 * math.pi + t
            x = math.cos(angle) * self.radius
            y = math.sin(angle) * self.radius
            self.renderer.vertex(x, y, color)
        self.renderer.end()

        return self.renderer.render_frame()

    def _hsv_to_rgb(self, h: float, s: float, v: float) -> int:
        h = h % 360
        c = v * s
        x = c * (1 - abs((h / 60) % 2 - 1))
        m = v - c

        if h < 60:
            r, g, b = c, x, 0
        elif h < 120:
            r, g, b = x, c, 0
        elif h < 180:
            r, g, b = 0, c, x
        elif h < 240:
            r, g, b = 0, x, c
        elif h < 300:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x

        r = int((r + m) * 255)
        g = int((g + m) * 255)
        b = int((b + m) * 255)
        return (r << 16) | (g << 8) | b

    @classmethod
    def get_config(cls) -> PatternConfig:
        return PatternConfig(
            name="Circle",
            description="Simple rotating circle",
            parameters={
                "radius": {"type": "float", "min": 0.1, "max": 1.0, "default": 0.7},
                "segments": {"type": "int", "min": 10, "max": 200, "default": 100},
                "rotating": {"type": "bool", "default": True},
                "speed": {"type": "float", "min": 0.1, "max": 5.0, "default": 1.0}
            }
        )


class LissajousPattern(PatternGenerator):
    """Lissajous curve pattern."""

    def __init__(self, a: int = 3, b: int = 4, delta: float = 0,
                 animate_delta: bool = True, speed: float = 1.0):
        super().__init__()
        self.a = a
        self.b = b
        self.delta = delta
        self.animate_delta = animate_delta
        self.speed = speed

    def generate(self) -> List[LaserPoint]:
        t = self.get_time() * self.speed
        self.renderer.reset()

        delta = t if self.animate_delta else self.delta
        hue = (t * 40) % 360
        color = self._hsv_to_rgb(hue, 1.0, 1.0)

        self.renderer.begin(LaserRenderer.LINESTRIP)
        for i in range(200):
            angle = (i / 200) * 2 * math.pi
            x = 0.8 * math.sin(self.a * angle + delta)
            y = 0.8 * math.sin(self.b * angle)
            self.renderer.vertex(x, y, color)
        self.renderer.end()

        return self.renderer.render_frame()

    def _hsv_to_rgb(self, h: float, s: float, v: float) -> int:
        h = h % 360
        c = v * s
        x = c * (1 - abs((h / 60) % 2 - 1))
        m = v - c

        if h < 60:
            r, g, b = c, x, 0
        elif h < 120:
            r, g, b = x, c, 0
        elif h < 180:
            r, g, b = 0, c, x
        elif h < 240:
            r, g, b = 0, x, c
        elif h < 300:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x

        r = int((r + m) * 255)
        g = int((g + m) * 255)
        b = int((b + m) * 255)
        return (r << 16) | (g << 8) | b

    @classmethod
    def get_config(cls) -> PatternConfig:
        return PatternConfig(
            name="Lissajous",
            description="Lissajous curve pattern",
            parameters={
                "a": {"type": "int", "min": 1, "max": 10, "default": 3},
                "b": {"type": "int", "min": 1, "max": 10, "default": 4},
                "animate_delta": {"type": "bool", "default": True},
                "speed": {"type": "float", "min": 0.1, "max": 5.0, "default": 1.0}
            }
        )


class TextPattern(PatternGenerator):
    """Simple text pattern using line drawing."""

    def __init__(self, text: str = "LASER", size: float = 0.3, speed: float = 0.5):
        super().__init__()
        self.text = text.upper()
        self.size = size
        self.speed = speed
        # Simple font definition (basic block letters)
        self.font = self._create_font()

    def _create_font(self) -> Dict[str, List[List[tuple]]]:
        """Create simple block letter font definitions."""
        return {
            'A': [[(0, 0), (0.5, 1), (1, 0)], [(0.25, 0.5), (0.75, 0.5)]],
            'B': [[(0, 0), (0, 1), (0.7, 1), (0.8, 0.9), (0.8, 0.6), (0.7, 0.5), (0, 0.5)],
                  [(0.7, 0.5), (0.8, 0.4), (0.8, 0.1), (0.7, 0), (0, 0)]],
            'C': [[(1, 0.2), (0.8, 0), (0.2, 0), (0, 0.2), (0, 0.8), (0.2, 1), (0.8, 1), (1, 0.8)]],
            'D': [[(0, 0), (0, 1), (0.6, 1), (1, 0.7), (1, 0.3), (0.6, 0), (0, 0)]],
            'E': [[(1, 0), (0, 0), (0, 1), (1, 1)], [(0, 0.5), (0.7, 0.5)]],
            'F': [[(0, 0), (0, 1), (1, 1)], [(0, 0.5), (0.7, 0.5)]],
            'G': [[(1, 0.8), (0.8, 1), (0.2, 1), (0, 0.8), (0, 0.2), (0.2, 0), (0.8, 0), (1, 0.2), (1, 0.5), (0.5, 0.5)]],
            'H': [[(0, 0), (0, 1)], [(1, 0), (1, 1)], [(0, 0.5), (1, 0.5)]],
            'I': [[(0.3, 0), (0.7, 0)], [(0.5, 0), (0.5, 1)], [(0.3, 1), (0.7, 1)]],
            'J': [[(0.2, 1), (0.8, 1)], [(0.5, 1), (0.5, 0.2), (0.3, 0), (0, 0.2)]],
            'K': [[(0, 0), (0, 1)], [(1, 1), (0, 0.5), (1, 0)]],
            'L': [[(0, 1), (0, 0), (1, 0)]],
            'M': [[(0, 0), (0, 1), (0.5, 0.5), (1, 1), (1, 0)]],
            'N': [[(0, 0), (0, 1), (1, 0), (1, 1)]],
            'O': [[(0.5, 0), (0.2, 0), (0, 0.2), (0, 0.8), (0.2, 1), (0.8, 1), (1, 0.8), (1, 0.2), (0.8, 0), (0.5, 0)]],
            'P': [[(0, 0), (0, 1), (0.8, 1), (1, 0.8), (1, 0.6), (0.8, 0.5), (0, 0.5)]],
            'Q': [[(0.5, 0), (0.2, 0), (0, 0.2), (0, 0.8), (0.2, 1), (0.8, 1), (1, 0.8), (1, 0.2), (0.8, 0), (0.5, 0)],
                  [(0.6, 0.3), (1, -0.1)]],
            'R': [[(0, 0), (0, 1), (0.8, 1), (1, 0.8), (1, 0.6), (0.8, 0.5), (0, 0.5)], [(0.5, 0.5), (1, 0)]],
            'S': [[(1, 0.8), (0.8, 1), (0.2, 1), (0, 0.8), (0, 0.6), (0.2, 0.5), (0.8, 0.5), (1, 0.4), (1, 0.2), (0.8, 0), (0.2, 0), (0, 0.2)]],
            'T': [[(0, 1), (1, 1)], [(0.5, 1), (0.5, 0)]],
            'U': [[(0, 1), (0, 0.2), (0.2, 0), (0.8, 0), (1, 0.2), (1, 1)]],
            'V': [[(0, 1), (0.5, 0), (1, 1)]],
            'W': [[(0, 1), (0.25, 0), (0.5, 0.5), (0.75, 0), (1, 1)]],
            'X': [[(0, 0), (1, 1)], [(0, 1), (1, 0)]],
            'Y': [[(0, 1), (0.5, 0.5), (1, 1)], [(0.5, 0.5), (0.5, 0)]],
            'Z': [[(0, 1), (1, 1), (0, 0), (1, 0)]],
            '0': [[(0.5, 0), (0.2, 0), (0, 0.2), (0, 0.8), (0.2, 1), (0.8, 1), (1, 0.8), (1, 0.2), (0.8, 0), (0.5, 0)]],
            '1': [[(0.3, 0.8), (0.5, 1), (0.5, 0)], [(0.2, 0), (0.8, 0)]],
            '2': [[(0, 0.8), (0.2, 1), (0.8, 1), (1, 0.8), (1, 0.6), (0, 0), (1, 0)]],
            '3': [[(0, 0.8), (0.2, 1), (0.8, 1), (1, 0.8), (0.8, 0.5), (0.3, 0.5)],
                  [(0.8, 0.5), (1, 0.3), (0.8, 0), (0.2, 0), (0, 0.2)]],
            '4': [[(0, 1), (0, 0.5), (1, 0.5)], [(0.7, 1), (0.7, 0)]],
            '5': [[(1, 1), (0, 1), (0, 0.5), (0.8, 0.5), (1, 0.3), (0.8, 0), (0.2, 0), (0, 0.2)]],
            '6': [[(0.8, 1), (0.2, 1), (0, 0.8), (0, 0.2), (0.2, 0), (0.8, 0), (1, 0.2), (1, 0.4), (0.8, 0.5), (0, 0.5)]],
            '7': [[(0, 1), (1, 1), (0.4, 0)]],
            '8': [[(0.5, 0.5), (0.2, 0.5), (0, 0.7), (0.2, 1), (0.8, 1), (1, 0.7), (0.8, 0.5), (0.2, 0.5)],
                  [(0.8, 0.5), (1, 0.3), (0.8, 0), (0.2, 0), (0, 0.3), (0.2, 0.5)]],
            '9': [[(0.2, 0), (0.8, 0), (1, 0.2), (1, 0.8), (0.8, 1), (0.2, 1), (0, 0.8), (0, 0.6), (0.2, 0.5), (1, 0.5)]],
            ' ': [],
            '!': [[(0.5, 1), (0.5, 0.3)], [(0.5, 0.1), (0.5, 0)]],
        }

    def generate(self) -> List[LaserPoint]:
        t = self.get_time() * self.speed
        self.renderer.reset()

        # Calculate total width
        char_width = self.size * 1.2
        total_width = len(self.text) * char_width
        start_x = -total_width / 2

        hue = (t * 60) % 360
        color = self._hsv_to_rgb(hue, 1.0, 1.0)

        # Apply some animation
        self.renderer.rotate(math.sin(t * 0.5) * 0.1)

        for i, char in enumerate(self.text):
            if char in self.font:
                x_offset = start_x + i * char_width
                y_offset = -self.size / 2 + math.sin(t * 2 + i * 0.5) * 0.05

                for stroke in self.font[char]:
                    if len(stroke) >= 2:
                        self.renderer.begin(LaserRenderer.LINESTRIP)
                        for x, y in stroke:
                            px = x_offset + x * self.size
                            py = y_offset + y * self.size
                            self.renderer.vertex(px, py, color)
                        self.renderer.end()

        return self.renderer.render_frame()

    def _hsv_to_rgb(self, h: float, s: float, v: float) -> int:
        h = h % 360
        c = v * s
        x = c * (1 - abs((h / 60) % 2 - 1))
        m = v - c

        if h < 60:
            r, g, b = c, x, 0
        elif h < 120:
            r, g, b = x, c, 0
        elif h < 180:
            r, g, b = 0, c, x
        elif h < 240:
            r, g, b = 0, x, c
        elif h < 300:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x

        r = int((r + m) * 255)
        g = int((g + m) * 255)
        b = int((b + m) * 255)
        return (r << 16) | (g << 8) | b

    @classmethod
    def get_config(cls) -> PatternConfig:
        return PatternConfig(
            name="Text",
            description="Animated text display",
            parameters={
                "text": {"type": "str", "default": "LASER"},
                "size": {"type": "float", "min": 0.1, "max": 0.5, "default": 0.3},
                "speed": {"type": "float", "min": 0.1, "max": 5.0, "default": 0.5}
            }
        )


# Registry of available patterns
PATTERNS = {
    "cube": RotatingCubePattern,
    "spiral": SpiralPattern,
    "wave": WavePattern,
    "circle": CirclePattern,
    "lissajous": LissajousPattern,
    "text": TextPattern,
}


def get_pattern_list() -> List[Dict[str, Any]]:
    """Get list of available patterns with their configurations."""
    return [
        {
            "id": pattern_id,
            "name": pattern_class.get_config().name,
            "description": pattern_class.get_config().description,
            "parameters": pattern_class.get_config().parameters
        }
        for pattern_id, pattern_class in PATTERNS.items()
    ]


def create_pattern(pattern_id: str, **kwargs) -> PatternGenerator:
    """Create a pattern instance by ID."""
    if pattern_id not in PATTERNS:
        raise ValueError(f"Unknown pattern: {pattern_id}")
    return PATTERNS[pattern_id](**kwargs)
