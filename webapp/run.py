#!/usr/bin/env python3
"""
OpenLase Web - Main Entry Point

Run the OpenLase Web application with Helios DAC output.

Usage:
    python run.py [--port PORT] [--hardware] [--debug]

Options:
    --port PORT     Port to run on (default: 5000)
    --hardware      Use real Helios DAC hardware instead of simulation
    --debug         Enable debug mode
"""

import sys
import os

# Add the webapp directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.server import run_server


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='OpenLase Web - Laser Control Interface',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run.py                    # Run in simulation mode on port 5000
    python run.py --port 8080        # Run on port 8080
    python run.py --hardware         # Use real Helios DAC hardware
    python run.py --debug            # Enable debug mode
        """
    )
    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='Host to bind to (default: 0.0.0.0)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='Port to listen on (default: 5000)'
    )
    parser.add_argument(
        '--hardware',
        action='store_true',
        help='Use real Helios DAC hardware instead of simulation'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode'
    )

    args = parser.parse_args()

    print("""
╔═══════════════════════════════════════════════════════════╗
║                    OpenLase Web                            ║
║            Laser Control Interface with Helios DAC         ║
╚═══════════════════════════════════════════════════════════╝
""")
    print(f"Starting server on http://{args.host}:{args.port}")
    print(f"Mode: {'Hardware' if args.hardware else 'Simulation'}")
    print(f"Debug: {'Enabled' if args.debug else 'Disabled'}")
    print("\nPress Ctrl+C to stop\n")

    try:
        run_server(
            host=args.host,
            port=args.port,
            simulate=not args.hardware,
            debug=args.debug
        )
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == '__main__':
    main()
