"""
OpenLase Web - Video Input Module

This module provides video input capabilities for realtime laser output,
including video file processing and frame capture from browser.

Copyright (C) 2024

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 2.1 or version 3.
"""

import base64
import io
import logging
import math
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Tuple
from PIL import Image
import numpy as np

from .helios_output import LaserPoint, normalize_to_helios
from .laser_renderer import LaserRenderer, RenderParams

logger = logging.getLogger(__name__)


@dataclass
class EdgePoint:
    """Represents an edge point with coordinates."""
    x: float
    y: float


@dataclass
class TraceParams:
    """Parameters for edge detection and tracing."""
    threshold: int = 50
    threshold2: int = 100
    min_length: int = 10
    decimate: int = 2
    blur_sigma: float = 1.0
    use_canny: bool = True
    invert: bool = False


class EdgeTracer:
    """
    Edge detection and tracing for converting images to laser points.
    Uses simple edge detection algorithm inspired by OpenLase's trace.c.
    """

    def __init__(self, params: Optional[TraceParams] = None):
        self.params = params or TraceParams()

    def trace(self, image_data: bytes, width: int, height: int) -> List[List[EdgePoint]]:
        """
        Trace edges in an image and return a list of edge objects.
        
        Args:
            image_data: Raw grayscale image data
            width: Image width
            height: Image height
        
        Returns:
            List of edge objects, each containing a list of EdgePoints
        """
        # Convert to numpy array
        if isinstance(image_data, bytes):
            arr = np.frombuffer(image_data, dtype=np.uint8).reshape((height, width))
        else:
            arr = image_data

        # Apply threshold or Canny-like edge detection
        if self.params.use_canny:
            edges = self._canny_edge_detection(arr)
        else:
            edges = self._threshold_detection(arr)

        # Trace contours
        objects = self._trace_contours(edges, width, height)

        return objects

    def _threshold_detection(self, arr: np.ndarray) -> np.ndarray:
        """Simple threshold-based edge detection."""
        thresh = self.params.threshold
        if self.params.invert:
            edges = arr < thresh
        else:
            edges = arr > thresh
        return edges.astype(np.uint8)

    def _canny_edge_detection(self, arr: np.ndarray) -> np.ndarray:
        """
        Simple Canny-like edge detection.
        Uses Sobel operators for gradient calculation.
        """
        # Apply Gaussian blur if sigma > 0
        if self.params.blur_sigma > 0:
            arr = self._gaussian_blur(arr, self.params.blur_sigma)

        # Compute gradients using Sobel operators
        gx = self._sobel_x(arr)
        gy = self._sobel_y(arr)

        # Compute gradient magnitude
        magnitude = np.sqrt(gx.astype(np.float32)**2 + gy.astype(np.float32)**2)
        
        # Normalize to 0-255
        magnitude = np.clip(magnitude, 0, 255).astype(np.uint8)

        # Apply double threshold
        strong = magnitude > self.params.threshold2
        weak = (magnitude >= self.params.threshold) & ~strong

        # Simple hysteresis - connect weak edges to strong edges
        edges = strong.copy()
        
        # Dilate strong edges and intersect with weak
        for _ in range(2):
            dilated = np.zeros_like(edges)
            dilated[1:, :] |= edges[:-1, :]
            dilated[:-1, :] |= edges[1:, :]
            dilated[:, 1:] |= edges[:, :-1]
            dilated[:, :-1] |= edges[:, 1:]
            edges = edges | (dilated & weak)

        return edges.astype(np.uint8)

    def _gaussian_blur(self, arr: np.ndarray, sigma: float) -> np.ndarray:
        """Apply a simple Gaussian blur."""
        # Create a simple 5x5 Gaussian kernel
        size = 5
        x = np.arange(size) - size // 2
        kernel = np.exp(-x**2 / (2 * sigma**2))
        kernel = kernel / kernel.sum()
        
        # Apply separable convolution
        result = arr.astype(np.float32)
        
        # Horizontal pass
        for i in range(arr.shape[0]):
            result[i, :] = np.convolve(result[i, :], kernel, mode='same')
        
        # Vertical pass
        for j in range(arr.shape[1]):
            result[:, j] = np.convolve(result[:, j], kernel, mode='same')
        
        return result.astype(np.uint8)

    def _sobel_x(self, arr: np.ndarray) -> np.ndarray:
        """Apply Sobel operator in X direction."""
        kernel = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32)
        return self._convolve(arr, kernel)

    def _sobel_y(self, arr: np.ndarray) -> np.ndarray:
        """Apply Sobel operator in Y direction."""
        kernel = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]], dtype=np.float32)
        return self._convolve(arr, kernel)

    def _convolve(self, arr: np.ndarray, kernel: np.ndarray) -> np.ndarray:
        """Simple 2D convolution."""
        h, w = arr.shape
        kh, kw = kernel.shape
        ph, pw = kh // 2, kw // 2
        
        result = np.zeros_like(arr, dtype=np.float32)
        
        for i in range(ph, h - ph):
            for j in range(pw, w - pw):
                result[i, j] = np.sum(
                    arr[i-ph:i+ph+1, j-pw:j+pw+1].astype(np.float32) * kernel
                )
        
        return result

    def _trace_contours(self, edges: np.ndarray, width: int, 
                        height: int) -> List[List[EdgePoint]]:
        """
        Trace connected edge pixels into objects.
        """
        objects = []
        visited = np.zeros_like(edges, dtype=bool)
        
        # Find connected components
        for y in range(height):
            for x in range(width):
                if edges[y, x] and not visited[y, x]:
                    obj = self._trace_object(edges, visited, x, y, width, height)
                    if len(obj) >= self.params.min_length:
                        # Decimate points
                        decimated = obj[::self.params.decimate]
                        objects.append(decimated)
        
        return objects

    def _trace_object(self, edges: np.ndarray, visited: np.ndarray,
                      start_x: int, start_y: int, width: int, 
                      height: int) -> List[EdgePoint]:
        """Trace a single connected component."""
        points = []
        stack = [(start_x, start_y)]
        
        # 8-connected neighbors
        neighbors = [(-1, -1), (0, -1), (1, -1),
                     (-1, 0),           (1, 0),
                     (-1, 1),  (0, 1),  (1, 1)]
        
        while stack and len(points) < 10000:  # Limit to prevent infinite loops
            x, y = stack.pop()
            
            if x < 0 or x >= width or y < 0 or y >= height:
                continue
            if visited[y, x]:
                continue
            if not edges[y, x]:
                continue
            
            visited[y, x] = True
            
            # Normalize to -1 to 1 range
            nx = (x / width) * 2 - 1
            ny = (y / height) * 2 - 1
            points.append(EdgePoint(nx, -ny))  # Flip Y for laser coordinates
            
            # Add unvisited neighbors to stack
            for dx, dy in neighbors:
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    if edges[ny, nx] and not visited[ny, nx]:
                        stack.append((nx, ny))
        
        return points


class VideoProcessor:
    """
    Processes video frames or browser captures and converts them to laser points.
    """

    def __init__(self):
        self.tracer = EdgeTracer()
        self.renderer = LaserRenderer()
        self.params = RenderParams()
        self.trace_params = TraceParams()
        self._lock = threading.Lock()
        self._current_frame: Optional[bytes] = None
        self._frame_width = 0
        self._frame_height = 0

    def set_trace_params(self, **kwargs):
        """Update trace parameters."""
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self.trace_params, key):
                    setattr(self.trace_params, key, value)
            self.tracer = EdgeTracer(self.trace_params)

    def process_image_data(self, image_data: bytes, width: int, 
                           height: int) -> List[LaserPoint]:
        """
        Process raw image data and convert to laser points.
        
        Args:
            image_data: Raw grayscale image data
            width: Image width
            height: Image height
        
        Returns:
            List of LaserPoint for laser output
        """
        with self._lock:
            self._current_frame = image_data
            self._frame_width = width
            self._frame_height = height

            # Trace edges
            objects = self.tracer.trace(image_data, width, height)

            # Convert to laser points
            return self._objects_to_laser_points(objects)

    def process_base64_image(self, base64_data: str) -> List[LaserPoint]:
        """
        Process a base64-encoded image from browser capture.
        
        Args:
            base64_data: Base64 encoded image data (with or without data URI prefix)
        
        Returns:
            List of LaserPoint for laser output
        """
        # Remove data URI prefix if present
        if ',' in base64_data:
            base64_data = base64_data.split(',')[1]

        # Decode base64
        image_bytes = base64.b64decode(base64_data)

        # Load image with PIL
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to grayscale
        if image.mode != 'L':
            image = image.convert('L')

        # Resize if too large (for performance)
        max_dim = 320
        if image.width > max_dim or image.height > max_dim:
            ratio = min(max_dim / image.width, max_dim / image.height)
            new_size = (int(image.width * ratio), int(image.height * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)

        # Get image data
        width, height = image.size
        image_data = np.array(image)

        return self.process_image_data(image_data.tobytes(), width, height)

    def _objects_to_laser_points(self, objects: List[List[EdgePoint]]) -> List[LaserPoint]:
        """Convert traced objects to laser points."""
        self.renderer.reset()

        # Draw each traced object
        for obj in objects:
            if len(obj) < 2:
                continue

            self.renderer.begin(LaserRenderer.LINESTRIP)
            for point in obj:
                # Use white color for traced edges
                self.renderer.vertex(point.x, point.y, 0xFFFFFF)
            self.renderer.end()

        return self.renderer.render_frame()


class BrowserCaptureHandler:
    """
    Handles browser/screen capture input for realtime laser output.
    """

    def __init__(self):
        self.processor = VideoProcessor()
        self._running = False
        self._last_frame_time = 0
        self._frame_interval = 1 / 30  # 30 FPS default
        self._frame_callback: Optional[Callable[[List[LaserPoint]], None]] = None
        self._lock = threading.Lock()

    def set_frame_rate(self, fps: float):
        """Set the target frame rate."""
        self._frame_interval = 1 / max(1, min(60, fps))

    def set_trace_params(self, **kwargs):
        """Update trace parameters."""
        self.processor.set_trace_params(**kwargs)

    def set_frame_callback(self, callback: Callable[[List[LaserPoint]], None]):
        """Set callback for new frames."""
        self._frame_callback = callback

    def process_frame(self, base64_data: str) -> List[LaserPoint]:
        """
        Process a single frame from browser capture.
        
        Args:
            base64_data: Base64 encoded image data
        
        Returns:
            List of LaserPoint for laser output
        """
        current_time = time.time()
        
        # Rate limiting
        if current_time - self._last_frame_time < self._frame_interval:
            return []

        self._last_frame_time = current_time

        with self._lock:
            points = self.processor.process_base64_image(base64_data)

            if self._frame_callback and points:
                self._frame_callback(points)

            return points

    def start(self):
        """Start capture processing."""
        self._running = True
        logger.info("Browser capture handler started")

    def stop(self):
        """Stop capture processing."""
        self._running = False
        logger.info("Browser capture handler stopped")

    @property
    def is_running(self) -> bool:
        return self._running


# Global instances
_video_processor: Optional[VideoProcessor] = None
_capture_handler: Optional[BrowserCaptureHandler] = None


def get_video_processor() -> VideoProcessor:
    """Get the global video processor instance."""
    global _video_processor
    if _video_processor is None:
        _video_processor = VideoProcessor()
    return _video_processor


def get_capture_handler() -> BrowserCaptureHandler:
    """Get the global capture handler instance."""
    global _capture_handler
    if _capture_handler is None:
        _capture_handler = BrowserCaptureHandler()
    return _capture_handler
