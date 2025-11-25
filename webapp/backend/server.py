"""
OpenLase Web - Flask Web Server

This module provides the web server and API for the laser control interface.

Copyright (C) 2024

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 2.1 or version 3.
"""

import base64
import io
import json
import logging
import threading
import time
from typing import Dict, Any, Optional, List

from flask import Flask, render_template, jsonify, request, Response, send_file
from flask_cors import CORS

from .helios_output import HeliosDAC, LaserPoint
from .patterns import (
    PatternGenerator, get_pattern_list, create_pattern,
    RotatingCubePattern
)
from .video_input import (
    get_video_processor, get_capture_handler,
    VideoProcessor, BrowserCaptureHandler
)
from .ilda_recorder import (
    get_recorder, get_editor,
    IldaRecorder, IldaEditor, IldaFormat, IldaReader
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
DAC_POLL_INTERVAL = 0.0001  # Seconds to wait between DAC status checks
PREVIEW_FPS = 30  # Frames per second for preview stream
PREVIEW_INTERVAL = 1 / PREVIEW_FPS  # Interval between preview frames
SSE_RECONNECT_DELAY_MS = 2000  # Milliseconds before SSE reconnection

# Create Flask app
app = Flask(__name__,
            template_folder='../frontend/templates',
            static_folder='../frontend/static')
CORS(app)

# Global state
dac: Optional[HeliosDAC] = None
current_pattern: Optional[PatternGenerator] = None
running = False
frame_thread: Optional[threading.Thread] = None
frame_lock = threading.Lock()
current_frame: list = []
pps = 30000  # Points per second

# Video/Capture mode state
input_mode = 'pattern'  # 'pattern', 'video', or 'capture'
video_processor: Optional[VideoProcessor] = None
capture_handler: Optional[BrowserCaptureHandler] = None
ilda_recorder: Optional[IldaRecorder] = None
ilda_editor: Optional[IldaEditor] = None


def init_dac(simulate: bool = True) -> HeliosDAC:
    """Initialize the Helios DAC."""
    global dac
    dac = HeliosDAC(simulate=simulate)
    logger.info(f"DAC initialized (simulate={simulate})")
    return dac


def frame_generator():
    """Generate frames continuously."""
    global current_frame, running

    while running:
        if current_pattern:
            with frame_lock:
                frame = current_pattern.generate()
                current_frame = frame

            if dac and frame:
                # Wait for DAC ready
                while dac.get_status(0) != 1 and running:
                    time.sleep(DAC_POLL_INTERVAL)

                if running:
                    dac.write_frame(0, frame, pps)
        else:
            time.sleep(0.01)


def start_output():
    """Start the laser output."""
    global running, frame_thread

    if running:
        return

    running = True
    frame_thread = threading.Thread(target=frame_generator, daemon=True)
    frame_thread.start()
    logger.info("Laser output started")


def stop_output():
    """Stop the laser output."""
    global running, frame_thread

    running = False
    if frame_thread:
        frame_thread.join(timeout=1.0)
        frame_thread = None
    logger.info("Laser output stopped")


# API Routes

@app.route('/')
def index():
    """Serve the main page."""
    return render_template('index.html')


@app.route('/api/status')
def get_status():
    """Get current system status."""
    return jsonify({
        'running': running,
        'pattern': current_pattern.__class__.__name__ if current_pattern else None,
        'dac_connected': dac is not None and dac.device_count > 0,
        'simulate_mode': dac.simulate if dac else True,
        'pps': pps
    })


@app.route('/api/patterns')
def list_patterns():
    """List available patterns."""
    return jsonify(get_pattern_list())


@app.route('/api/pattern', methods=['POST'])
def set_pattern():
    """Set the current pattern."""
    global current_pattern

    data = request.json
    pattern_id = data.get('pattern')
    params = data.get('params', {})

    try:
        with frame_lock:
            current_pattern = create_pattern(pattern_id, **params)
        logger.info(f"Pattern set to: {pattern_id}")
        return jsonify({'status': 'ok', 'pattern': pattern_id})
    except Exception as e:
        logger.error(f"Failed to set pattern: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 400


@app.route('/api/start', methods=['POST'])
def api_start():
    """Start laser output."""
    start_output()
    return jsonify({'status': 'ok', 'running': True})


@app.route('/api/stop', methods=['POST'])
def api_stop():
    """Stop laser output."""
    stop_output()
    return jsonify({'status': 'ok', 'running': False})


@app.route('/api/pps', methods=['POST'])
def set_pps():
    """Set points per second."""
    global pps
    data = request.json
    new_pps = data.get('pps', 30000)
    pps = max(1000, min(65535, new_pps))
    return jsonify({'status': 'ok', 'pps': pps})


@app.route('/api/frame')
def get_frame():
    """Get the current frame data for preview."""
    with frame_lock:
        frame_data = [
            {'x': p.x, 'y': p.y, 'r': p.r, 'g': p.g, 'b': p.b}
            for p in current_frame[:1000]  # Limit for performance
        ]
    return jsonify(frame_data)


@app.route('/api/frame/stream')
def stream_frames():
    """Stream frames via Server-Sent Events."""
    def generate():
        last_frame = []
        while True:
            with frame_lock:
                if current_frame != last_frame:
                    frame_data = [
                        {'x': p.x, 'y': p.y, 'r': p.r, 'g': p.g, 'b': p.b}
                        for p in current_frame[:500]
                    ]
                    last_frame = current_frame.copy()
                    yield f"data: {json.dumps(frame_data)}\n\n"
            time.sleep(PREVIEW_INTERVAL)

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
        }
    )


# ============================================================================
# Video/Capture Input API Routes
# ============================================================================

@app.route('/api/input/mode', methods=['GET', 'POST'])
def input_mode_endpoint():
    """Get or set the input mode (pattern, video, or capture)."""
    global input_mode, video_processor, capture_handler
    
    if request.method == 'GET':
        return jsonify({
            'mode': input_mode,
            'available_modes': ['pattern', 'video', 'capture']
        })
    
    data = request.json
    new_mode = data.get('mode', 'pattern')
    
    if new_mode not in ['pattern', 'video', 'capture']:
        return jsonify({'status': 'error', 'message': 'Invalid mode'}), 400
    
    input_mode = new_mode
    
    # Initialize processors if needed
    if new_mode == 'capture' and capture_handler is None:
        capture_handler = get_capture_handler()
        capture_handler.start()
    
    if new_mode == 'video' and video_processor is None:
        video_processor = get_video_processor()
    
    logger.info(f"Input mode set to: {input_mode}")
    return jsonify({'status': 'ok', 'mode': input_mode})


@app.route('/api/input/capture/frame', methods=['POST'])
def capture_frame():
    """Process a captured frame from the browser."""
    global current_frame, capture_handler
    
    if input_mode != 'capture':
        return jsonify({'status': 'error', 'message': 'Not in capture mode'}), 400
    
    data = request.json
    image_data = data.get('image')
    
    if not image_data:
        return jsonify({'status': 'error', 'message': 'No image data'}), 400
    
    if capture_handler is None:
        capture_handler = get_capture_handler()
        capture_handler.start()
    
    try:
        # Process the frame
        points = capture_handler.process_frame(image_data)
        
        if points:
            with frame_lock:
                current_frame = points
            
            # Record if recording is active
            if ilda_recorder and ilda_recorder.is_recording:
                ilda_recorder.record_frame(points)
            
            # Send to DAC if running
            if running and dac and points:
                while dac.get_status(0) != 1:
                    time.sleep(DAC_POLL_INTERVAL)
                dac.write_frame(0, points, pps)
        
        return jsonify({
            'status': 'ok',
            'points': len(points) if points else 0
        })
    except Exception as e:
        logger.error(f"Failed to process capture frame: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/input/capture/params', methods=['GET', 'POST'])
def capture_params():
    """Get or set capture/trace parameters."""
    global capture_handler
    
    if capture_handler is None:
        capture_handler = get_capture_handler()
    
    if request.method == 'GET':
        params = capture_handler.processor.trace_params
        return jsonify({
            'threshold': params.threshold,
            'threshold2': params.threshold2,
            'min_length': params.min_length,
            'decimate': params.decimate,
            'blur_sigma': params.blur_sigma,
            'use_canny': params.use_canny,
            'invert': params.invert
        })
    
    data = request.json
    capture_handler.set_trace_params(**data)
    logger.info(f"Capture params updated: {data}")
    return jsonify({'status': 'ok'})


# ============================================================================
# ILDA Recording API Routes
# ============================================================================

@app.route('/api/record/start', methods=['POST'])
def start_recording():
    """Start ILDA recording."""
    global ilda_recorder
    
    data = request.json or {}
    name = data.get('name', 'Recording')
    
    ilda_recorder = get_recorder()
    ilda_recorder.start(name=name)
    
    return jsonify({
        'status': 'ok',
        'recording': True,
        'name': name
    })


@app.route('/api/record/stop', methods=['POST'])
def stop_recording():
    """Stop ILDA recording and return file info."""
    global ilda_recorder
    
    if not ilda_recorder or not ilda_recorder.is_recording:
        return jsonify({'status': 'error', 'message': 'Not recording'}), 400
    
    ilda_file = ilda_recorder.stop()
    
    return jsonify({
        'status': 'ok',
        'recording': False,
        'frame_count': ilda_file.frame_count,
        'total_points': ilda_file.total_points,
        'duration': ilda_recorder.duration
    })


@app.route('/api/record/status')
def recording_status():
    """Get current recording status."""
    global ilda_recorder
    
    if not ilda_recorder:
        return jsonify({
            'recording': False,
            'frame_count': 0,
            'duration': 0
        })
    
    return jsonify({
        'recording': ilda_recorder.is_recording,
        'frame_count': ilda_recorder.ilda_file.frame_count if ilda_recorder.ilda_file else 0,
        'duration': ilda_recorder.duration
    })


@app.route('/api/record/download')
def download_recording():
    """Download the recorded ILDA file."""
    global ilda_recorder
    
    if not ilda_recorder or ilda_recorder.ilda_file.frame_count == 0:
        return jsonify({'status': 'error', 'message': 'No recording available'}), 400
    
    format_str = request.args.get('format', '2d_rgb')
    format_map = {
        '2d_indexed': IldaFormat.FORMAT_2D_INDEXED,
        '2d_rgb': IldaFormat.FORMAT_2D_RGB,
        '3d_rgb': IldaFormat.FORMAT_3D_RGB
    }
    
    ilda_format = format_map.get(format_str, IldaFormat.FORMAT_2D_RGB)
    data = ilda_recorder.export(ilda_format)
    
    return send_file(
        io.BytesIO(data),
        mimetype='application/octet-stream',
        as_attachment=True,
        download_name=f'{ilda_recorder.ilda_file.name or "recording"}.ild'
    )


# ============================================================================
# ILDA Editor API Routes
# ============================================================================

@app.route('/api/editor/load', methods=['POST'])
def editor_load():
    """Load an ILDA file into the editor."""
    global ilda_editor
    
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file provided'}), 400
    
    file = request.files['file']
    data = file.read()
    
    ilda_editor = get_editor()
    success = ilda_editor.load(data)
    
    if success:
        return jsonify({
            'status': 'ok',
            'info': ilda_editor.get_info()
        })
    else:
        return jsonify({'status': 'error', 'message': 'Failed to load file'}), 400


@app.route('/api/editor/load-recording', methods=['POST'])
def editor_load_recording():
    """Load the current recording into the editor."""
    global ilda_editor, ilda_recorder
    
    if not ilda_recorder or ilda_recorder.ilda_file.frame_count == 0:
        return jsonify({'status': 'error', 'message': 'No recording available'}), 400
    
    ilda_editor = get_editor()
    ilda_editor.load_file(ilda_recorder.ilda_file)
    
    return jsonify({
        'status': 'ok',
        'info': ilda_editor.get_info()
    })


@app.route('/api/editor/info')
def editor_info():
    """Get information about the loaded file."""
    global ilda_editor
    
    if not ilda_editor or not ilda_editor.ilda_file:
        return jsonify({'status': 'error', 'message': 'No file loaded'}), 400
    
    return jsonify(ilda_editor.get_info())


@app.route('/api/editor/frame/<int:frame_index>')
def editor_frame(frame_index):
    """Get a frame preview."""
    global ilda_editor
    
    if not ilda_editor or not ilda_editor.ilda_file:
        return jsonify({'status': 'error', 'message': 'No file loaded'}), 400
    
    points = ilda_editor.get_frame_preview(frame_index)
    frame_data = [
        {'x': p.x, 'y': p.y, 'r': p.r, 'g': p.g, 'b': p.b}
        for p in points
    ]
    
    return jsonify(frame_data)


@app.route('/api/editor/frame/<int:frame_index>/delete', methods=['POST'])
def editor_delete_frame(frame_index):
    """Delete a frame."""
    global ilda_editor
    
    if not ilda_editor or not ilda_editor.ilda_file:
        return jsonify({'status': 'error', 'message': 'No file loaded'}), 400
    
    success = ilda_editor.delete_frame(frame_index)
    return jsonify({
        'status': 'ok' if success else 'error',
        'info': ilda_editor.get_info()
    })


@app.route('/api/editor/frame/<int:frame_index>/duplicate', methods=['POST'])
def editor_duplicate_frame(frame_index):
    """Duplicate a frame."""
    global ilda_editor
    
    if not ilda_editor or not ilda_editor.ilda_file:
        return jsonify({'status': 'error', 'message': 'No file loaded'}), 400
    
    success = ilda_editor.duplicate_frame(frame_index)
    return jsonify({
        'status': 'ok' if success else 'error',
        'info': ilda_editor.get_info()
    })


@app.route('/api/editor/transform', methods=['POST'])
def editor_transform():
    """Apply transformations to the file."""
    global ilda_editor
    
    if not ilda_editor or not ilda_editor.ilda_file:
        return jsonify({'status': 'error', 'message': 'No file loaded'}), 400
    
    data = request.json
    operation = data.get('operation')
    
    if operation == 'scale':
        ilda_editor.scale(data.get('scale_x', 1.0), data.get('scale_y', 1.0))
    elif operation == 'translate':
        ilda_editor.translate(data.get('offset_x', 0), data.get('offset_y', 0))
    elif operation == 'rotate':
        ilda_editor.rotate(data.get('angle', 0))
    elif operation == 'invert_colors':
        ilda_editor.invert_colors()
    elif operation == 'set_color':
        ilda_editor.set_color(data.get('r', 255), data.get('g', 255), data.get('b', 255))
    elif operation == 'trim':
        ilda_editor.trim(data.get('start', 0), data.get('end', 0))
    else:
        return jsonify({'status': 'error', 'message': 'Unknown operation'}), 400
    
    return jsonify({
        'status': 'ok',
        'info': ilda_editor.get_info()
    })


@app.route('/api/editor/undo', methods=['POST'])
def editor_undo():
    """Undo the last edit."""
    global ilda_editor
    
    if not ilda_editor:
        return jsonify({'status': 'error', 'message': 'No file loaded'}), 400
    
    success = ilda_editor.undo()
    return jsonify({
        'status': 'ok' if success else 'error',
        'message': 'Nothing to undo' if not success else None,
        'info': ilda_editor.get_info() if ilda_editor.ilda_file else {}
    })


@app.route('/api/editor/download')
def editor_download():
    """Download the edited ILDA file."""
    global ilda_editor
    
    if not ilda_editor or not ilda_editor.ilda_file:
        return jsonify({'status': 'error', 'message': 'No file loaded'}), 400
    
    format_str = request.args.get('format', '2d_rgb')
    format_map = {
        '2d_indexed': IldaFormat.FORMAT_2D_INDEXED,
        '2d_rgb': IldaFormat.FORMAT_2D_RGB,
        '3d_rgb': IldaFormat.FORMAT_3D_RGB
    }
    
    ilda_format = format_map.get(format_str, IldaFormat.FORMAT_2D_RGB)
    data = ilda_editor.export(ilda_format)
    
    if not data:
        return jsonify({'status': 'error', 'message': 'Export failed'}), 500
    
    return send_file(
        io.BytesIO(data),
        mimetype='application/octet-stream',
        as_attachment=True,
        download_name=f'{ilda_editor.ilda_file.name or "edited"}.ild'
    )


@app.route('/api/editor/play/<int:frame_index>', methods=['POST'])
def editor_play_frame(frame_index):
    """Play a frame from the editor on the laser."""
    global ilda_editor, current_frame
    
    if not ilda_editor or not ilda_editor.ilda_file:
        return jsonify({'status': 'error', 'message': 'No file loaded'}), 400
    
    points = ilda_editor.get_frame_preview(frame_index)
    
    if points:
        with frame_lock:
            current_frame = points
        
        if running and dac:
            while dac.get_status(0) != 1:
                time.sleep(DAC_POLL_INTERVAL)
            dac.write_frame(0, points, pps)
    
    return jsonify({
        'status': 'ok',
        'points': len(points)
    })


def create_app(simulate: bool = True) -> Flask:
    """Create and configure the Flask app."""
    global current_pattern

    init_dac(simulate=simulate)
    current_pattern = RotatingCubePattern()
    return app


def run_server(host: str = '0.0.0.0', port: int = 5000, 
               simulate: bool = True, debug: bool = False):
    """Run the web server."""
    create_app(simulate=simulate)
    start_output()

    try:
        app.run(host=host, port=port, debug=debug, threaded=True)
    finally:
        stop_output()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='OpenLase Web Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to listen on')
    parser.add_argument('--hardware', action='store_true',
                        help='Use real hardware instead of simulation')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')

    args = parser.parse_args()
    run_server(
        host=args.host,
        port=args.port,
        simulate=not args.hardware,
        debug=args.debug
    )
