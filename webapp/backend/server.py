"""
OpenLase Web - Flask Web Server

This module provides the web server and API for the laser control interface.

Copyright (C) 2024

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 2.1 or version 3.
"""

import json
import logging
import threading
import time
from typing import Dict, Any, Optional

from flask import Flask, render_template, jsonify, request, Response
from flask_cors import CORS

from .helios_output import HeliosDAC, LaserPoint
from .patterns import (
    PatternGenerator, get_pattern_list, create_pattern,
    RotatingCubePattern
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
