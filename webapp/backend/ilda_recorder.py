"""
OpenLase Web - ILDA Recorder and Editor Module

This module provides ILDA file recording and editing capabilities
for the web interface.

Copyright (C) 2024

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 2.1 or version 3.
"""

import io
import logging
import struct
import time
import threading
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum

from .helios_output import LaserPoint

logger = logging.getLogger(__name__)


class IldaFormat(Enum):
    """ILDA file format types."""
    FORMAT_3D_INDEXED = 0  # 3D coordinates with color index
    FORMAT_2D_INDEXED = 1  # 2D coordinates with color index
    FORMAT_COLOR_PALETTE = 2  # Color palette
    FORMAT_3D_RGB = 4  # 3D coordinates with RGB color
    FORMAT_2D_RGB = 5  # 2D coordinates with RGB color


@dataclass
class IldaPoint:
    """Represents a single ILDA point."""
    x: int  # -32768 to 32767
    y: int  # -32768 to 32767
    z: int = 0  # -32768 to 32767 (3D only)
    r: int = 255  # 0-255
    g: int = 255  # 0-255
    b: int = 255  # 0-255
    is_blank: bool = False
    is_last: bool = False

    @classmethod
    def from_laser_point(cls, point: LaserPoint) -> 'IldaPoint':
        """Convert a LaserPoint to IldaPoint."""
        # Convert from Helios coordinates (0-4095) to ILDA (-32768 to 32767)
        x = int((point.x / 4095.0) * 65535 - 32768)
        y = int((point.y / 4095.0) * 65535 - 32768)
        
        # Clamp values
        x = max(-32768, min(32767, x))
        y = max(-32768, min(32767, y))
        
        # Determine if blanked (all colors zero)
        is_blank = point.r == 0 and point.g == 0 and point.b == 0
        
        return cls(
            x=x,
            y=y,
            z=0,
            r=point.r,
            g=point.g,
            b=point.b,
            is_blank=is_blank
        )

    def to_laser_point(self) -> LaserPoint:
        """Convert to LaserPoint for playback."""
        # Convert from ILDA (-32768 to 32767) to Helios (0-4095)
        hx = int(((self.x + 32768) / 65535.0) * 4095)
        hy = int(((self.y + 32768) / 65535.0) * 4095)
        
        hx = max(0, min(4095, hx))
        hy = max(0, min(4095, hy))
        
        return LaserPoint(
            x=hx,
            y=hy,
            r=0 if self.is_blank else self.r,
            g=0 if self.is_blank else self.g,
            b=0 if self.is_blank else self.b
        )


@dataclass
class IldaFrame:
    """Represents a single ILDA frame."""
    points: List[IldaPoint] = field(default_factory=list)
    name: str = ""
    company: str = "OpenLase"
    
    def add_point(self, point: IldaPoint):
        """Add a point to the frame."""
        self.points.append(point)

    def clear(self):
        """Clear all points."""
        self.points = []

    @property
    def point_count(self) -> int:
        return len(self.points)


@dataclass
class IldaFile:
    """Represents an ILDA file with multiple frames."""
    frames: List[IldaFrame] = field(default_factory=list)
    name: str = "OpenLase Recording"
    company: str = "OpenLase"

    def add_frame(self, frame: IldaFrame):
        """Add a frame to the file."""
        self.frames.append(frame)

    def clear(self):
        """Clear all frames."""
        self.frames = []

    @property
    def frame_count(self) -> int:
        return len(self.frames)

    @property
    def total_points(self) -> int:
        return sum(f.point_count for f in self.frames)


class IldaWriter:
    """Writes ILDA files in standard format."""

    MAGIC = b'ILDA'

    def __init__(self, format_type: IldaFormat = IldaFormat.FORMAT_2D_RGB):
        self.format_type = format_type

    def write(self, ilda_file: IldaFile) -> bytes:
        """
        Write an ILDA file to bytes.
        
        Args:
            ilda_file: The ILDA file to write
        
        Returns:
            Bytes containing the ILDA file data
        """
        output = io.BytesIO()
        
        total_frames = len(ilda_file.frames)
        
        for frame_num, frame in enumerate(ilda_file.frames):
            self._write_frame(output, frame, frame_num, total_frames, ilda_file)
        
        # Write terminating header (zero-point frame)
        self._write_header(
            output,
            format_type=self.format_type.value,
            name=ilda_file.name,
            company=ilda_file.company,
            point_count=0,
            frame_number=total_frames,
            total_frames=total_frames,
            scanner=0
        )
        
        return output.getvalue()

    def _write_header(self, output: io.BytesIO, format_type: int, name: str,
                      company: str, point_count: int, frame_number: int,
                      total_frames: int, scanner: int):
        """Write an ILDA section header."""
        # Pad name and company to 8 characters
        name_bytes = name[:8].ljust(8).encode('ascii', errors='replace')
        company_bytes = company[:8].ljust(8).encode('ascii', errors='replace')
        
        # Pack header (32 bytes total)
        header = struct.pack(
            '>4s3xB8s8sHHHBx',  # Big-endian
            self.MAGIC,
            format_type,
            name_bytes,
            company_bytes,
            point_count,
            frame_number,
            total_frames,
            scanner
        )
        
        output.write(header)

    def _write_frame(self, output: io.BytesIO, frame: IldaFrame,
                     frame_number: int, total_frames: int, ilda_file: IldaFile):
        """Write a single frame."""
        # Write header
        self._write_header(
            output,
            format_type=self.format_type.value,
            name=frame.name or ilda_file.name,
            company=frame.company or ilda_file.company,
            point_count=len(frame.points),
            frame_number=frame_number,
            total_frames=total_frames,
            scanner=0
        )
        
        # Write points
        for i, point in enumerate(frame.points):
            is_last = (i == len(frame.points) - 1)
            self._write_point(output, point, is_last)

    def _write_point(self, output: io.BytesIO, point: IldaPoint, is_last: bool):
        """Write a single point in the current format."""
        if self.format_type == IldaFormat.FORMAT_2D_RGB:
            # Format 5: 2D with RGB color (8 bytes per point)
            status = 0
            if point.is_blank:
                status |= 0x40  # Blanking bit
            if is_last:
                status |= 0x80  # Last point bit
            
            point_data = struct.pack(
                '>hhBBBB',  # Big-endian: x, y, status, r, g, b
                point.x,
                point.y,
                status,
                point.b,  # ILDA uses BGR order
                point.g,
                point.r
            )
            output.write(point_data)
            
        elif self.format_type == IldaFormat.FORMAT_3D_RGB:
            # Format 4: 3D with RGB color (10 bytes per point)
            status = 0
            if point.is_blank:
                status |= 0x40
            if is_last:
                status |= 0x80
            
            point_data = struct.pack(
                '>hhhBBBB',  # Big-endian: x, y, z, status, r, g, b
                point.x,
                point.y,
                point.z,
                status,
                point.b,
                point.g,
                point.r
            )
            output.write(point_data)
            
        elif self.format_type == IldaFormat.FORMAT_2D_INDEXED:
            # Format 1: 2D with color index (6 bytes per point)
            status = 0
            if point.is_blank:
                status |= 0x40
            if is_last:
                status |= 0x80
            
            # Simple color to index mapping (use brightness as index)
            color_index = max(point.r, point.g, point.b) // 4
            
            point_data = struct.pack(
                '>hhBB',  # Big-endian: x, y, status, color
                point.x,
                point.y,
                status,
                color_index
            )
            output.write(point_data)


class IldaReader:
    """Reads ILDA files."""

    MAGIC = 0x494C4441  # 'ILDA' in big-endian

    # Default color palette
    DEFAULT_PALETTE = [
        (255, 0, 0), (255, 127, 0), (255, 255, 0), (127, 255, 0),
        (0, 255, 0), (0, 255, 127), (0, 255, 255), (0, 127, 255),
        (0, 0, 255), (127, 0, 255), (255, 0, 255), (255, 0, 127),
        (255, 255, 255), (191, 191, 191), (127, 127, 127), (63, 63, 63)
    ]

    def __init__(self):
        self.palette = list(self.DEFAULT_PALETTE)

    def read(self, data: bytes) -> IldaFile:
        """
        Read an ILDA file from bytes.
        
        Args:
            data: Raw ILDA file data
        
        Returns:
            Parsed IldaFile object
        """
        stream = io.BytesIO(data)
        ilda_file = IldaFile()
        
        while True:
            frame = self._read_section(stream)
            if frame is None:
                break
            if frame.point_count > 0:
                ilda_file.add_frame(frame)
        
        return ilda_file

    def _read_section(self, stream: io.BytesIO) -> Optional[IldaFrame]:
        """Read a single ILDA section."""
        header_data = stream.read(32)
        if len(header_data) < 32:
            return None
        
        # Parse header
        magic = struct.unpack('>I', header_data[0:4])[0]
        if magic != self.MAGIC:
            logger.error(f"Invalid ILDA magic: {magic:#x}")
            return None
        
        format_type = header_data[7]
        name = header_data[8:16].decode('ascii', errors='replace').strip()
        company = header_data[16:24].decode('ascii', errors='replace').strip()
        point_count = struct.unpack('>H', header_data[24:26])[0]
        frame_number = struct.unpack('>H', header_data[26:28])[0]
        total_frames = struct.unpack('>H', header_data[28:30])[0]
        
        if point_count == 0:
            return None
        
        frame = IldaFrame(name=name, company=company)
        
        # Read points based on format
        if format_type == 0:  # 3D indexed
            for _ in range(point_count):
                point_data = stream.read(8)
                if len(point_data) < 8:
                    break
                x, y, z, status, color = struct.unpack('>hhhBB', point_data)
                r, g, b = self._get_color(color)
                frame.add_point(IldaPoint(
                    x=x, y=y, z=z, r=r, g=g, b=b,
                    is_blank=bool(status & 0x40),
                    is_last=bool(status & 0x80)
                ))
                
        elif format_type == 1:  # 2D indexed
            for _ in range(point_count):
                point_data = stream.read(6)
                if len(point_data) < 6:
                    break
                x, y, status, color = struct.unpack('>hhBB', point_data)
                r, g, b = self._get_color(color)
                frame.add_point(IldaPoint(
                    x=x, y=y, z=0, r=r, g=g, b=b,
                    is_blank=bool(status & 0x40),
                    is_last=bool(status & 0x80)
                ))
                
        elif format_type == 2:  # Color palette
            for _ in range(point_count):
                color_data = stream.read(3)
                if len(color_data) < 3:
                    break
                r, g, b = color_data
                if len(self.palette) < 256:
                    self.palette.append((r, g, b))
            return IldaFrame()  # Return empty frame for palette
            
        elif format_type == 4:  # 3D RGB
            for _ in range(point_count):
                point_data = stream.read(10)
                if len(point_data) < 10:
                    break
                x, y, z, status, b, g, r = struct.unpack('>hhhBBBB', point_data)
                frame.add_point(IldaPoint(
                    x=x, y=y, z=z, r=r, g=g, b=b,
                    is_blank=bool(status & 0x40),
                    is_last=bool(status & 0x80)
                ))
                
        elif format_type == 5:  # 2D RGB
            for _ in range(point_count):
                point_data = stream.read(8)
                if len(point_data) < 8:
                    break
                x, y, status, b, g, r = struct.unpack('>hhBBBB', point_data)
                frame.add_point(IldaPoint(
                    x=x, y=y, z=0, r=r, g=g, b=b,
                    is_blank=bool(status & 0x40),
                    is_last=bool(status & 0x80)
                ))
        
        return frame

    def _get_color(self, index: int) -> Tuple[int, int, int]:
        """Get RGB color from palette index."""
        if index < len(self.palette):
            return self.palette[index]
        # Return white for out-of-range indices
        return (255, 255, 255)


class IldaRecorder:
    """
    Records laser frames to ILDA format.
    """

    def __init__(self, max_frames: int = 3600):
        self.ilda_file = IldaFile()
        self.max_frames = max_frames
        self.is_recording = False
        self._lock = threading.Lock()
        self._start_time: Optional[float] = None
        self._frame_count = 0

    def start(self, name: str = "Recording"):
        """Start recording."""
        with self._lock:
            self.ilda_file = IldaFile(name=name)
            self.is_recording = True
            self._start_time = time.time()
            self._frame_count = 0
            logger.info(f"Started recording: {name}")

    def stop(self) -> IldaFile:
        """Stop recording and return the recorded file."""
        with self._lock:
            self.is_recording = False
            result = self.ilda_file
            duration = time.time() - self._start_time if self._start_time else 0
            logger.info(f"Stopped recording: {result.frame_count} frames, "
                       f"{result.total_points} points, {duration:.1f}s")
            return result

    def record_frame(self, points: List[LaserPoint]) -> bool:
        """
        Record a single frame.
        
        Args:
            points: List of LaserPoint to record
        
        Returns:
            True if frame was recorded, False if recording is full
        """
        if not self.is_recording:
            return False
        
        with self._lock:
            if self._frame_count >= self.max_frames:
                return False
            
            frame = IldaFrame()
            for point in points:
                frame.add_point(IldaPoint.from_laser_point(point))
            
            self.ilda_file.add_frame(frame)
            self._frame_count += 1
            
            return True

    def export(self, format_type: IldaFormat = IldaFormat.FORMAT_2D_RGB) -> bytes:
        """Export the recorded file as bytes."""
        with self._lock:
            writer = IldaWriter(format_type)
            return writer.write(self.ilda_file)

    @property
    def duration(self) -> float:
        """Get recording duration in seconds."""
        if self._start_time is None:
            return 0
        return time.time() - self._start_time


class IldaEditor:
    """
    Simple ILDA file editor for modifying recordings.
    """

    def __init__(self):
        self.ilda_file: Optional[IldaFile] = None
        self._history: List[IldaFile] = []
        self._max_history = 20

    def load(self, data: bytes) -> bool:
        """Load an ILDA file from bytes."""
        try:
            reader = IldaReader()
            self.ilda_file = reader.read(data)
            self._save_history()
            return True
        except Exception as e:
            logger.error(f"Failed to load ILDA file: {e}")
            return False

    def load_file(self, ilda_file: IldaFile):
        """Load an existing IldaFile object."""
        self.ilda_file = ilda_file
        self._save_history()

    def _save_history(self):
        """Save current state to history for undo."""
        if self.ilda_file:
            # Deep copy
            history_entry = IldaFile(
                name=self.ilda_file.name,
                company=self.ilda_file.company
            )
            for frame in self.ilda_file.frames:
                new_frame = IldaFrame(
                    name=frame.name,
                    company=frame.company,
                    points=list(frame.points)
                )
                history_entry.add_frame(new_frame)
            
            self._history.append(history_entry)
            if len(self._history) > self._max_history:
                self._history.pop(0)

    def undo(self) -> bool:
        """Undo the last edit."""
        if len(self._history) > 1:
            self._history.pop()  # Remove current state
            self.ilda_file = self._history[-1]
            return True
        return False

    def delete_frame(self, frame_index: int) -> bool:
        """Delete a frame at the specified index."""
        if self.ilda_file and 0 <= frame_index < len(self.ilda_file.frames):
            self._save_history()
            self.ilda_file.frames.pop(frame_index)
            return True
        return False

    def duplicate_frame(self, frame_index: int) -> bool:
        """Duplicate a frame at the specified index."""
        if self.ilda_file and 0 <= frame_index < len(self.ilda_file.frames):
            self._save_history()
            frame = self.ilda_file.frames[frame_index]
            new_frame = IldaFrame(
                name=frame.name,
                company=frame.company,
                points=list(frame.points)
            )
            self.ilda_file.frames.insert(frame_index + 1, new_frame)
            return True
        return False

    def move_frame(self, from_index: int, to_index: int) -> bool:
        """Move a frame from one index to another."""
        if self.ilda_file:
            if (0 <= from_index < len(self.ilda_file.frames) and 
                0 <= to_index < len(self.ilda_file.frames)):
                self._save_history()
                frame = self.ilda_file.frames.pop(from_index)
                self.ilda_file.frames.insert(to_index, frame)
                return True
        return False

    def trim(self, start_frame: int, end_frame: int) -> bool:
        """Trim the file to include only frames in the specified range."""
        if self.ilda_file:
            if (0 <= start_frame < len(self.ilda_file.frames) and
                start_frame <= end_frame < len(self.ilda_file.frames)):
                self._save_history()
                self.ilda_file.frames = self.ilda_file.frames[start_frame:end_frame + 1]
                return True
        return False

    def scale(self, scale_x: float, scale_y: float):
        """Scale all points in all frames."""
        if not self.ilda_file:
            return
        
        self._save_history()
        for frame in self.ilda_file.frames:
            for point in frame.points:
                point.x = max(-32768, min(32767, int(point.x * scale_x)))
                point.y = max(-32768, min(32767, int(point.y * scale_y)))

    def translate(self, offset_x: int, offset_y: int):
        """Translate all points in all frames."""
        if not self.ilda_file:
            return
        
        self._save_history()
        for frame in self.ilda_file.frames:
            for point in frame.points:
                point.x = max(-32768, min(32767, point.x + offset_x))
                point.y = max(-32768, min(32767, point.y + offset_y))

    def rotate(self, angle_degrees: float):
        """Rotate all points in all frames around the center."""
        if not self.ilda_file:
            return
        
        import math
        self._save_history()
        angle_rad = math.radians(angle_degrees)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        
        for frame in self.ilda_file.frames:
            for point in frame.points:
                new_x = point.x * cos_a - point.y * sin_a
                new_y = point.x * sin_a + point.y * cos_a
                point.x = max(-32768, min(32767, int(new_x)))
                point.y = max(-32768, min(32767, int(new_y)))

    def invert_colors(self):
        """Invert colors in all frames."""
        if not self.ilda_file:
            return
        
        self._save_history()
        for frame in self.ilda_file.frames:
            for point in frame.points:
                point.r = 255 - point.r
                point.g = 255 - point.g
                point.b = 255 - point.b

    def set_color(self, r: int, g: int, b: int):
        """Set all points to a specific color."""
        if not self.ilda_file:
            return
        
        self._save_history()
        for frame in self.ilda_file.frames:
            for point in frame.points:
                if not point.is_blank:
                    point.r = r
                    point.g = g
                    point.b = b

    def export(self, format_type: IldaFormat = IldaFormat.FORMAT_2D_RGB) -> Optional[bytes]:
        """Export the edited file as bytes."""
        if not self.ilda_file:
            return None
        writer = IldaWriter(format_type)
        return writer.write(self.ilda_file)

    def get_frame_preview(self, frame_index: int) -> List[LaserPoint]:
        """Get a frame as LaserPoints for preview."""
        if not self.ilda_file or frame_index >= len(self.ilda_file.frames):
            return []
        
        frame = self.ilda_file.frames[frame_index]
        return [point.to_laser_point() for point in frame.points]

    def get_info(self) -> Dict[str, Any]:
        """Get information about the loaded file."""
        if not self.ilda_file:
            return {}
        
        return {
            'name': self.ilda_file.name,
            'company': self.ilda_file.company,
            'frame_count': self.ilda_file.frame_count,
            'total_points': self.ilda_file.total_points,
            'frames': [
                {
                    'index': i,
                    'name': f.name,
                    'point_count': f.point_count
                }
                for i, f in enumerate(self.ilda_file.frames)
            ]
        }


# Global instances
_recorder: Optional[IldaRecorder] = None
_editor: Optional[IldaEditor] = None


def get_recorder() -> IldaRecorder:
    """Get the global ILDA recorder instance."""
    global _recorder
    if _recorder is None:
        _recorder = IldaRecorder()
    return _recorder


def get_editor() -> IldaEditor:
    """Get the global ILDA editor instance."""
    global _editor
    if _editor is None:
        _editor = IldaEditor()
    return _editor
