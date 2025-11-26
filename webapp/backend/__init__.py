"""
OpenLase Web Backend Package

This package provides the web-based laser control interface with Helios DAC output.
"""

from .helios_output import HeliosDAC, LaserPoint, SimulatedHeliosDAC
from .laser_renderer import LaserRenderer, RenderParams
from .patterns import (
    PatternGenerator, get_pattern_list, create_pattern,
    RotatingCubePattern, SpiralPattern, WavePattern,
    CirclePattern, LissajousPattern, TextPattern
)
from .server import app, run_server, create_app
from .video_input import (
    VideoProcessor, BrowserCaptureHandler, EdgeTracer, TraceParams,
    get_video_processor, get_capture_handler
)
from .ilda_recorder import (
    IldaRecorder, IldaEditor, IldaWriter, IldaReader,
    IldaFile, IldaFrame, IldaPoint, IldaFormat,
    get_recorder, get_editor
)

__all__ = [
    'HeliosDAC',
    'LaserPoint',
    'SimulatedHeliosDAC',
    'LaserRenderer',
    'RenderParams',
    'PatternGenerator',
    'get_pattern_list',
    'create_pattern',
    'RotatingCubePattern',
    'SpiralPattern',
    'WavePattern',
    'CirclePattern',
    'LissajousPattern',
    'TextPattern',
    'app',
    'run_server',
    'create_app',
    # Video input
    'VideoProcessor',
    'BrowserCaptureHandler',
    'EdgeTracer',
    'TraceParams',
    'get_video_processor',
    'get_capture_handler',
    # ILDA recording
    'IldaRecorder',
    'IldaEditor',
    'IldaWriter',
    'IldaReader',
    'IldaFile',
    'IldaFrame',
    'IldaPoint',
    'IldaFormat',
    'get_recorder',
    'get_editor',
]
