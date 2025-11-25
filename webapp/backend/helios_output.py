"""
OpenLase Web - Helios DAC Output Module

This module provides the interface to the Helios DAC laser controller,
replacing the original JACK audio output for web-based operation.

Copyright (C) 2024

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 2.1 or version 3.
"""

import ctypes
import os
import threading
import time
from dataclasses import dataclass
from typing import List, Optional, Callable
import logging

logger = logging.getLogger(__name__)


@dataclass
class LaserPoint:
    """Represents a single laser point with position and color."""
    x: int  # 0-4095 for Helios DAC
    y: int  # 0-4095 for Helios DAC
    r: int  # 0-255
    g: int  # 0-255
    b: int  # 0-255
    i: int = 255  # Intensity 0-255

    def to_helios_format(self):
        """Convert to Helios DAC native format."""
        return (self.x, self.y, self.r, self.g, self.b, self.i)


class HeliosPoint(ctypes.Structure):
    """C structure for Helios DAC point data."""
    _fields_ = [
        ("x", ctypes.c_uint16),
        ("y", ctypes.c_uint16),
        ("r", ctypes.c_uint8),
        ("g", ctypes.c_uint8),
        ("b", ctypes.c_uint8),
        ("i", ctypes.c_uint8),
    ]


class SimulatedHeliosDAC:
    """
    Simulated Helios DAC for development/testing without hardware.
    Stores frames for visualization in the web interface.
    """

    def __init__(self):
        self.connected = False
        self.current_frame: List[LaserPoint] = []
        self.frame_rate = 30000  # points per second
        self.callbacks: List[Callable] = []
        self._lock = threading.Lock()
        logger.info("SimulatedHeliosDAC initialized")

    def open_devices(self) -> int:
        """Simulate opening devices, returns 1 for simulated device."""
        self.connected = True
        return 1

    def close_devices(self):
        """Close simulated devices."""
        self.connected = False

    def get_status(self, device_num: int = 0) -> int:
        """Get device status (1 = ready, 0 = busy)."""
        return 1 if self.connected else 0

    def write_frame(self, device_num: int, points: List[LaserPoint],
                    pps: int = 30000, flags: int = 0) -> int:
        """
        Write a frame to the simulated DAC.
        Returns 1 on success, 0 on failure.
        """
        if not self.connected:
            return 0

        with self._lock:
            self.current_frame = points.copy()

        # Notify callbacks for web preview
        for callback in self.callbacks:
            try:
                callback(points)
            except Exception as e:
                logger.error(f"Callback error: {e}")

        return 1

    def get_current_frame(self) -> List[LaserPoint]:
        """Get the current frame for preview."""
        with self._lock:
            return self.current_frame.copy()

    def register_callback(self, callback: Callable):
        """Register a callback for frame updates."""
        self.callbacks.append(callback)

    def unregister_callback(self, callback: Callable):
        """Unregister a callback."""
        if callback in self.callbacks:
            self.callbacks.remove(callback)


class HeliosDAC:
    """
    Interface to the Helios DAC hardware.
    Falls back to simulation if hardware is not available.
    """

    def __init__(self, simulate: bool = False):
        self.simulate = simulate
        self.lib = None
        self.simulated_dac: Optional[SimulatedHeliosDAC] = None
        self.device_count = 0
        self._lock = threading.Lock()
        self._running = False
        self._frame_thread: Optional[threading.Thread] = None
        self._current_points: List[LaserPoint] = []
        self._pps = 30000

        if simulate:
            self._init_simulation()
        else:
            self._init_hardware()

    def _init_simulation(self):
        """Initialize simulation mode."""
        self.simulated_dac = SimulatedHeliosDAC()
        self.device_count = self.simulated_dac.open_devices()
        logger.info("Helios DAC running in simulation mode")

    def _init_hardware(self):
        """Initialize hardware mode, fall back to simulation if unavailable."""
        try:
            lib_path = self._find_library()
            if lib_path:
                self.lib = ctypes.CDLL(lib_path)
                self._setup_lib_functions()
                self.device_count = self.lib.OpenDevices()
                if self.device_count > 0:
                    logger.info(f"Found {self.device_count} Helios DAC device(s)")
                    return
        except Exception as e:
            logger.warning(f"Could not initialize Helios hardware: {e}")

        # Fall back to simulation
        logger.info("Falling back to simulation mode")
        self.simulate = True
        self._init_simulation()

    def _find_library(self) -> Optional[str]:
        """Find the Helios DAC library."""
        # Common library paths
        lib_names = [
            "libHeliosDacAPI.so",
            "libHeliosDacAPI.dylib",
            "HeliosDacAPI.dll",
        ]

        search_paths = [
            os.path.dirname(__file__),
            "/usr/local/lib",
            "/usr/lib",
            os.path.expanduser("~/.local/lib"),
        ]

        for path in search_paths:
            for name in lib_names:
                full_path = os.path.join(path, name)
                if os.path.exists(full_path):
                    return full_path
        return None

    def _setup_lib_functions(self):
        """Set up ctypes function signatures."""
        if not self.lib:
            return

        # OpenDevices() -> int
        self.lib.OpenDevices.restype = ctypes.c_int

        # CloseDevices() -> int
        self.lib.CloseDevices.restype = ctypes.c_int

        # GetStatus(int deviceNum) -> int
        self.lib.GetStatus.argtypes = [ctypes.c_int]
        self.lib.GetStatus.restype = ctypes.c_int

        # WriteFrame(int deviceNum, HeliosPoint* points, int numPoints, int pps, int flags) -> int
        self.lib.WriteFrame.argtypes = [
            ctypes.c_int,
            ctypes.POINTER(HeliosPoint),
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
        ]
        self.lib.WriteFrame.restype = ctypes.c_int

    def open_devices(self) -> int:
        """Open and enumerate Helios devices."""
        if self.simulate:
            return self.simulated_dac.open_devices()
        return self.lib.OpenDevices() if self.lib else 0

    def close_devices(self):
        """Close all Helios devices."""
        if self.simulate:
            self.simulated_dac.close_devices()
        elif self.lib:
            self.lib.CloseDevices()

    def get_status(self, device_num: int = 0) -> int:
        """Get device status."""
        if self.simulate:
            return self.simulated_dac.get_status(device_num)
        return self.lib.GetStatus(device_num) if self.lib else 0

    def write_frame(self, device_num: int, points: List[LaserPoint],
                    pps: int = 30000, flags: int = 0) -> int:
        """Write a frame to the DAC."""
        if self.simulate:
            return self.simulated_dac.write_frame(device_num, points, pps, flags)

        if not self.lib or not points:
            return 0

        # Convert to ctypes array
        point_array = (HeliosPoint * len(points))()
        for i, p in enumerate(points):
            point_array[i].x = p.x
            point_array[i].y = p.y
            point_array[i].r = p.r
            point_array[i].g = p.g
            point_array[i].b = p.b
            point_array[i].i = p.i

        return self.lib.WriteFrame(device_num, point_array, len(points), pps, flags)

    def start_streaming(self, points_callback: Callable[[], List[LaserPoint]],
                        pps: int = 30000):
        """Start streaming frames from a callback function."""
        self._running = True
        self._pps = pps

        def stream_loop():
            while self._running:
                points = points_callback()
                if points:
                    while self.get_status(0) != 1 and self._running:
                        time.sleep(0.0001)
                    if self._running:
                        self.write_frame(0, points, self._pps)
                else:
                    time.sleep(0.001)

        self._frame_thread = threading.Thread(target=stream_loop, daemon=True)
        self._frame_thread.start()

    def stop_streaming(self):
        """Stop the streaming thread."""
        self._running = False
        if self._frame_thread:
            self._frame_thread.join(timeout=1.0)
            self._frame_thread = None

    def get_current_frame(self) -> List[LaserPoint]:
        """Get current frame for preview (simulation mode only)."""
        if self.simulate and self.simulated_dac:
            return self.simulated_dac.get_current_frame()
        return []

    def register_frame_callback(self, callback: Callable):
        """Register a callback for frame updates (simulation mode)."""
        if self.simulate and self.simulated_dac:
            self.simulated_dac.register_callback(callback)


def normalize_to_helios(x: float, y: float) -> tuple:
    """
    Convert normalized coordinates (-1 to 1) to Helios DAC coordinates (0-4095).
    """
    hx = int((x + 1.0) * 2047.5)
    hy = int((y + 1.0) * 2047.5)
    # Clamp to valid range
    hx = max(0, min(4095, hx))
    hy = max(0, min(4095, hy))
    return hx, hy


def color_to_rgb(color: int) -> tuple:
    """
    Convert OpenLase color format (0xRRGGBB) to RGB tuple.
    """
    r = (color >> 16) & 0xFF
    g = (color >> 8) & 0xFF
    b = color & 0xFF
    return r, g, b
