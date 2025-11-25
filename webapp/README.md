# OpenLase Web

A web-based laser control interface for the OpenLase laser graphics toolkit, with support for the Helios DAC as output for RGB lasers.

## Features

- **Web Interface**: Control your laser from any browser
- **Pattern Generator**: Multiple built-in patterns (rotating cube, spirals, waves, Lissajous curves, text)
- **Real-time Preview**: See what your laser is projecting in the browser
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

- `GET /api/status` - Get current system status
- `GET /api/patterns` - List available patterns
- `POST /api/pattern` - Set the current pattern
- `POST /api/start` - Start laser output
- `POST /api/stop` - Stop laser output
- `POST /api/pps` - Set points per second
- `GET /api/frame` - Get current frame data
- `GET /api/frame/stream` - Server-sent events for real-time preview

## Available Patterns

1. **Rotating Cube** - A colorful 3D rotating cube
2. **Spiral** - Animated multi-arm spiral
3. **Wave** - Animated sine waves
4. **Circle** - Simple rotating circle
5. **Lissajous** - Lissajous curve patterns
6. **Text** - Animated text display

## Architecture

```
webapp/
├── backend/
│   ├── __init__.py          # Package exports
│   ├── helios_output.py     # Helios DAC interface
│   ├── laser_renderer.py    # OpenLase-compatible renderer
│   ├── patterns.py          # Pattern generators
│   └── server.py            # Flask web server
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
