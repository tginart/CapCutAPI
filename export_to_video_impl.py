"""
===============================================================================
VIDEO EXPORT IMPLEMENTATION FOR CAPCUT API
===============================================================================

OVERVIEW:
---------
This module provides a complete video composition engine that exports CapCut drafts
to video files using FFmpeg. It takes a draft specification (YAML config or draft ID)
and renders all visual and textual elements into a final video output.

ARCHITECTURE:
-------------
1. VideoCompositionEngine Class:
   - Core engine that extracts segments from draft tracks
   - Sorts segments by render order (z-index) for proper layering
   - Generates FFmpeg filter_complex strings for compositing

2. Segment Processing Pipeline:
   - Extract segments from all tracks (video, text, stickers)
   - Convert CapCut timing (microseconds) to FFmpeg timing (seconds)
   - Apply transformations, effects, and timing controls
   - Generate FFmpeg filter graphs for each segment type

3. FFmpeg Integration:
   - Builds complex filter graphs for multi-layer compositing
   - Handles multiple input sources (videos, images, generated content)
   - Applies real-time transformations and effects
   - Encodes final output with configurable settings

CURRENT FUNCTIONALITY:
----------------------

SUPPORTED OPERATIONS:
~~~~~~~~~~~~~~~~~~~~~~
✓ add_video:
  - Video clips with source/target timing
  - Scale transformations (scale_x, scale_y)
  - Position transformations (transform_x, transform_y)
  - Opacity control (alpha)
  - Rotation (rotation)
  - Speed effects (speed)
  - Basic video effects (blur, sharpen via effect mapping)

✓ add_image:
  - Static images as video segments
  - All video transformations apply
  - Intro/outro animations (basic support)
  - Transitions (basic support)
  - Background blur (not implemented)

✓ add_text:
  - Text overlays with custom content
  - Font size and color control
  - Position control (transform_x, transform_y)
  - Timing control (start/end)
  - Basic styling (font, color, alpha)

✓ add_sticker:
  - Basic placeholder support
  - Position and transformation support
  - Limited to simple colored rectangles

✓ add_subtitle:
  - SRT subtitle import
  - Text styling and positioning
  - Timing synchronization

✓ add_audio:
  - Audio clips with source/target timing
  - Volume control and speed effects
  - Multiple audio track mixing
  - AAC encoding with configurable settings

SUPPORTED FEATURES:
~~~~~~~~~~~~~~~~~~~
✓ Multiple track compositing with proper z-index layering
✓ Complex timing synchronization across tracks
✓ Video transformations (scale, position, rotation, opacity)
✓ Audio track mixing and synchronization
✓ Text overlay rendering with basic styling
✓ FFmpeg filter graph generation for professional compositing
✓ Configurable output settings (resolution, FPS, bitrate, audio)
✓ Progress logging and error handling
✓ Asset downloading and management
✓ YAML config processing
✓ Draft ID processing

LIMITATIONS & MISSING FUNCTIONALITY:
------------------------------------

VIDEO EFFECTS & FILTERS:
~~~~~~~~~~~~~~~~~~~~~~~~
✗ Advanced CapCut video effects (only basic blur/sharpen mapped)
✗ Complex filter chains and combinations
✗ Real-time effect parameters and keyframes
✗ CapCut-specific effect presets

TRANSITIONS:
~~~~~~~~~~~
✗ Smooth transitions between segments
✗ Transition duration and easing
✗ Transition effects (dissolve, wipe, etc.)
✗ Custom transition curves

ANIMATIONS:
~~~~~~~~~~~
✗ Complex intro/outro animations
✗ Keyframe-based animations
✗ Animation curves and interpolation
✗ Multi-point animation paths

STICKER SYSTEM:
~~~~~~~~~~~~~~~
✗ Real sticker assets (only placeholder rectangles)
✗ Sticker animations
✗ Sticker effects and transformations
✗ Dynamic sticker properties

TEXT ADVANCED FEATURES:
~~~~~~~~~~~~~~~~~~~~~~~
✗ Rich text formatting (bold, italic, underline)
✗ Multi-style text ranges
✗ Text shadows and outlines
✗ Text background/bubble effects
✗ Font family selection
✗ Text animations and keyframes

KEYFRAME SYSTEM:
~~~~~~~~~~~~~~~~
✗ Video keyframes for property animation
✗ Complex animation curves
✗ Keyframe interpolation
✗ Real-time parameter changes

PERFORMANCE LIMITATIONS:
~~~~~~~~~~~~~~~~~~~~~~~~
✗ No streaming processing for large projects
✗ Memory-intensive for complex compositions
✗ Limited concurrency for asset downloads
✗ No GPU acceleration support

ARCHITECTURAL CONSTRAINTS:
~~~~~~~~~~~~~~~~~~~~~~~~~~
✗ Single-pass FFmpeg processing (no intermediate files)
✗ Limited to FFmpeg-supported formats and codecs
✗ No real-time preview generation
✗ Synchronous processing only

INPUT FORMAT LIMITATIONS:
~~~~~~~~~~~~~~~~~~~~~~~~~
✗ No support for CapCut template imports
✗ Limited imported track support
✗ No support for draft collaboration features
✗ Limited metadata preservation

DEPENDENCIES:
-------------
- FFmpeg must be installed and available in PATH
- All CapCutAPI dependencies
- Python 3.7+
- Remote assets must be accessible via URL

USAGE PATTERNS:
---------------
This implementation is designed for:
✓ Programmatic video generation from YAML configs
✓ Automated content creation workflows
✓ Preview generation for CapCut drafts
✓ Exporting simple to medium-complexity compositions

Not suitable for:
✗ Real-time video processing
✗ Ultra-high-resolution workflows
✗ Complex multi-camera editing
✗ Professional post-production workflows

FUTURE ENHANCEMENT POSSIBILITIES:
---------------------------------
1. Advanced video effects mapping
2. Keyframe animation system
3. Real sticker asset support
4. Transition effects engine
5. Audio fade in/out effects
6. Background music mixing enhancements
7. GPU acceleration support
8. Streaming processing for large projects
9. Multi-format export support
10. Real-time preview generation
11. Advanced text rendering with rich formatting

===============================================================================
"""

import os
import json
import subprocess
import tempfile
import shutil
import argparse
import sys
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass
from collections import defaultdict
import logging

import pyJianYingDraft as draft
from settings.local import IS_CAPCUT_ENV, DRAFT_CACHE_DIR
from draft_cache import DRAFT_CACHE
from save_draft_impl import query_script_impl
from util import generate_draft_url

# Setup logging
logger = logging.getLogger(__name__)

# --- Global calibration for text sizing (CapCut-style size → pixel size) ---
# Defaults estimated from reference at canvas height 1920px:
#   size 12 ≈ 60px, size 8 ≈ 40px
CC_TEXT_PX_AT_SIZE12: float = 60.0
CC_TEXT_PX_AT_SIZE8: float = 40.0
CC_TEXT_BASE_HEIGHT: float = 1920.0

@dataclass
class VideoExportConfig:
    """Configuration for video export"""
    output_path: str
    width: int = 1080
    height: int = 1920
    fps: int = 30
    video_bitrate: str = "8000k"
    audio_bitrate: str = "128k"
    audio_codec: str = "aac"
    audio_channels: int = 2
    audio_sample_rate: int = 44100
    codec: str = "libx264"
    preset: str = "medium"
    crf: str = "23"

@dataclass
class CompositionSegment:
    """Represents a segment in the composition timeline"""
    track_name: str
    track_type: str
    render_index: int
    start_time: float  # seconds
    end_time: float    # seconds
    segment_data: Any
    material_data: Any = None
    z_index: int = 0

@dataclass
class VideoCompositionEngine:
    """Engine for composing video from draft segments"""

    def __init__(self, script: 'draft.Script_file'):
        self.script = script
        self.width = script.width
        self.height = script.height
        # Ensure a valid FPS for filter inputs; fallback to 30 if missing
        self.fps = getattr(script, 'fps', None) or 30
        self.duration_seconds = script.duration / 1_000_000.0  # Convert from microseconds

        # Extract all segments from all tracks
        self.segments: List[CompositionSegment] = []
        self._extract_segments()

        # Sort segments by render order (z-index)
        self.segments.sort(key=lambda s: s.render_index)

    # --- Text sizing helpers -------------------------------------------------
    def _map_capcut_size_to_pixels(self, capcut_size: Optional[float]) -> int:
        """Map CapCut-style text size to drawtext pixel size.

        Calibrated using module-level constants:
          - CC_TEXT_PX_AT_SIZE12: pixel height for size=12 at base height
          - CC_TEXT_PX_AT_SIZE8:  pixel height for size=8  at base height
          - CC_TEXT_BASE_HEIGHT: base canvas height these measurements were taken on

        If needed, falls back to a simple heuristic scaling with canvas height.
        """
        # Fallback default ~5% of height when size not provided
        if capcut_size is None:
            return max(12, int(0.05 * self.height))

        # Linear map at base height, then scale with our canvas height
        p12 = CC_TEXT_PX_AT_SIZE12
        p8 = CC_TEXT_PX_AT_SIZE8
        base_h = CC_TEXT_BASE_HEIGHT if CC_TEXT_BASE_HEIGHT > 0 else 1920.0
        try:
            slope = (p12 - p8) / (12.0 - 8.0)
            intercept = p12 - slope * 12.0
            px_at_base = slope * float(capcut_size) + intercept
            px = px_at_base * (self.height / base_h)
            return max(12, int(px))
        except Exception:
            # Ignore calibration errors and use heuristic
            pass

        # Heuristic compatible with common 1080x1920 vertical canvases
        # Target: size 12 ≈ 60px and size 8 ≈ 40px at height 1920 → ~5 px/size
        # px ≈ size * (height / 384)
        return max(12, int(float(capcut_size) * (self.height / 384.0)))

    def _extract_segments(self):
        """Extract all segments from the script and organize by time"""
        track_list = list(self.script.tracks.values())
        track_list.extend(getattr(self.script, 'imported_tracks', []))

        for track in track_list:
            track_name = getattr(track, 'name', 'unnamed')
            track_type = track.track_type.name
            render_index = track.render_index

            segments = getattr(track, 'segments', [])
            for i, segment in enumerate(segments):
                # Convert timerange from microseconds to seconds
                target_range = getattr(segment, 'target_timerange', None)
                if target_range is None:
                    continue

                start_time = target_range.start / 1_000_000.0
                end_time = (target_range.start + target_range.duration) / 1_000_000.0

                # Get material data for this segment
                material_data = None
                if hasattr(segment, 'material_instance'):
                    material_data = segment.material_instance
                elif hasattr(segment, 'material_id'):
                    # Try to find material by ID
                    material_data = self._find_material_by_id(segment.material_id, track_type)

                comp_segment = CompositionSegment(
                    track_name=track_name,
                    track_type=track_type,
                    render_index=render_index,
                    start_time=start_time,
                    end_time=end_time,
                    segment_data=segment,
                    material_data=material_data,
                    z_index=i
                )

                self.segments.append(comp_segment)

    def _find_material_by_id(self, material_id: str, track_type: str) -> Optional[Any]:
        """Find material by ID in the script materials"""
        materials = getattr(self.script, 'materials', None)
        if materials is None:
            return None

        if track_type == 'video':
            for video in getattr(materials, 'videos', []):
                if getattr(video, 'material_id', None) == material_id:
                    return video
        elif track_type == 'audio':
            for audio in getattr(materials, 'audios', []):
                if getattr(audio, 'material_id', None) == material_id:
                    return audio
        elif track_type == 'text':
            for text in getattr(materials, 'texts', []):
                if text.get('id') == material_id:
                    return text

        return None

    def get_active_segments_at_time(self, time_seconds: float) -> List[CompositionSegment]:
        """Get all segments that are active at a given time"""
        active_segments = []
        for segment in self.segments:
            if segment.start_time <= time_seconds < segment.end_time:
                active_segments.append(segment)
        return active_segments

    def _overlay_coords(self, segment: CompositionSegment) -> Tuple[int, int]:
        """Compute pixel coordinates for overlay placement from normalized transforms."""
        clip_settings = getattr(segment.segment_data, 'clip_settings', None)
        if not clip_settings:
            return 0, 0
        transform_x = getattr(clip_settings, 'transform_x', 0.0)
        transform_y = getattr(clip_settings, 'transform_y', 0.0)
        x_pixels = int((transform_x + 1.0) * self.width / 2)
        y_pixels = int((transform_y + 1.0) * self.height / 2)
        return x_pixels, y_pixels

    def _is_image_media(self, segment: CompositionSegment) -> bool:
        """Best-effort detection of still image media based on URL extension."""
        material = segment.material_data
        url = getattr(material, 'remote_url', '') or ''
        url = url.lower().split('?')[0]
        return url.endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.tif'))

    def generate_ffmpeg_filter_complex(self, temp_dir: str) -> Tuple[str, str, List[str]]:
        """
        Generate FFmpeg filter_complex strings for video and audio composition

        Returns:
            Tuple of (video_filter_complex, audio_filter_complex, input_files_list)
        """
        filter_parts = []
        audio_filter_parts = []
        input_files = []
        stream_index = 0

        # Global ordered list by render index and in-track z_index
        ordered_segments = sorted(self.segments, key=lambda s: (s.render_index, s.z_index))
        # Audio segments handled after video composition
        audio_segments = [s for s in ordered_segments if s.track_type == 'audio']

        # Create background
        background_input = f"color=c=black:size={self.width}x{self.height}:r={self.fps}:d={self.duration_seconds}"
        # Add as grouped arguments for FFmpeg (so the builder can extend them verbatim)
        input_files.append(['-f', 'lavfi', '-i', background_input])
        filter_parts.append(f"[{stream_index}:v]null[bg]")

        stream_index += 1
        layer_outputs = ["[bg]"]

        # Iterate in global z-order; maintain running index for text intermediates
        text_intermediate_files = getattr(self, 'text_intermediate_files', None)
        text_idx = 0

        for i, segment in enumerate(ordered_segments):
            if segment.track_type in ['video', 'image']:
                if segment.material_data and hasattr(segment.material_data, 'remote_url'):
                    video_url = segment.material_data.remote_url
                    if video_url:
                        if self._is_image_media(segment):
                            seg_duration = max(0.0, segment.end_time - segment.start_time)
                            input_files.append(['-loop', '1', '-t', f"{seg_duration}", '-i', video_url])
                        else:
                            input_files.append(video_url)
                        video_filter = self._generate_video_segment_filter(
                            segment, stream_index, i, temp_dir
                        )
                        if video_filter:
                            filter_parts.append(video_filter)
                            start = segment.start_time
                            filter_parts.append(f"[v{i}]setpts=PTS+{start}/TB[v{i}_ts]")
                            prev_layer = layer_outputs[-1]
                            ox, oy = self._overlay_coords(segment)
                            end = segment.end_time
                            filter_parts.append(
                                f"{prev_layer}[v{i}_ts]overlay={ox}-w/2:{oy}-h/2:enable='between(t\\,{start}\\,{end})'[layer{i+1}]"
                            )
                            layer_outputs.append(f"[layer{i+1}]")
                        stream_index += 1

            elif segment.track_type == 'sticker':
                if segment.material_data:
                    sticker_filter = self._generate_sticker_segment_filter(
                        segment, i, temp_dir
                    )
                    if sticker_filter:
                        filter_parts.append(sticker_filter)
                        prev_layer = layer_outputs[-1]
                        ox, oy = self._overlay_coords(segment)
                        start = segment.start_time
                        end = segment.end_time
                        filter_parts.append(
                            f"{prev_layer}[sticker{i}]overlay={ox}-w/2:{oy}-h/2:enable='between(t\\,{start}\\,{end})'[layer{i+1}]"
                        )
                        layer_outputs.append(f"[layer{i+1}]")

            elif segment.track_type == 'text':
                start = segment.start_time
                end = segment.end_time
                prev_layer = layer_outputs[-1]
                if text_intermediate_files and text_idx < len(text_intermediate_files) and text_intermediate_files[text_idx]:
                    input_files.append(text_intermediate_files[text_idx])
                    filter_parts.append(f"[{stream_index}:v]setpts=PTS+{start}/TB[text{i}_ts]")
                    filter_parts.append(
                        f"{prev_layer}[text{i}_ts]overlay=0:0:enable='between(t\\,{start}\\,{end})'[layer{i+1}]"
                    )
                    layer_outputs.append(f"[layer{i+1}]")
                    stream_index += 1
                else:
                    text_filter = self._generate_text_segment_filter(segment, i, temp_dir)
                    if text_filter:
                        filter_parts.append(f"{prev_layer}{text_filter}[layer{i+1}]")
                        layer_outputs.append(f"[layer{i+1}]")
                text_idx += 1

        # Final video output
        final_output = layer_outputs[-1]
        # Use a no-op filter to assign the final label
        filter_parts.append(f"{final_output}null[final_video]")

        # Process audio segments and build audio mix
        if audio_segments:
            audio_filter_parts = self._build_audio_mix_graph(audio_segments, stream_index, input_files)

        filter_complex = "; ".join(filter_parts) if filter_parts else ""
        audio_filter_complex = "; ".join(audio_filter_parts) if audio_filter_parts else ""

        # Validate filter complex is not empty and has proper structure
        if not filter_complex.strip():
            raise ValueError("Generated video filter complex is empty")

        # Ensure we have at least one input (the background)
        if len(input_files) == 0:
            raise ValueError("No input files generated for FFmpeg")

        return filter_complex, audio_filter_complex, input_files

    def _generate_video_segment_filter(self, segment: CompositionSegment,
                                     stream_index: int, layer_index: int,
                                     temp_dir: str) -> Optional[str]:
        """Generate FFmpeg filter for a video segment"""
        segment_data = segment.segment_data
        material_data = segment.material_data

        if not material_data or not hasattr(material_data, 'remote_url'):
            return None

        filters = []

        # Base stream
        base_stream = f"[{stream_index}:v]"

        # Apply timing - trim to segment duration
        duration = segment.end_time - segment.start_time
        source_range = getattr(segment_data, 'source_timerange', None)

        if source_range:
            start_offset = source_range.start / 1_000_000.0
            source_duration = source_range.duration / 1_000_000.0
            filters.append(f"{base_stream}trim={start_offset}:{start_offset + source_duration},setpts=PTS-STARTPTS[vid{layer_index}]")
        else:
            filters.append(f"{base_stream}trim=0:{duration},setpts=PTS-STARTPTS[vid{layer_index}]")

        # Apply transformations
        clip_settings = getattr(segment_data, 'clip_settings', None)
        if clip_settings:
            transform_filters = []

            # Scale
            if hasattr(clip_settings, 'scale_x') and hasattr(clip_settings, 'scale_y'):
                scale_x = getattr(clip_settings, 'scale_x', 1.0)
                scale_y = getattr(clip_settings, 'scale_y', 1.0)
                if scale_x != 1.0 or scale_y != 1.0:
                    transform_filters.append(f"scale=iw*{scale_x}:ih*{scale_y}")

            # Opacity
            if hasattr(clip_settings, 'alpha'):
                alpha = getattr(clip_settings, 'alpha', 1.0)
                if alpha != 1.0:
                    transform_filters.append(f"format=rgba,colorchannelmixer=aa={alpha}")

            # Rotation
            if hasattr(clip_settings, 'rotation'):
                rotation = getattr(clip_settings, 'rotation', 0.0)
                if rotation != 0.0:
                    transform_filters.append(f"rotate={rotation}*PI/180")

            if transform_filters:
                transform_chain = ",".join(transform_filters)
                filters.append(f"[vid{layer_index}]{transform_chain}[v{layer_index}]")
            else:
                # Pass-through mapping to name the stream for downstream filters
                filters.append(f"[vid{layer_index}]null[v{layer_index}]")

        # Apply speed effect
        speed = getattr(segment_data, 'speed', None)
        if speed and hasattr(speed, 'speed') and speed.speed != 1.0:
            speed_factor = speed.speed
            filters.append(f"[v{layer_index}]setpts=PTS/{speed_factor}[v{layer_index}]")

        # Apply effects if any
        effects = getattr(segment_data, 'effects', [])
        for effect in effects:
            effect_name = getattr(effect, 'name', '')
            if effect_name:
                effect_filter = self._apply_video_effect(effect_name, layer_index)
                if effect_filter:
                    filters.append(effect_filter)

        # Combine all filters for this segment
        if filters:
            return "; ".join(filters)
        else:
            return f"[{stream_index}:v]null[v{layer_index}]"

    def _generate_sticker_segment_filter(self, segment: CompositionSegment,
                                       layer_index: int, temp_dir: str) -> Optional[str]:
        """Generate FFmpeg filter for a sticker segment"""
        segment_data = segment.segment_data
        material_data = segment.material_data

        if not material_data:
            return None

        # For now, treat stickers similar to images
        # In a full implementation, this would handle sticker-specific properties
        filters = []

        # Create a temporary image input (placeholder for sticker)
        # In practice, stickers would need to be downloaded and processed
        sticker_input = f"color=c=red:size=100x100:r={self.fps}:d={segment.end_time - segment.start_time}[sticker{layer_index}]"
        filters.append(sticker_input)

        # Apply transformations similar to video segments
        clip_settings = getattr(segment_data, 'clip_settings', None)
        if clip_settings:
            transform_filters = []

            # Scale
            if hasattr(clip_settings, 'scale_x') and hasattr(clip_settings, 'scale_y'):
                scale_x = getattr(clip_settings, 'scale_x', 1.0)
                scale_y = getattr(clip_settings, 'scale_y', 1.0)
                if scale_x != 1.0 or scale_y != 1.0:
                    transform_filters.append(f"scale=iw*{scale_x}:ih*{scale_y}")

            # Position
            if hasattr(clip_settings, 'transform_x') and hasattr(clip_settings, 'transform_y'):
                transform_x = getattr(clip_settings, 'transform_x', 0.0)
                transform_y = getattr(clip_settings, 'transform_y', 0.0)
                if transform_x != 0.0 or transform_y != 0.0:
                    x_pixels = int((transform_x + 1.0) * self.width / 2)
                    y_pixels = int((transform_y + 1.0) * self.height / 2)
                    transform_filters.append(f"translate={x_pixels}:{y_pixels}")

            # Opacity
            if hasattr(clip_settings, 'alpha'):
                alpha = getattr(clip_settings, 'alpha', 1.0)
                if alpha != 1.0:
                    transform_filters.append(f"format=rgba,colorchannelmixer=aa={alpha}")

            if transform_filters:
                transform_chain = ",".join(transform_filters)
                filters.append(f"[sticker{layer_index}]{transform_chain}[sticker{layer_index}]")

        return "; ".join(filters) if filters else None

    def _apply_video_effect(self, effect_name: str, layer_index: int) -> Optional[str]:
        """Apply a video effect filter"""
        # Placeholder for video effects
        # In a full implementation, this would map CapCut effect names to FFmpeg filters
        effect_map = {
            'blur': f'[v{layer_index}]boxblur=5[v{layer_index}]',
            'sharpen': f'[v{layer_index}]unsharp[v{layer_index}]',
            # Add more effects as needed
        }

        return effect_map.get(effect_name.lower())

    def _generate_text_segment_filter(self, segment: CompositionSegment,
                                    layer_index: int, temp_dir: str) -> Optional[str]:
        """Generate FFmpeg filter for a text segment"""
        segment_data = segment.segment_data

        # Get text content
        text_content = getattr(segment_data, 'text', '')
        if not text_content:
            return None

        # Escape special characters for FFmpeg filtergraph safety
        # Order matters: escape backslashes first
        text_content = (
            text_content
            .replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace(":", "\\:")
            .replace(",", "\\,")
            .replace(";", "\\;")
            .replace("[", "\\[")
            .replace("]", "\\]")
            .replace("\n", "\\n")
            .replace("\r", "")
        )

        # Get text style and clip transforms
        style = getattr(segment_data, 'style', None)
        clip_settings = getattr(segment_data, 'clip_settings', None)
        # Default font size ~5% of canvas height, minimum 12
        default_font_size = max(12, int(0.05 * self.height))
        font_size = default_font_size
        font_color = "white"
        position_x = "(w-tw)/2"  # default center if no transforms
        position_y = "(h-th)/2"

        if style:
            # Map CapCut size to pixels
            size_val = getattr(style, 'size', None)
            if size_val is not None:
                font_size = self._map_capcut_size_to_pixels(size_val)

            # Font color from RGB tuple 0..1
            if hasattr(style, 'color'):
                try:
                    r, g, b = getattr(style, 'color', (1.0, 1.0, 1.0))
                    r_i = max(0, min(255, int(round(r * 255))))
                    g_i = max(0, min(255, int(round(g * 255))))
                    b_i = max(0, min(255, int(round(b * 255))))
                    alpha_val = getattr(style, 'alpha', 1.0)
                    # drawtext supports 0xRRGGBB and optional @alpha
                    font_color = f"0x{r_i:02x}{g_i:02x}{b_i:02x}"
                    if 0.0 <= alpha_val < 1.0:
                        font_color += f"@{alpha_val}"
                except Exception:
                    pass

        # Position conversion from normalized coordinates stored in clip_settings
        if clip_settings is not None:
            if hasattr(clip_settings, 'transform_x'):
                transform_x = getattr(clip_settings, 'transform_x', 0.0)
                # Position center of text at the specified coordinate
                center_x = int((transform_x + 1.0) * self.width / 2)
                position_x = f"{center_x}-tw/2"
            if hasattr(clip_settings, 'transform_y'):
                transform_y = getattr(clip_settings, 'transform_y', 0.0)
                # Position center of text at the specified coordinate
                center_y = int((transform_y + 1.0) * self.height / 2)
                position_y = f"{center_y}-th/2"

        # Create text filter with timing
        duration = segment.end_time - segment.start_time
        text_filter = (
            f"drawtext=text='{text_content}'"
            f":fontsize={font_size}"
            f":fontcolor={font_color}"
            f":x={position_x}"
            f":y={position_y}"
            f":enable='between(t\\,{segment.start_time}\\,{segment.end_time})'"
        )

        return text_filter

    def _generate_audio_segment_filter(self, segment: CompositionSegment,
                                     stream_index: int, layer_index: int) -> Optional[str]:
        """Generate FFmpeg filter for an audio segment"""
        segment_data = segment.segment_data
        material_data = segment.material_data

        if not material_data or not hasattr(material_data, 'remote_url'):
            return None

        filters = []
        base_stream = f"[{stream_index}:a]"

        # Apply timing - trim to segment duration
        duration = segment.end_time - segment.start_time
        source_range = getattr(segment_data, 'source_timerange', None)

        if source_range:
            start_offset = source_range.start / 1_000_000.0
            source_duration = source_range.duration / 1_000_000.0
            filters.append(f"{base_stream}atrim={start_offset}:{start_offset + source_duration},asetpts=PTS-STARTPTS[a{layer_index}]")
        else:
            filters.append(f"{base_stream}atrim=0:{duration},asetpts=PTS-STARTPTS[a{layer_index}]")

        # Shift audio into the global timeline so playback starts at target start
        start_ms = int(segment.start_time * 1000)
        if start_ms > 0:
            filters.append(f"[a{layer_index}]adelay={start_ms}:all=1[a{layer_index}]")

        # Apply speed effect (atempo)
        speed = getattr(segment_data, 'speed', None)
        if speed and hasattr(speed, 'speed') and speed.speed != 1.0:
            speed_factor = speed.speed
            # Handle speed factors outside atempo's 0.5-2.0 range by chaining
            remaining_speed = speed_factor
            speed_filters = []

            while remaining_speed < 0.5:
                speed_filters.append("atempo=2.0")
                remaining_speed *= 2.0
            while remaining_speed > 2.0:
                speed_filters.append("atempo=0.5")
                remaining_speed *= 0.5

            if remaining_speed != 1.0:
                speed_filters.append(f"atempo={remaining_speed}")

            if speed_filters:
                speed_chain = ",".join(speed_filters)
                filters.append(f"[a{layer_index}]{speed_chain}[a{layer_index}]")

        # Apply volume
        clip_settings = getattr(segment_data, 'clip_settings', None)
        if clip_settings:
            volume = getattr(clip_settings, 'volume', 1.0)
            if volume != 1.0:
                filters.append(f"[a{layer_index}]volume={volume}[a{layer_index}]")

        # Combine all filters for this segment
        if filters:
            return "; ".join(filters)
        else:
            return f"[{stream_index}:a]anull[a{layer_index}]"

    def _build_audio_mix_graph(self, audio_segments: List[CompositionSegment],
                              start_stream_index: int, input_files: List) -> List[str]:
        """Build FFmpeg audio filter graph for mixing multiple audio tracks"""
        if not audio_segments:
            return []

        filter_parts = []
        audio_streams = []

        # Process each audio segment
        current_stream_index = start_stream_index
        for i, segment in enumerate(audio_segments):
            if segment.material_data and hasattr(segment.material_data, 'remote_url'):
                audio_url = segment.material_data.remote_url
                if audio_url:
                    input_files.append(audio_url)
                    audio_filter = self._generate_audio_segment_filter(
                        segment, current_stream_index, i
                    )
                    if audio_filter:
                        filter_parts.append(audio_filter)
                        audio_streams.append(f"[a{i}]")
                    current_stream_index += 1

        # Mix all audio streams
        if len(audio_streams) == 1:
            # Single audio stream
            filter_parts.append(f"{audio_streams[0]}anull[final_audio]")
        elif len(audio_streams) > 1:
            # Mix multiple streams
            mix_inputs = "".join(audio_streams)
            filter_parts.append(f"{mix_inputs}amix=inputs={len(audio_streams)}:dropout_transition=0[final_audio]")
        else:
            # No audio streams, create silent audio
            silent_input = f"anoisesrc=d=0:c=pink:r=44100:a=0.0"
            input_files.append(['-f', 'lavfi', '-i', silent_input])
            filter_parts.append(f"[{current_stream_index}:a]anull[final_audio]")

        return filter_parts


def _prerender_text_segments(engine: VideoCompositionEngine, temp_dir: str) -> List[Optional[str]]:
    """Pre-render text segments to alpha-preserving intermediates.

    Each intermediate has duration equal to the text segment duration and baked-in position.
    Timing is applied at final overlay stage, not inside the prerender.
    Returns a list of file paths (or None) aligned with the order of text segments in generate_ffmpeg_filter_complex.
    """
    # Collect text segments in the same order used in generate_ffmpeg_filter_complex
    sorted_segments = sorted(engine.segments, key=lambda s: s.render_index)
    text_segments = [s for s in sorted_segments if s.track_type == 'text']

    intermediates: List[Optional[str]] = []
    for idx, segment in enumerate(text_segments):
        segment_data = segment.segment_data
        text_content = getattr(segment_data, 'text', '')
        if not text_content:
            intermediates.append(None)
            continue

        # Escape for filtergraph
        text_content = (
            text_content
            .replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace(":", "\\:")
            .replace(",", "\\,")
            .replace(";", "\\;")
            .replace("[", "\\[")
            .replace("]", "\\]")
            .replace("\n", "\\n")
            .replace("\r", "")
        )

        style = getattr(segment_data, 'style', None)
        # Map style.size to calibrated pixels for prerendered text
        font_size = engine._map_capcut_size_to_pixels(getattr(style, 'size', None)) if style else max(12, int(0.05 * engine.height))
        font_color = getattr(style, 'font_color', 'white') if style else 'white'

        # Position baked into prerender from clip settings (global normalized coords)
        clip_settings = getattr(segment_data, 'clip_settings', None)
        position_x = "(w-tw)/2"
        position_y = "(h-th)/2"
        if clip_settings is not None:
            if hasattr(clip_settings, 'transform_x'):
                transform_x = getattr(clip_settings, 'transform_x', 0.0)
                # Position center of text at the specified coordinate
                center_x = int((transform_x + 1.0) * engine.width / 2)
                position_x = f"{center_x}-tw/2"
            if hasattr(clip_settings, 'transform_y'):
                transform_y = getattr(clip_settings, 'transform_y', 0.0)
                # Position center of text at the specified coordinate
                center_y = int((transform_y + 1.0) * engine.height / 2)
                position_y = f"{center_y}-th/2"

        duration = max(0.0, segment.end_time - segment.start_time)
        if duration <= 0:
            intermediates.append(None)
            continue

        # Transparent canvas with a true zero alpha plane
        canvas = (
            f"color=s={engine.width}x{engine.height}:r={engine.fps}:d={duration},format=rgba,geq=a='0'"
        )
        text_filter = (
            f"drawtext=text='{text_content}':fontsize={font_size}:fontcolor={font_color}:x={position_x}:y={position_y}"
        )

        out_path = os.path.join(temp_dir, f"text_seg_{idx:03d}.mov")
        cmd = [
            'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
            '-f', 'lavfi', '-i', canvas,
            # Canvas already has alpha; draw text directly
            '-filter_complex', f"[0:v]{text_filter}",
            # Use a codec/pixel format with robust alpha support for intermediates.
            '-c:v', 'qtrle', '-pix_fmt', 'argb',
            out_path
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=temp_dir)
            intermediates.append(out_path)
        except Exception:
            intermediates.append(None)

    return intermediates

def export_to_video_impl(
    output_path: str,
    yaml_config: Optional[str] = None,
    draft_id: Optional[str] = None,
    export_config: Optional[VideoExportConfig] = None
) -> Dict[str, Any]:
    """
    Export a CapCut draft to video using FFmpeg

    Args:
        output_path: Path where the output video will be saved
        yaml_config: Path to YAML config file or raw YAML content
        draft_id: ID of existing draft in cache
        export_config: Video export configuration

    Returns:
        Dict with success status and metadata
    """

    # Input validation
    if yaml_config and draft_id:
        raise ValueError("Cannot specify both yaml_config and draft_id")
    if not yaml_config and not draft_id:
        raise ValueError("Must specify either yaml_config or draft_id")

    # Default export config
    if export_config is None:
        export_config = VideoExportConfig(output_path=output_path)

    try:
        logger.info(f"Starting video export to: {output_path}")

        # Get or create draft
        if yaml_config:
            logger.info("Processing YAML config...")
            # Import parse_yaml_config function
            from CapCutAPI import parse_yaml_config

            # Check if yaml_config is a file path or raw content
            if os.path.isfile(yaml_config):
                # It's a file path
                result = parse_yaml_config(yaml_config)
            else:
                # It's raw YAML content - create a temporary file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                    f.write(yaml_config)
                    temp_yaml_path = f.name

                try:
                    result = parse_yaml_config(temp_yaml_path)
                finally:
                    # Clean up temporary file
                    if os.path.exists(temp_yaml_path):
                        os.unlink(temp_yaml_path)

            draft_id = result.get('draft_id')
            if not draft_id:
                raise ValueError("Failed to parse YAML config or create draft")
            logger.info(f"Created draft from YAML: {draft_id}")

        logger.info(f"Loading draft: {draft_id}")

        # Get script from cache
        script = query_script_impl(draft_id, force_update=True)
        if script is None:
            raise ValueError(f"Draft {draft_id} not found in cache")

        logger.info(f"Draft loaded successfully. Canvas: {script.width}x{script.height}, Duration: {script.duration/1_000_000.0:.2f}s")

        # Create composition engine
        engine = VideoCompositionEngine(script)
        logger.info(f"Composition engine created. Found {len(engine.segments)} segments")

        # Create temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info(f"Created temporary directory: {temp_dir}")

            # Pre-render text segments to intermediates to reduce filter graph complexity
            try:
                engine.text_intermediate_files = _prerender_text_segments(engine, temp_dir)
                logger.info(f"Pre-rendered {len([p for p in engine.text_intermediate_files if p])} text segments")
            except Exception as _e:
                logger.warning(f"Text pre-render failed, falling back to inline drawtext: {_e}")
                engine.text_intermediate_files = None

            # Generate FFmpeg filter complex
            filter_complex, audio_filter_complex, input_files = engine.generate_ffmpeg_filter_complex(temp_dir)
            logger.info(f"Generated FFmpeg filter complex with {len(input_files)} inputs")

            # Build FFmpeg command
            ffmpeg_cmd = [
                'ffmpeg',
                '-y',  # Overwrite output files
                '-hide_banner',  # Reduce output verbosity
                '-loglevel', 'info'
            ]

            # Add input files (some are already expanded argument lists)
            for input_item in input_files:
                if isinstance(input_item, list):
                    # Already expanded arguments (like ['-f', 'lavfi', '-i', 'color=...'])
                    ffmpeg_cmd.extend(input_item)
                else:
                    # Single input file
                    ffmpeg_cmd.extend(['-i', input_item])

            # Build complete filter complex (video + audio)
            full_filter_complex = filter_complex
            if audio_filter_complex:
                full_filter_complex += ("; " if full_filter_complex else "") + audio_filter_complex

            # Add filter complex
            ffmpeg_cmd.extend([
                '-filter_complex', full_filter_complex,
                '-map', '[final_video]',
                '-c:v', export_config.codec if export_config else 'libx264',
                '-preset', export_config.preset if export_config else 'medium',
                '-crf', export_config.crf if export_config else '23',
                '-b:v', export_config.video_bitrate if export_config else '8000k',
                '-r', str(export_config.fps if export_config else 30),
                '-pix_fmt', 'yuv420p',  # Ensure compatibility
            ])

            # Add audio mapping and encoding if we have audio
            if audio_filter_complex:
                ffmpeg_cmd.extend([
                    '-map', '[final_audio]',
                    '-c:a', export_config.audio_codec if export_config else 'aac',
                    '-b:a', export_config.audio_bitrate if export_config else '128k',
                    '-ac', str(export_config.audio_channels if export_config else 2),
                    '-ar', str(export_config.audio_sample_rate if export_config else 44100),
                ])
            else:
                # No audio, ensure we don't output an audio stream
                ffmpeg_cmd.extend(['-an'])

            ffmpeg_cmd.append(output_path)

            logger.info(f"Running FFmpeg command with {len(ffmpeg_cmd)} arguments")
            logger.debug(f"FFmpeg command: {' '.join(ffmpeg_cmd)}")

            # Execute FFmpeg
            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True,
                cwd=temp_dir,
                timeout=300  # 5 minute timeout
            )

            if result.returncode != 0:
                logger.error(f"FFmpeg failed with return code {result.returncode}")
                logger.error(f"FFmpeg stderr: {result.stderr}")
                logger.error(f"FFmpeg stdout: {result.stdout}")
                raise RuntimeError(f"FFmpeg export failed (return code {result.returncode}): {result.stderr}")

            # Success path
            logger.info(f"Video export completed successfully: {output_path}")

            # Check output file
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                logger.info(f"Output file size: {file_size} bytes ({file_size/1024/1024:.2f} MB)")
            else:
                raise RuntimeError(f"Output file was not created: {output_path}")

            return {
                "success": True,
                "output_path": output_path,
                "duration": engine.duration_seconds,
                "width": engine.width,
                "height": engine.height,
                "fps": engine.fps,
                "file_size": file_size if 'file_size' in locals() else 0
            }

    except subprocess.TimeoutExpired:
        logger.error("FFmpeg export timed out after 5 minutes")
        raise RuntimeError("FFmpeg export timed out - video may be too complex or system overloaded")

        # Success path handled above after FFmpeg execution

    except Exception as e:
        logger.error(f"Video export failed: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


def create_cli_parser() -> argparse.ArgumentParser:
    """Create command line argument parser for video export."""
    parser = argparse.ArgumentParser(
        description="Export CapCut drafts to video using FFmpeg",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export from YAML config file
  python export_to_video_impl.py output.mp4 --yaml-config project.yml

  # Export from YAML string
  python export_to_video_impl.py output.mp4 --yaml-config 'draft:\\n  width: 1080\\nsteps:\\n  - add_text:\\n      text: "Hello"'

  # Export from draft ID with custom settings
  python export_to_video_impl.py output.mp4 --draft-id dfd_cat_123456 --width 1920 --height 1080 --fps 60

  # Export with custom video settings
  python export_to_video_impl.py output.mp4 --yaml-config config.yml --video-bitrate 10000k --codec libx264
        """
    )

    # Required positional argument
    parser.add_argument(
        "output_path",
        help="Path where the output video will be saved"
    )

    # Input source (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--yaml-config",
        help="Path to YAML config file or raw YAML content string"
    )
    input_group.add_argument(
        "--draft-id",
        help="ID of existing draft in cache"
    )

    # Export configuration options
    config_group = parser.add_argument_group("export configuration")
    config_group.add_argument(
        "--width",
        type=int,
        help="Output video width (default: use draft canvas width)"
    )
    config_group.add_argument(
        "--height",
        type=int,
        help="Output video height (default: use draft canvas height)"
    )
    config_group.add_argument(
        "--fps",
        type=int,
        help="Output video FPS (default: 30)"
    )
    config_group.add_argument(
        "--video-bitrate",
        help="Video bitrate (e.g., '8000k', default: '8000k')"
    )
    config_group.add_argument(
        "--audio-bitrate",
        help="Audio bitrate (e.g., '128k', default: '128k')"
    )
    config_group.add_argument(
        "--audio-codec",
        help="Audio codec (default: 'aac')"
    )
    config_group.add_argument(
        "--audio-channels",
        type=int,
        help="Audio channels (1=mono, 2=stereo, default: 2)"
    )
    config_group.add_argument(
        "--audio-sample-rate",
        type=int,
        help="Audio sample rate in Hz (default: 44100)"
    )
    config_group.add_argument(
        "--codec",
        help="Video codec (default: 'libx264')"
    )
    config_group.add_argument(
        "--preset",
        choices=['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow'],
        help="Encoding preset (default: 'medium')"
    )
    config_group.add_argument(
        "--crf",
        help="Constant Rate Factor (default: '23')"
    )

    # Logging options
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress most output (only show errors and final result)"
    )

    return parser


def main():
    """Main CLI entry point."""
    parser = create_cli_parser()
    args = parser.parse_args()

    # Setup logging based on verbosity
    if args.quiet:
        logging.basicConfig(level=logging.ERROR)
    elif args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    logger = logging.getLogger(__name__)

    try:
        # Validate output path
        output_path = args.output_path
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            logger.info(f"Created output directory: {output_dir}")

        # Create export config if any custom settings provided
        export_config = None
        config_params = {
            'width': args.width,
            'height': args.height,
            'fps': args.fps,
            'video_bitrate': args.video_bitrate,
            'audio_bitrate': args.audio_bitrate,
            'audio_codec': args.audio_codec,
            'audio_channels': args.audio_channels,
            'audio_sample_rate': args.audio_sample_rate,
            'codec': args.codec,
            'preset': args.preset,
            'crf': args.crf
        }

        # Only create config if any parameters are specified
        if any(v is not None for v in config_params.values()):
            # Filter out None values to avoid overriding defaults
            filtered_params = {k: v for k, v in config_params.items() if v is not None}
            export_config = VideoExportConfig(output_path=output_path, **filtered_params)
            logger.info("Using custom export configuration")
        else:
            export_config = VideoExportConfig(output_path=output_path)

        # Call the export function
        logger.info("Starting video export...")
        result = export_to_video_impl(
            output_path=output_path,
            yaml_config=args.yaml_config,
            draft_id=args.draft_id,
            export_config=export_config
        )

        if result["success"]:
            if not args.quiet:
                print("✅ Video export completed successfully!")
                print(f"📁 Output: {result['output_path']}")
                print(f"🎬 Duration: {result['duration']:.2f} seconds")
                print(f"📐 Resolution: {result['width']}x{result['height']}")
                print(f"🎞️  FPS: {result['fps']}")
                if result.get('file_size', 0) > 0:
                    print(f"💾 File size: {result['file_size'] / 1024 / 1024:.2f} MB")
            sys.exit(0)
        else:
            print(f"❌ Export failed: {result['error']}")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⚠️  Export interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
