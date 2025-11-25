# OpenLase Web

A web-based laser control interface for the OpenLase laser graphics toolkit, with support for the Helios DAC as output for RGB lasers.

## Features

- **Web Interface**: Control your laser from any browser
- **Pattern Generator**: Multiple built-in patterns (rotating cube, spirals, waves, Lissajous curves, text)
- **Real-time Preview**: See what your laser is projecting in the browser
- **Video/Screen Capture**: Convert video from webcam or screen capture to realtime laser output
- **Edge Detection**: Canny and threshold-based edge detection for video input
- **ILDA Recording**: Record laser output to standard ILDA format
- **ILDA Editor**: Load, edit, and export ILDA files with transformations
- **Helios DAC Support**: Direct output to Helios DAC hardware
- **Simulation Mode**: Test patterns without hardware

## Requirements

- Python 3.8+
- Flask and dependencies (see requirements.txt)
- For hardware mode: Helios DAC and libHeliosDacAPI

## Installation

1. Install Python dependencies:

```bash
cd webapp
pip install -r requirements.txt
```

2. (Optional) For hardware mode, install the Helios DAC SDK and place the shared library in a standard location.

## Usage

### Simulation Mode (no hardware required)

```bash
cd webapp
python run.py
```

Open your browser to `http://localhost:5000`

### Hardware Mode

```bash
cd webapp
python run.py --hardware
```

### Command Line Options

```
--host HOST     Host to bind to (default: 0.0.0.0)
--port PORT     Port to listen on (default: 5000)
--hardware      Use real Helios DAC hardware instead of simulation
--debug         Enable debug mode
```

## Web API

The web interface communicates with the backend via a REST API:

### Core API
- `GET /api/status` - Get current system status
- `GET /api/patterns` - List available patterns
- `POST /api/pattern` - Set the current pattern
- `POST /api/start` - Start laser output
- `POST /api/stop` - Stop laser output
- `POST /api/pps` - Set points per second
- `GET /api/frame` - Get current frame data
- `GET /api/frame/stream` - Server-sent events for real-time preview

### Video/Capture API
- `GET/POST /api/input/mode` - Get or set input mode (pattern, video, capture)
- `POST /api/input/capture/frame` - Process a captured frame from browser
- `GET/POST /api/input/capture/params` - Get or set edge detection parameters

### Recording API
- `POST /api/record/start` - Start ILDA recording
- `POST /api/record/stop` - Stop ILDA recording
- `GET /api/record/status` - Get recording status
- `GET /api/record/download` - Download recorded ILDA file

### Editor API
- `POST /api/editor/load` - Load an ILDA file
- `POST /api/editor/load-recording` - Load current recording into editor
- `GET /api/editor/info` - Get file information
- `GET /api/editor/frame/<index>` - Get frame preview
- `POST /api/editor/frame/<index>/delete` - Delete a frame
- `POST /api/editor/frame/<index>/duplicate` - Duplicate a frame
- `POST /api/editor/transform` - Apply transformations (scale, rotate, color)
- `POST /api/editor/undo` - Undo last edit
- `GET /api/editor/download` - Download edited ILDA file
- `POST /api/editor/play/<index>` - Play a frame on the laser

## Available Patterns

1. **Rotating Cube** - A colorful 3D rotating cube
2. **Spiral** - Animated multi-arm spiral
3. **Wave** - Animated sine waves
4. **Circle** - Simple rotating circle
5. **Lissajous** - Lissajous curve patterns
6. **Text** - Animated text display

## Video/Capture Input

The application supports realtime laser output from:

1. **Webcam** - Use your webcam as input
2. **Screen Capture** - Capture your screen or a window

### Edge Detection Settings

- **Threshold** - Lower threshold for edge detection
- **Threshold 2** - Upper threshold for Canny edge detection
- **Blur** - Gaussian blur sigma for noise reduction
- **Decimate** - Point decimation factor
- **Use Canny** - Toggle between Canny and simple threshold detection
- **Invert Edges** - Invert the detected edges

## ILDA Recording

Record your laser output to standard ILDA format:

1. Click "Record" to start recording
2. All frames sent to the laser will be captured
3. Click "Stop" to stop recording
4. Click "Download Recording" to save as .ild file

## ILDA Editor

Edit ILDA files with the built-in editor:

1. Click "Load ILDA" to load a file, or "Load Recording" to edit your recording
2. Browse frames in the frame list
3. Click frames to preview them
4. Use transformation buttons to modify:
   - **Scale** - Scale the entire file
   - **Rotate** - Rotate all points
   - **Color** - Set a uniform color
   - **Undo** - Undo the last change
5. Delete or duplicate individual frames
6. Click "Download" to save your edited file

## Architecture

```
webapp/
├── backend/
│   ├── __init__.py          # Package exports
│   ├── helios_output.py     # Helios DAC interface
│   ├── laser_renderer.py    # OpenLase-compatible renderer
│   ├── patterns.py          # Pattern generators
│   ├── server.py            # Flask web server
│   ├── video_input.py       # Video/capture processing
│   └── ilda_recorder.py     # ILDA recording and editing
├── frontend/
│   ├── templates/
│   │   └── index.html       # Main HTML template
│   └── static/
│       ├── css/
│       │   └── style.css    # Styles
│       └── js/
│           └── app.js       # Frontend JavaScript
├── requirements.txt         # Python dependencies
├── run.py                   # Main entry point
└── README.md               # This file
```

## Safety Notes

⚠️ **WARNING**: Lasers can cause permanent eye damage and skin burns.

- Always follow laser safety protocols
- Never aim lasers at people, animals, or aircraft
- Use appropriate safety eyewear
- Ensure proper interlock systems are in place
- Only operate lasers in controlled environments

## License

This software is part of the OpenLase project and is distributed under the GNU Lesser General Public License (LGPL).

## Credits

- Based on [OpenLase](https://github.com/marcan/openlase) by Hector Martin
- Helios DAC support based on the [Helios DAC SDK](https://github.com/Grix/helios_dac)
