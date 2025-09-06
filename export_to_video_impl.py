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
from pyJianYingDraft.metadata.capcut_transition_meta import TRANSITION_NAME_LUT

# Setup logging
logger = logging.getLogger(__name__)

# Optional font support via pyfonts
try:
    # pyfonts is expected to be provided in the environment
    # Different versions may expose different helpers; we will try a few APIs at runtime
    import pyfonts  # type: ignore
    _HAS_PYFONTS = True
except Exception:
    pyfonts = None  # type: ignore
    _HAS_PYFONTS = False

# --- Global calibration for text sizing (CapCut-style size → pixel size) ---
# Defaults estimated from reference at canvas height 1920px:
#   size 12 ≈ 60px, size 8 ≈ 40px
CC_TEXT_PX_AT_SIZE12: float = 60.0
CC_TEXT_PX_AT_SIZE8: float = 40.0
CC_TEXT_BASE_HEIGHT: float = 1920.0

# CapCut font → closest Google Font family mapping
# Note: Only includes fonts that successfully resolve via Google Fonts API
CAPCUT_TO_GOOGLE_FONT = {
    'Roboto_BlkCn': 'Roboto Condensed',
    'Poppins_Regular': 'Poppins',
    'Poppins_Bold': 'Poppins',
    'Nunito': 'Nunito',
    'PlayfairDisplay_Bold': 'Playfair Display',
    'Pacifico_Regular': 'Pacifico',
    'Caveat_Regular': 'Caveat',
    'Grandstander_Regular': 'Grandstander',
    'DMSans_BoldItalic': 'DM Sans',
    'Exo': 'Exo',
    'Cabin_Rg': 'Cabin',
    'Kanit_Regular': 'Kanit',
    'Kanit_Black': 'Kanit',
    'Staatliches_Regular': 'Staatliches',
    'Bungee_Regular': 'Bungee',
    'Inter_Black': 'Inter',
    # Removed problematic mappings that cause HTTP 400 errors:
    # 'SansitaSwashed_Regular': 'Sansita Swashed',  # API rejects "SansitaSwashed" family name
    # 'SecularOne_Regular': 'Secular One',          # API rejects "SecularOne" family name  
    'Sora_Regular': 'Sora',
    'Zapfino': 'Great Vibes',
    # 'OldStandardTT_Regular': 'Old Standard TT',   # API rejects "OldStandardTT" family name
    'Coiny_Regular': 'Coiny',
    # 'HeptaSlab_ExtraBold': 'Hepta Slab',          # API rejects "HeptaSlab" family name
    # 'HeptaSlab_Light': 'Hepta Slab',              # API rejects "HeptaSlab" family name
    'Giveny': 'Bodoni Moda',
}

# Explanation: This mapping translates CapCut-specific font identifiers to their closest
# Google Fonts family equivalents. During rendering, we use this to resolve an actual
# local font file via the optional 'pyfonts' helper so FFmpeg drawtext can find a TTF/OTF.
# If a CapCut font is not listed here, we fall back to using the given name directly as
# a best-effort pass-through.

def _infer_font_style_tokens(capcut_font_name: Optional[str], style_obj: Optional[object]) -> tuple[str, bool]:
    """Infer weight token (e.g., 'black','bold','regular','light') and italic from CapCut font name and style.

    Returns (weight_token, italic)
    """
    italic = False
    weight_token = 'regular'

    # Inspect style attributes if present
    if style_obj is not None:
        try:
            italic = bool(getattr(style_obj, 'italic', False)) or bool(getattr(style_obj, 'is_italic', False))
        except Exception:
            pass
        try:
            # Numeric weight if provided
            w = getattr(style_obj, 'weight', None)
            if isinstance(w, (int, float)):
                if w >= 900:
                    weight_token = 'black'
                elif w >= 800:
                    weight_token = 'extra-bold'
                elif w >= 700:
                    weight_token = 'bold'
                elif w >= 600:
                    weight_token = 'semi-bold'
                elif w >= 500:
                    weight_token = 'medium'
                elif w >= 300:
                    weight_token = 'light'
                elif w >= 200:
                    weight_token = 'extra-light'
                else:
                    weight_token = 'regular'
        except Exception:
            pass

    # Parse from CapCut font code/name
    name = (capcut_font_name or '').lower()
    if 'italic' in name:
        # WARN: The expression below used to be `italic = True or italic`, which always evaluates to True.
        # Keeping logic unchanged, but this likely forces italic whenever 'italic' appears in the font name,
        # ignoring any prior italic setting. Intended behavior might have been `italic = italic or True`.
        italic = True or italic
    if any(tok in name for tok in ['black', 'blk']):
        weight_token = 'black'
    elif 'extrabold' in name or 'extra_bold' in name or 'xtrabold' in name:
        weight_token = 'extra-bold'
    elif 'semibold' in name or 'semi_bold' in name:
        weight_token = 'semi-bold'
    elif 'bold' in name:
        weight_token = 'bold'
    elif 'medium' in name:
        weight_token = 'medium'
    elif 'extralight' in name or 'extra_light' in name:
        weight_token = 'extra-light'
    elif 'light' in name:
        weight_token = 'light'
    elif 'thin' in name:
        weight_token = 'thin'

    return weight_token, italic

def _resolve_font_arguments(style_obj: Optional[object], segment_obj: Optional[object] = None) -> list[str]:
    """Resolve drawtext font arguments using pyfonts if available.

    Returns a list of drawtext arguments like [":fontfile='...'"] or [":font='Family'"].
    Raises ValueError if font resolution fails.
    """
    # Extract a CapCut style font name if present
    capcut_font_name: Optional[str] = None
    if style_obj is not None:
        for attr in ('font', 'font_name', 'family', 'fontFamily', 'font_family'):
            try:
                v = getattr(style_obj, attr, None)
                if isinstance(v, str) and v.strip():
                    capcut_font_name = v.strip()
                    break
            except Exception as e:
                raise ValueError(f"Failed to extract font name from style object: {e}") from e

    # Debug: log the incoming style object to aid troubleshooting in development
    print(f"style_obj: {style_obj}")
    # Debug: pause here when running interactively to inspect font resolution behavior
    # breakpoint()
    # If not provided, try fallbacks from the segment object (global or per-range font)
    if not capcut_font_name and segment_obj is not None:
        try:
            seg_font = getattr(segment_obj, 'font', None)
            seg_font_name = getattr(seg_font, 'name', None) if seg_font is not None else None
            if isinstance(seg_font_name, str) and seg_font_name.strip():
                capcut_font_name = seg_font_name.strip()
                print(f"[FONTDBG] using fallback from segment_data.font: {capcut_font_name}")
        except Exception:
            pass

        # Fallback to first per-range font if any
        if not capcut_font_name:
            try:
                ranges = getattr(segment_obj, 'text_styles', []) or []
                for r in ranges:
                    rf = getattr(r, 'font', None)
                    rf_name = getattr(rf, 'name', None) if rf is not None else None
                    if isinstance(rf_name, str) and rf_name.strip():
                        capcut_font_name = rf_name.strip()
                        print(f"[FONTDBG] using fallback from first text_styles font: {capcut_font_name}")
                        break
            except Exception:
                pass

    # If still not provided, we cannot resolve
    if not capcut_font_name:
        print("[FONTDBG] capcut_font_name missing; style_obj and segment fallbacks had no font-like attrs")
        raise ValueError("No font name specified in style object")

    # Check if pyfonts is available
    if not _HAS_PYFONTS:
        raise ValueError(f"pyfonts is required for font '{capcut_font_name}' but is not installed. Please install with: pip install pyfonts")

    # Map to Google Font family with normalization (underscore/hyphen and base family fallback)
    gf_family = CAPCUT_TO_GOOGLE_FONT.get(capcut_font_name)
    if not gf_family:
        alt_key = capcut_font_name.replace('-', '_')
        gf_family = CAPCUT_TO_GOOGLE_FONT.get(alt_key)
    if not gf_family:
        base_key = capcut_font_name.split('-', 1)[0]
        gf_family = CAPCUT_TO_GOOGLE_FONT.get(base_key, base_key)
    print(f"[FONTDBG] font map: '{capcut_font_name}' -> '{gf_family}'")
    weight_token, italic = _infer_font_style_tokens(capcut_font_name, style_obj)

    # Attempt resolution via pyfonts
    fontfile_path: Optional[str] = None
    resolution_error = None

    # Common API: pyfonts.load_google_font(name, weight=..., italic=...)
    if hasattr(pyfonts, 'load_google_font'):
        try:
            font_obj = pyfonts.load_google_font(gf_family, weight=weight_token, italic=italic)  # type: ignore
            # Accept direct path, or object with path-like attribute
            if isinstance(font_obj, str) and os.path.exists(font_obj):
                fontfile_path = font_obj
            else:
                # Handle matplotlib.font_manager.FontProperties objects
                if hasattr(font_obj, 'get_file'):
                    try:
                        p = font_obj.get_file()
                        if isinstance(p, str) and os.path.exists(p):
                            fontfile_path = p
                    except Exception:
                        pass
                
                # Handle other object types with path attributes  
                if not fontfile_path:
                    for attr in ('path', 'file', 'filename', 'fname', 'ttf_path', 'otf_path'):
                        p = getattr(font_obj, attr, None)
                        if isinstance(p, str) and os.path.exists(p):
                            fontfile_path = p
                            break
        except Exception as e:
            resolution_error = f"pyfonts.load_google_font failed for '{gf_family}' (weight={weight_token}, italic={italic}): {e}"

    # Alternative API: pyfonts.get_font_path(name, weight=..., italic=...)
    if fontfile_path is None and hasattr(pyfonts, 'get_font_path'):
        try:
            p = pyfonts.get_font_path(gf_family, weight=weight_token, italic=italic)  # type: ignore
            if isinstance(p, str) and os.path.exists(p):
                fontfile_path = p
        except Exception as e:
            if resolution_error:
                resolution_error += f"; pyfonts.get_font_path also failed: {e}"
            else:
                resolution_error = f"pyfonts.get_font_path failed for '{gf_family}' (weight={weight_token}, italic={italic}): {e}"

    if not fontfile_path:
        error_msg = f"Could not resolve font file for '{capcut_font_name}' (mapped to '{gf_family}', weight={weight_token}, italic={italic})"
        if resolution_error:
            error_msg += f": {resolution_error}"
        raise ValueError(error_msg)

    # Verify the font file exists
    if not os.path.exists(fontfile_path):
        raise ValueError(f"Resolved font file does not exist: {fontfile_path}")

    # Escape for filtergraph
    ff = (
        fontfile_path
        .replace("\\", "\\\\")
        .replace("'", "\\'")
    )
    return [f":fontfile='{ff}'"]

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
        # Preprocess: flatten all tracks into a single list of time-placed segments.
        # Each segment captures source media, target placement window, and z-order hints.
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
        # Tracks include native tracks and optionally imported tracks.
        # A segment's target_timerange indicates when it should appear in the final timeline.
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
        # CapCut normalized space is [-1,1] in both axes with (0,0) being center.
        # Convert to pixel coordinates centered on canvas for FFmpeg overlay.
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

        # Filtergraph structure overview:
        # - We start with a synthetic black background labeled [bg].
        # - For each visual segment (video/image/sticker/text), we produce a labeled video
        #   stream, align it in time with setpts (relative to the global timeline), and
        #   overlay it onto the running composition with enable=between(t,start,end).
        # - Text can be drawn inline with drawtext, or pre-rendered to alpha-preserving
        #   intermediates to reduce filter complexity. Pre-rendered text is then treated
        #   as a normal video input and overlaid.
        # - Audio segments are handled after video: each is trimmed, delayed into place,
        #   optionally sped up/slowed via atempo, and then all tracks are mixed with amix.
        # - The final labeled outputs are [final_video] and (if present) [final_audio].

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

        # Transition helper state: remember last video/image segment per track so we can
        # build transitions between adjacent clips on the same track.
        last_visual_segment_by_track: Dict[str, Tuple[int, CompositionSegment]] = {}
        # Cache effective durations (after speed) for segments we process, keyed by loop index
        effective_duration_by_loop_index: Dict[int, float] = {}

        for i, segment in enumerate(ordered_segments):
            if segment.track_type in ['video', 'image']:
                if segment.material_data and hasattr(segment.material_data, 'remote_url'):
                    video_url = segment.material_data.remote_url
                    if video_url:
                        if self._is_image_media(segment):
                            # Still images are fed as looping single-frame inputs with a fixed duration
                            seg_duration = max(0.0, segment.end_time - segment.start_time)
                            input_files.append(['-loop', '1', '-t', f"{seg_duration}", '-i', video_url])
                        else:
                            # Video inputs are fed directly; trimming happens in filtergraph
                            input_files.append(video_url)
                        video_filter = self._generate_video_segment_filter(
                            segment, stream_index, i, temp_dir
                        )
                        if video_filter:
                            filter_parts.append(video_filter)
                            # Shift segment into global timeline by adding a constant PTS offset
                            start = segment.start_time
                            filter_parts.append(f"[v{i}]setpts=PTS+{start}/TB[v{i}_ts]")
                            prev_layer = layer_outputs[-1]
                            ox, oy = self._overlay_coords(segment)
                            end = segment.end_time
                            # Overlay with enable between start and end, aligning center to (ox,oy)
                            filter_parts.append(
                                f"{prev_layer}[v{i}_ts]overlay={ox}-w/2:{oy}-h/2:enable='between(t\\,{start}\\,{end})'[layer{i+1}]"
                            )
                            layer_outputs.append(f"[layer{i+1}]")

                            # --- Transition: If there is a previous visual segment on the same track,
                            # and it requests a Pull In/Out transition into this segment, build a
                            # zoomed crossfade for the overlap window and overlay it at correct z-order.
                            # Determine this segment's effective duration (after speed)
                            speed_obj = getattr(segment.segment_data, 'speed', None)
                            speed_factor = getattr(speed_obj, 'speed', 1.0) if speed_obj is not None else 1.0
                            try:
                                speed_factor = float(speed_factor) if speed_factor else 1.0
                            except Exception:
                                speed_factor = 1.0
                            eff_duration_curr = max(0.0, (segment.end_time - segment.start_time) / (speed_factor if speed_factor != 0 else 1.0))
                            effective_duration_by_loop_index[i] = eff_duration_curr

                            last_tuple = last_visual_segment_by_track.get(segment.track_name)
                            if last_tuple is not None:
                                prev_loop_index, prev_seg = last_tuple
                                # Read transition parameters from previous segment (preferred) or current
                                def _extract_transition_info(obj: object) -> Tuple[Optional[str], Optional[float]]:
                                    name_candidate: Optional[str] = None
                                    duration_seconds: Optional[float] = None
                                    if obj is None:
                                        return None, None
                                    # Try common name attributes
                                    for attr in ('name', 'transition_name'):
                                        try:
                                            val = getattr(obj, attr, None)
                                            if isinstance(val, str) and val.strip():
                                                name_candidate = val.strip()
                                                break
                                        except Exception:
                                            pass
                                    # Try type/enum-ish attributes
                                    if name_candidate is None:
                                        for attr in ('transition_type', 'type', 'enum', 'effect', 'meta', 'effect_meta'):
                                            try:
                                                val = getattr(obj, attr, None)
                                                if isinstance(val, str) and val.strip():
                                                    name_candidate = val.strip()
                                                    break
                                                # If it's an object with a name/display name
                                                for sub_attr in ('name', 'transition_name', 'display_name'):
                                                    try:
                                                        sub = getattr(val, sub_attr, None)
                                                        if isinstance(sub, str) and sub.strip():
                                                            name_candidate = sub.strip()
                                                            break
                                                    except Exception:
                                                        pass
                                                if name_candidate is not None:
                                                    break
                                            except Exception:
                                                pass
                                    # Duration: prefer microseconds if present
                                    for dur_attr in ('duration', 'duration_us', 'duration_microseconds', 'duration_ms'):
                                        try:
                                            dval = getattr(obj, dur_attr, None)
                                            if isinstance(dval, (int, float)):
                                                # Heuristic: if very large, it is microseconds; if moderate, could be ms
                                                if dur_attr.endswith(('us', 'microseconds')) or dval > 10000:
                                                    duration_seconds = float(dval) / 1_000_000.0
                                                elif dur_attr.endswith('ms'):
                                                    duration_seconds = float(dval) / 1000.0
                                                else:
                                                    duration_seconds = float(dval)
                                                break
                                        except Exception:
                                            pass
                                    return name_candidate, duration_seconds

                                # Prefer explicit metadata stored by add_video_track
                                trans_name_str = getattr(getattr(prev_seg, 'segment_data', None), '_cc_transition_enum_name', None)
                                trans_dur_sec = getattr(getattr(prev_seg, 'segment_data', None), '_cc_transition_duration_sec', None)
                                if not trans_name_str:
                                    trans_name_str = getattr(getattr(segment, 'segment_data', None), '_cc_transition_enum_name', None)
                                if trans_dur_sec is None:
                                    trans_dur_sec = getattr(getattr(prev_seg, 'segment_data', None), '_cc_transition_duration_sec', None)
                                if trans_dur_sec is None:
                                    trans_dur_sec = getattr(getattr(segment, 'segment_data', None), '_cc_transition_duration_sec', None)
                                # As a last resort, attempt to extract from raw transition object (older behavior)
                                if not trans_name_str or trans_dur_sec is None:
                                    prev_trans_obj = getattr(getattr(prev_seg, 'segment_data', None), 'transition', None)
                                    curr_trans_obj = getattr(getattr(segment, 'segment_data', None), 'transition', None)
                                    name_fallback, dur_fallback = _extract_transition_info(prev_trans_obj)
                                    if not name_fallback and curr_trans_obj is not None:
                                        name_fallback, dur_fallback = _extract_transition_info(curr_trans_obj)
                                    trans_name_str = trans_name_str or name_fallback
                                    trans_dur_sec = trans_dur_sec if trans_dur_sec is not None else dur_fallback
                                # Hard rule: only transition_duration controls transition time
                                # If still None, treat as 0 (no transition)
                                if trans_dur_sec is None:
                                    trans_dur_sec = 0.0

                                # Normalize and check using centralized LUT
                                trans_name_norm = str(trans_name_str).strip().lower().replace(' ', '_') if isinstance(trans_name_str, str) else ''
                                enum_name = TRANSITION_NAME_LUT.get(trans_name_norm, trans_name_norm)
                                # WARN: Comparison below relies on exact strings 'Pull_in' and 'Pull_Out'.
                                # If LUT values differ in case/underscore (e.g., 'pull_in', 'Pull Out'), it will fail.
                                # Keeping logic unchanged; consider normalizing enum values in LUT or here.
                                is_pull_in = enum_name == 'Pull_in'
                                is_pull_out = enum_name == 'Pull_Out'
                                print(
                                    f"[XFADE] track='{segment.track_name}' prev_idx={prev_loop_index} curr_idx={i} "
                                    f"raw='{trans_name_str}' norm='{trans_name_norm}' enum='{enum_name}' "
                                    f"pull_in={is_pull_in} pull_out={is_pull_out}"
                                )

                                # Only when clips butt-join to avoid gaps
                                joins_cleanly = abs(prev_seg.end_time - segment.start_time) < 1e-4

                                if (is_pull_in or is_pull_out) and joins_cleanly and isinstance(trans_dur_sec, (int, float)) and trans_dur_sec > 0:
                                    # Clamp overlap to available tails/heads (after speed)
                                    prev_speed_obj = getattr(prev_seg.segment_data, 'speed', None)
                                    prev_speed_factor = getattr(prev_speed_obj, 'speed', 1.0) if prev_speed_obj is not None else 1.0
                                    try:
                                        prev_speed_factor = float(prev_speed_factor) if prev_speed_factor else 1.0
                                    except Exception:
                                        prev_speed_factor = 1.0
                                    eff_duration_prev = effective_duration_by_loop_index.get(prev_loop_index)
                                    if eff_duration_prev is None:
                                        eff_duration_prev = max(0.0, (prev_seg.end_time - prev_seg.start_time) / (prev_speed_factor if prev_speed_factor != 0 else 1.0))
                                        effective_duration_by_loop_index[prev_loop_index] = eff_duration_prev

                                    d = float(trans_dur_sec)
                                    d = max(0.0, min(d, eff_duration_prev, eff_duration_curr))
                                    print(
                                        f"[XFADE] Using transition enum='{enum_name}' duration={d:.3f}s (requested={trans_dur_sec}) "
                                        f"prev_eff={eff_duration_prev:.3f}s curr_eff={eff_duration_curr:.3f}s join_ok={joins_cleanly}"
                                    )

                                    if d > 1e-3:
                                        # Labels for tails/heads and transition
                                        a_tail = f"v{prev_loop_index}_tail"
                                        b_head = f"v{i}_head"
                                        trans_label = f"v{prev_loop_index}_{i}_trans"

                                        # Trim last d seconds of A (prev) and first d seconds of B (curr)
                                        # Both [vX] streams already include base transforms and speed effects
                                        filter_parts.append(f"[v{prev_loop_index}]trim={eff_duration_prev - d}:{eff_duration_prev},setpts=PTS-STARTPTS[{a_tail}]")
                                        filter_parts.append(f"[v{i}]trim=0:{d},setpts=PTS-STARTPTS[{b_head}]")

                                        # Determine window [t0, startB]
                                        t0 = max(0.0, segment.start_time - d)

                                        # Split current composed base into two window copies and a carry stream
                                        baseA = f"v{prev_loop_index}_{i}_baseA"
                                        baseB = f"v{prev_loop_index}_{i}_baseB"
                                        carry = f"v{prev_loop_index}_{i}_carry"
                                        prev_layer_after_b = layer_outputs[-1]
                                        filter_parts.append(f"{prev_layer_after_b}split=3[{baseA}][{baseB}][{carry}]")

                                        # Trim each base copy to the transition window and reset PTS
                                        baseA_w = f"v{prev_loop_index}_{i}_baseA_w"
                                        baseB_w = f"v{prev_loop_index}_{i}_baseB_w"
                                        filter_parts.append(f"[{baseA}]trim={t0}:{segment.start_time},setpts=PTS-STARTPTS[{baseA_w}]")
                                        filter_parts.append(f"[{baseB}]trim={t0}:{segment.start_time},setpts=PTS-STARTPTS[{baseB_w}]")

                                        # Overlay the trimmed tails/heads onto the windowed base copies to get full frames
                                        ox_prev, oy_prev = self._overlay_coords(prev_seg)
                                        ox_curr, oy_curr = self._overlay_coords(segment)
                                        A_full = f"v{prev_loop_index}_{i}_A_full"
                                        B_full = f"v{prev_loop_index}_{i}_B_full"
                                        filter_parts.append(f"[{baseA_w}][{a_tail}]overlay={ox_prev}-w/2:{oy_prev}-h/2[{A_full}]")
                                        filter_parts.append(f"[{baseB_w}][{b_head}]overlay={ox_curr}-w/2:{oy_curr}-h/2[{B_full}]")

                                        # Normalize to constant frame rate and pixel format for xfade stability
                                        A_full_cfr = f"v{prev_loop_index}_{i}_A_full_cfr"
                                        B_full_cfr = f"v{prev_loop_index}_{i}_B_full_cfr"
                                        filter_parts.append(f"[{A_full}]fps=fps={self.fps},format=yuv420p[{A_full_cfr}]")
                                        filter_parts.append(f"[{B_full}]fps=fps={self.fps},format=yuv420p[{B_full_cfr}]")

                                        # Choose xfade transition type and run between full frames
                                        xfade_type = 'zoomin' if is_pull_in else 'zoomout'
                                        filter_parts.append(f"[{A_full_cfr}][{B_full_cfr}]xfade=transition={xfade_type}:duration={d}:offset=0[{trans_label}]")
                                        print(
                                            f"[XFADE] Built full-frame xfade type='{xfade_type}' between idx {prev_loop_index}->{i} over d={d:.3f}s"
                                        )

                                        # Remove black fill from xfade by keying out near-black and creating alpha
                                        trans_label_ck = f"{trans_label}_ck"
                                        filter_parts.append(f"[{trans_label}]format=rgba,chromakey=0x000000:0.02:0.0[{trans_label_ck}]")

                                        # Align to global timeline and overlay only during the transition window
                                        filter_parts.append(f"[{trans_label_ck}]setpts=PTS+{t0}/TB[{trans_label}_ts]")
                                        filter_parts.append(
                                            f"[{carry}][{trans_label}_ts]overlay=0:0:enable='between(t\\,{t0}\\,{segment.start_time})'[layer{i+1}_tr]"
                                        )
                                        print(
                                            f"[XFADE] Overlaying transition window [{t0:.3f}, {segment.start_time:.3f}]s on track='{segment.track_name}'"
                                        )
                                        layer_outputs.append(f"[layer{i+1}_tr]")
                                    else:
                                        print(
                                            f"[XFADE][WARN] Skipping transition enum='{enum_name}': effective duration too small (d={d:.4f}s)"
                                        )
                                else:
                                    print(
                                        f"[XFADE] Transition not applied: enum='{enum_name}', join_ok={joins_cleanly}, "
                                        f"trans_dur='{trans_dur_sec}', pull_in={is_pull_in}, pull_out={is_pull_out}"
                                    )

                            # Update last segment for this track after processing this segment
                            last_visual_segment_by_track[segment.track_name] = (i, segment)
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
                    # Use prerendered alpha video for text to simplify final filtergraph
                    input_files.append(text_intermediate_files[text_idx])
                    filter_parts.append(f"[{stream_index}:v]setpts=PTS+{start}/TB[text{i}_ts]")
                    filter_parts.append(
                        f"{prev_layer}[text{i}_ts]overlay=0:0:enable='between(t\\,{start}\\,{end})'[layer{i+1}]"
                    )
                    layer_outputs.append(f"[layer{i+1}]")
                    stream_index += 1
                else:
                    # Fall back to inline drawtext on the current composed layer
                    text_filter = self._generate_text_segment_filter(segment, i, temp_dir)
                    if text_filter:
                        filter_parts.append(f"{prev_layer}{text_filter}[layer{i+1}]")
                        layer_outputs.append(f"[layer{i+1}]")
                # WARN: The ordering of prerendered text intermediates is based on render_index only in
                # _prerender_text_segments, while here segments are ordered by (render_index, z_index).
                # In rare cases this could misalign text files to segments. Logic unchanged.
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

        # Apply timing - trim to segment duration or to source_timerange if provided.
        # setpts=PTS-STARTPTS re-bases timestamps to start at 0 for subsequent transforms.
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
                    # Multiply input dimensions by normalized scale factors
                    transform_filters.append(f"scale=iw*{scale_x}:ih*{scale_y}")

            # Opacity
            if hasattr(clip_settings, 'alpha'):
                alpha = getattr(clip_settings, 'alpha', 1.0)
                if alpha != 1.0:
                    # Ensure RGBA before adjusting alpha via colorchannelmixer
                    transform_filters.append(f"format=rgba,colorchannelmixer=aa={alpha}")

            # Rotation
            if hasattr(clip_settings, 'rotation'):
                rotation = getattr(clip_settings, 'rotation', 0.0)
                if rotation != 0.0:
                    # FFmpeg rotate uses radians; CapCut rotation is in degrees
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
            # Video speed-up/down by dividing PTS
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
                    # WARN: FFmpeg does not have a 'translate' filter for video frames. Positioning typically uses
                    # 'overlay' with x/y or 'lut'/'geq' for per-pixel ops. This 'translate' link likely has no effect
                    # or will cause a filtergraph error if executed in isolation. Logic unchanged.
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

        # Background properties
        background_enabled = False
        background_color = "black@0.5"  # Default transparent black

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

        # Extract background properties from segment data
        background_data = getattr(segment_data, 'background', None)
        if background_data:
            try:
                # Import hex_to_rgb utility
                from util import hex_to_rgb

                bg_alpha = getattr(background_data, 'alpha', 0.0)
                bg_round_radius = getattr(background_data, 'round_radius', 0.0)

                # Throw error for rounded corners (not supported yet)
                if bg_round_radius > 0:
                    raise NotImplementedError("Rounded corners for text backgrounds are not supported yet")

                if bg_alpha > 0:  # Only enable background if alpha > 0
                    background_enabled = True

                    # Convert background color from hex to FFmpeg format
                    bg_color_hex = getattr(background_data, 'color', '#000000')
                    if isinstance(bg_color_hex, str) and bg_color_hex.startswith('#'):
                        try:
                            r, g, b = hex_to_rgb(bg_color_hex)
                            r_i = max(0, min(255, int(round(r * 255))))
                            g_i = max(0, min(255, int(round(g * 255))))
                            b_i = max(0, min(255, int(round(b * 255))))
                            background_color = f"0x{r_i:02x}{g_i:02x}{b_i:02x}@{bg_alpha}"
                        except Exception:
                            # Fallback to default if color conversion fails
                            background_color = f"black@{bg_alpha}"
                    else:
                        background_color = f"black@{bg_alpha}"

            except NotImplementedError:
                raise  # Re-raise the rounded corners error
            except Exception:
                # If background processing fails, disable background
                background_enabled = False

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
        text_filter_parts = [
            f"drawtext=text='{text_content}'",
            f":fontsize={font_size}",
            f":fontcolor={font_color}",
        ]

        # Add font resolution arguments (fontfile or font family)
        print("[FONTDBG] style has font attr?", hasattr(style, "font") if style else "no style",
              "segment_data.font:", getattr(segment_data, "font", None),
              "num text_styles:", len(getattr(segment_data, "text_styles", []) or []),
              "range fonts:", [getattr(r, "font", None) for r in (getattr(segment_data, "text_styles", []) or [])])
        text_filter_parts.extend(_resolve_font_arguments(style, segment_data))

        text_filter_parts.extend([
            f":x={position_x}",
            f":y={position_y}",
            f":enable='between(t\\,{segment.start_time}\\,{segment.end_time})'"
        ])

        # Add background parameters if enabled
        if background_enabled:
            text_filter_parts.extend([
                f":box=1",
                f":boxcolor={background_color}"
            ])

        text_filter = "".join(text_filter_parts)

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
            # adelay expects milliseconds; all=1 delays all channels equally
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
                # WARN: For remaining_speed > 2.0 the code appends 'atempo=0.5' and multiplies remaining_speed by 0.5.
                # This tends to cancel out later 'atempo' factors (e.g., 4.0 → 0.5, then appends 2.0 → net 1.0).
                # Likely intended to decompose factor into a product of values within [0.5, 2.0] using 2.0 segments.
                # Logic preserved as-is.
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
            # Map the generated silent source to final_audio to keep muxer happy
            filter_parts.append(f"[{current_stream_index}:a]anull[final_audio]")

        return filter_parts


def _prerender_text_segments(engine: VideoCompositionEngine, temp_dir: str) -> List[Optional[str]]:
    """Pre-render text segments to alpha-preserving intermediates.

    Each intermediate has duration equal to the text segment duration and baked-in position.
    Timing is applied at final overlay stage, not inside the prerender.
    Returns a list of file paths (or None) aligned with the order of text segments in generate_ffmpeg_filter_complex.
    """
    # Collect text segments in the exact same order used in generate_ffmpeg_filter_complex
    # to ensure indices align when consuming intermediates during overlay.
    ordered_segments = sorted(engine.segments, key=lambda s: (s.render_index, s.z_index))
    text_segments = [s for s in ordered_segments if s.track_type == 'text']

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

        # Extract background properties for prerendered text
        background_enabled = False
        background_color = "black@0.5"

        background_data = getattr(segment_data, 'background', None)
        if background_data:
            try:
                from util import hex_to_rgb

                bg_alpha = getattr(background_data, 'alpha', 0.0)
                bg_round_radius = getattr(background_data, 'round_radius', 0.0)

                # Throw error for rounded corners (not supported yet)
                if bg_round_radius > 0:
                    raise NotImplementedError("Rounded corners for text backgrounds are not supported yet")

                if bg_alpha > 0:
                    background_enabled = True

                    bg_color_hex = getattr(background_data, 'color', '#000000')
                    if isinstance(bg_color_hex, str) and bg_color_hex.startswith('#'):
                        try:
                            r, g, b = hex_to_rgb(bg_color_hex)
                            r_i = max(0, min(255, int(round(r * 255))))
                            g_i = max(0, min(255, int(round(g * 255))))
                            b_i = max(0, min(255, int(round(b * 255))))
                            background_color = f"0x{r_i:02x}{g_i:02x}{b_i:02x}@{bg_alpha}"
                        except Exception:
                            background_color = f"black@{bg_alpha}"
                    else:
                        background_color = f"black@{bg_alpha}"

            except NotImplementedError:
                raise  # Re-raise the rounded corners error
            except Exception:
                background_enabled = False

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
            f"color=s={engine.width}x{engine.height}:r={engine.fps}:d={duration}:c=black@0.0,format=rgba"
        )

        # Build text filter with background support
        text_filter_parts = [
            f"drawtext=text='{text_content}'",
            f":fontsize={font_size}",
            f":fontcolor={font_color}",
        ]

        # Add font resolution arguments (fontfile or font family)
        print("[FONTDBG] prerender style has font?", hasattr(style, "font") if style else "no style",
              "segment_data.font:", getattr(segment_data, "font", None),
              "num text_styles:", len(getattr(segment_data, "text_styles", []) or []),
              "range fonts:", [getattr(r, "font", None) for r in (getattr(segment_data, "text_styles", []) or [])])
        text_filter_parts.extend(_resolve_font_arguments(style, segment_data))

        # Add positioning
        text_filter_parts.extend([
            f":x={position_x}",
            f":y={position_y}",
        ])

        if background_enabled:
            text_filter_parts.extend([
                f":box=1:boxcolor={background_color}"
            ])

        text_filter = "".join(text_filter_parts)

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


# ------------------------------ Modular helpers (non-behavioral) ------------------------------

def _determine_draft_id_from_inputs(yaml_config: Optional[str], draft_id: Optional[str]) -> str:
    """Resolve and return a draft_id from provided inputs.

    This wraps the exact logic used inline in export_to_video_impl without changing behavior.
    """
    # Input validation mirrors export_to_video_impl
    if yaml_config and draft_id:
        raise ValueError("Cannot specify both yaml_config and draft_id")
    if not yaml_config and not draft_id:
        raise ValueError("Must specify either yaml_config or draft_id")

    if yaml_config:
        # Import lazily to preserve original import location and side effects
        from CapCutAPI import parse_yaml_config
        if os.path.isfile(yaml_config):
            result = parse_yaml_config(yaml_config)
        else:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                f.write(yaml_config)
                temp_yaml_path = f.name
            try:
                result = parse_yaml_config(temp_yaml_path)
            finally:
                if os.path.exists(temp_yaml_path):
                    os.unlink(temp_yaml_path)
        draft_id_resolved = result.get('draft_id')
        if not draft_id_resolved:
            raise ValueError("Failed to parse YAML config or create draft")
        return draft_id_resolved

    # If we reach here, draft_id must be provided and valid per original validation
    return str(draft_id)


def _attach_prerendered_text(engine: VideoCompositionEngine, temp_dir: str, logger: logging.Logger) -> None:
    """Populate engine.text_intermediate_files with prerendered text intermediates.

    Keeps original try/except behavior and logs.
    """
    try:
        engine.text_intermediate_files = _prerender_text_segments(engine, temp_dir)
        logger.info(f"Pre-rendered {len([p for p in engine.text_intermediate_files if p])} text segments")
    except Exception as _e:
        logger.warning(f"Text pre-render failed, falling back to inline drawtext: {_e}")
        engine.text_intermediate_files = None


def _build_full_filter_complex(video_fc: str, audio_fc: str) -> str:
    """Combine video and audio filter_complex strings identically to inline behavior."""
    if audio_fc:
        return (video_fc + ("; " if video_fc else "") + audio_fc)
    return video_fc


def _extend_ffmpeg_inputs(ffmpeg_cmd: List[str], input_files: List[Union[str, List[str]]]) -> None:
    """Append inputs to ffmpeg command, preserving original structure and order."""
    for input_item in input_files:
        if isinstance(input_item, list):
            ffmpeg_cmd.extend(input_item)
        else:
            ffmpeg_cmd.extend(['-i', input_item])


def _build_ffmpeg_cmd(
    input_files: List[Union[str, List[str]]],
    filter_complex: str,
    audio_filter_complex: str,
    export_config: VideoExportConfig,
    output_path: str
) -> List[str]:
    """Construct the ffmpeg command list exactly like the original implementation."""
    cmd: List[str] = [
        'ffmpeg',
        '-y',
        '-hide_banner',
        '-loglevel', 'info'
    ]
    _extend_ffmpeg_inputs(cmd, input_files)

    full_fc = _build_full_filter_complex(filter_complex, audio_filter_complex)
    cmd.extend([
        '-filter_complex', full_fc,
        '-map', '[final_video]',
        '-c:v', export_config.codec if export_config else 'libx264',
        '-preset', export_config.preset if export_config else 'medium',
        '-crf', export_config.crf if export_config else '23',
        '-b:v', export_config.video_bitrate if export_config else '8000k',
        '-r', str(export_config.fps if export_config else 30),
        '-pix_fmt', 'yuv420p',
    ])

    if audio_filter_complex:
        cmd.extend([
            '-map', '[final_audio]',
            '-c:a', export_config.audio_codec if export_config else 'aac',
            '-b:a', export_config.audio_bitrate if export_config else '128k',
            '-ac', str(export_config.audio_channels if export_config else 2),
            '-ar', str(export_config.audio_sample_rate if export_config else 44100),
        ])
    else:
        cmd.extend(['-an'])

    cmd.append(output_path)
    return cmd


# ------------------------------ Multi-pass pipeline helpers ------------------------------

def _transparent_clip(engine: VideoCompositionEngine, duration: float, temp_dir: str, tag: str) -> str:
    """Create a transparent full-canvas clip of the requested duration.

    Uses a fast intra codec with alpha. Duration is clamped to non-negative.
    """
    d = max(0.0, float(duration))
    out_path = os.path.join(temp_dir, f"gap_{tag}_{abs(hash((tag, d))) & 0xFFFF:x}.mov")
    cmd = [
        'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
        '-f', 'lavfi', '-i', f"color=c=black@0:size={engine.width}x{engine.height}:r={engine.fps}:d={d}",
        '-c:v', 'qtrle', '-pix_fmt', 'argb', '-r', str(engine.fps),
        out_path
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return out_path


def _render_visual_segment_clip(engine: VideoCompositionEngine, segment: CompositionSegment, temp_dir: str,
                                text_intermediate_map: Dict[int, Optional[str]]) -> Optional[str]:
    """Render a single visual segment (video/image/text) to a full-canvas clip with alpha.

    - Video/Image: trims to source/target, applies transforms, overlays onto transparent canvas
    - Text: uses prerendered intermediate for the specific text segment
    Returns output path or None on skip.
    """
    seg_type = segment.track_type

    # Text: reuse prerendered file
    if seg_type == 'text':
        # text_intermediate_map is keyed by the global ordered text index
        idx = getattr(segment.segment_data, '_text_global_index', None)
        if idx is None:
            return None
        return text_intermediate_map.get(idx) or None

    if seg_type not in ['video', 'image']:
        return None

    material = segment.material_data
    if not material or not hasattr(material, 'remote_url') or not material.remote_url:
        return None

    duration = max(0.0, segment.end_time - segment.start_time)
    if duration <= 0:
        return None

    # Inputs:
    #   0: transparent canvas
    #   1: source media (video or image)
    canvas = f"color=c=black@0:size={engine.width}x{engine.height}:r={engine.fps}:d={duration}"

    inputs: List[Union[str, List[str]]] = [['-f', 'lavfi', '-i', canvas]]
    source_url: str = material.remote_url

    # Image vs video handling for input 1
    if engine._is_image_media(segment):
        inputs.append(['-loop', '1', '-t', f"{duration}", '-i', source_url])
    else:
        inputs.append(source_url)

    # Build per-segment filter
    filters: List[str] = []
    base_stream = "[1:v]"

    # Source trim based on source_timerange or duration
    segment_data = segment.segment_data
    source_range = getattr(segment_data, 'source_timerange', None)
    if source_range is not None:
        start_offset = source_range.start / 1_000_000.0
        source_duration = max(0.0, source_range.duration / 1_000_000.0)
        filters.append(f"{base_stream}trim={start_offset}:{start_offset + source_duration},setpts=PTS-STARTPTS[V1]")
    else:
        filters.append(f"{base_stream}trim=0:{duration},setpts=PTS-STARTPTS[V1]")

    # Transforms: scale, opacity, rotation
    transform_filters: List[str] = []
    clip_settings = getattr(segment_data, 'clip_settings', None)
    if clip_settings is not None:
        if hasattr(clip_settings, 'scale_x') and hasattr(clip_settings, 'scale_y'):
            sx = getattr(clip_settings, 'scale_x', 1.0) or 1.0
            sy = getattr(clip_settings, 'scale_y', 1.0) or 1.0
            if sx != 1.0 or sy != 1.0:
                transform_filters.append(f"scale=iw*{sx}:ih*{sy}")
        if hasattr(clip_settings, 'alpha'):
            a = getattr(clip_settings, 'alpha', 1.0)
            if a != 1.0:
                transform_filters.append("format=rgba,colorchannelmixer=aa={}".format(a))
        if hasattr(clip_settings, 'rotation'):
            deg = getattr(clip_settings, 'rotation', 0.0)
            if deg:
                transform_filters.append(f"rotate={deg}*PI/180")

    if transform_filters:
        filters.append("[V1]" + ",".join(transform_filters) + "[V1]")

    # Speed
    speed_obj = getattr(segment_data, 'speed', None)
    if speed_obj is not None and hasattr(speed_obj, 'speed'):
        try:
            spd = float(speed_obj.speed)
        except Exception:
            spd = 1.0
        if spd and spd != 1.0:
            filters.append(f"[V1]setpts=PTS/{spd}[V1]")

    # Compute overlay coordinates
    ox, oy = engine._overlay_coords(segment)

    # Compose on transparent canvas
    filters.append(f"[0:v][V1]overlay=x={ox}-w/2:y={oy}-h/2:shortest=1:format=auto[V]")

    filter_complex = "; ".join(filters)

    # Output path
    out_path = os.path.join(temp_dir, f"seg_{segment.track_name}_{segment.z_index}_{abs(hash((segment.start_time, segment.end_time))) & 0xFFFF:x}.mov")

    # Assemble command
    cmd: List[str] = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error']
    _extend_ffmpeg_inputs(cmd, inputs)
    cmd.extend([
        '-filter_complex', filter_complex,
        '-map', '[V]',
        '-c:v', 'qtrle', '-pix_fmt', 'argb', '-r', str(engine.fps),
        out_path
    ])

    subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=temp_dir)
    return out_path


def _concat_full_track(engine: VideoCompositionEngine, parts: List[str], temp_dir: str, track_key: str) -> str:
    """Concatenate a list of clip paths into a single track video with alpha, enforcing fps/pix_fmt.
    Uses concat filter for reliability (inputs must match geometry/fps/pix_fmt which we enforce on creation).
    """
    # If only one part, optionally normalize and return
    if not parts:
        # Produce a full-duration transparent track
        return _transparent_clip(engine, engine.duration_seconds, temp_dir, f"track_{track_key}_empty")
    if len(parts) == 1:
        # Ensure output clip is present; still rewrap to normalize if needed
        single = parts[0]
        out_path = os.path.join(temp_dir, f"track_{track_key}.mov")
        cmd = [
            'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
            '-i', single,
            '-c:v', 'qtrle', '-pix_fmt', 'argb', '-r', str(engine.fps),
            out_path
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=temp_dir)
        return out_path

    # Build concat filter over N inputs
    in_cmd: List[str] = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error']
    for p in parts:
        in_cmd.extend(['-i', p])
    n = len(parts)
    filter_str = ''.join(f"[{i}:v]" for i in range(n)) + f"concat=n={n}:v=1:a=0[V]"
    out_path = os.path.join(temp_dir, f"track_{track_key}.mov")
    in_cmd.extend(['-filter_complex', filter_str, '-map', '[V]', '-c:v', 'qtrle', '-pix_fmt', 'argb', '-r', str(engine.fps), out_path])
    subprocess.run(in_cmd, check=True, capture_output=True, text=True, cwd=temp_dir)
    return out_path


def _build_visual_tracks(engine: VideoCompositionEngine, temp_dir: str) -> Tuple[Dict[str, str], List[Tuple[str, int]]]:
    """Render visual segments per track into full-duration track videos with alpha.

    Returns:
      - track_name -> track_video_path
      - ordered list of (track_name, render_index) to preserve overlay order
    """
    # Prepare text intermediate index mapping
    ordered = sorted(engine.segments, key=lambda s: (s.render_index, s.z_index))
    text_index = 0
    text_map: Dict[int, Optional[str]] = {}
    # If prerendered files exist, attach indices to segments and map index->path
    text_files = getattr(engine, 'text_intermediate_files', None) or []
    for seg in ordered:
        if seg.track_type == 'text':
            setattr(seg.segment_data, '_text_global_index', text_index)
            text_map[text_index] = text_files[text_index] if text_index < len(text_files) else None
            text_index += 1

    # Group by track
    from collections import defaultdict as _dd
    by_track: Dict[str, Dict[str, Any]] = _dd(lambda: {'render_index': 0, 'track_type': '', 'segments': []})
    for seg in ordered:
        k = seg.track_name
        if not by_track[k]['segments']:
            by_track[k]['render_index'] = seg.render_index
            by_track[k]['track_type'] = seg.track_type
        by_track[k]['segments'].append(seg)

    track_videos: Dict[str, str] = {}
    order_list: List[Tuple[str, int]] = []

    for track_name, info in by_track.items():
        if info['track_type'] not in ['video', 'image', 'text']:
            # Skip non-visual tracks
            continue
        order_list.append((track_name, info['render_index']))

        # Build timeline with gaps
        clips: List[str] = []
        cursor = 0.0
        for seg in info['segments']:
            if seg.start_time > cursor + 1e-6:
                # Insert transparent gap
                gap_dur = seg.start_time - cursor
                gap_path = _transparent_clip(engine, gap_dur, temp_dir, f"{track_name}_gap_{len(clips)}")
                clips.append(gap_path)
                cursor = seg.start_time

            # Render/collect segment clip
            clip_path = _render_visual_segment_clip(engine, seg, temp_dir, text_map)
            if clip_path:
                clips.append(clip_path)
            cursor = max(cursor, seg.end_time)

        # Trailing gap to full duration
        if cursor < engine.duration_seconds - 1e-6:
            tail_gap = _transparent_clip(engine, engine.duration_seconds - cursor, temp_dir, f"{track_name}_trail")
            clips.append(tail_gap)

        track_key = track_name.replace(' ', '_')
        track_out = _concat_full_track(engine, clips, temp_dir, track_key)
        track_videos[track_name] = track_out

    # Overlay order by render_index asc
    order_list.sort(key=lambda t: t[1])
    return track_videos, order_list


def _compose_final_from_tracks(engine: VideoCompositionEngine,
                               track_videos: Dict[str, str],
                               overlay_order: List[Tuple[str, int]],
                               temp_dir: str,
                               export_config: VideoExportConfig,
                               output_path: str) -> None:
    """Compose full-canvas track videos over a background and mix audio segments.

    Reuses the existing audio graph builder to avoid regressions for audio behavior.
    """
    inputs: List[Union[str, List[str]]] = []

    # Background (index 0)
    bg = f"color=c=black:size={engine.width}x{engine.height}:r={engine.fps}:d={engine.duration_seconds}"
    inputs.append(['-f', 'lavfi', '-i', bg])

    # Track videos (indices 1..N)
    ordered_tracks = [name for name, _ in overlay_order if name in track_videos]
    for name in ordered_tracks:
        inputs.append(track_videos[name])

    # Build video overlay chain
    parts: List[str] = []
    if len(ordered_tracks) == 0:
        parts.append("[0:v]null[final_video]")
    else:
        # Begin with background
        current = "[0:v]"
        for i in range(len(ordered_tracks)):
            parts.append(f"{current}[{i+1}:v]overlay=0:0[lay{i+1}]")
            current = f"[lay{i+1}]"
        parts.append(f"{current}null[final_video]")

    # Audio: reuse existing audio graph builder
    audio_segments = [s for s in engine.segments if s.track_type == 'audio']
    audio_parts: List[str] = []
    if audio_segments:
        audio_parts = engine._build_audio_mix_graph(audio_segments, start_stream_index=1 + len(ordered_tracks), input_files=inputs)  # type: ignore[attr-defined]

    video_fc = "; ".join(parts)
    audio_fc = "; ".join(audio_parts) if audio_parts else ""
    # Build and run final ffmpeg
    cmd = _build_ffmpeg_cmd(inputs, video_fc, audio_fc, export_config, output_path)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=temp_dir)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg final compose failed (return code {result.returncode}): {result.stderr}")

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

    # Default export config
    if export_config is None:
        export_config = VideoExportConfig(output_path=output_path)

    try:
        logger.info(f"Starting video export to: {output_path}")

        # Resolve or validate draft_id via modular helper while preserving logs
        if yaml_config:
            logger.info("Processing YAML config...")
            resolved_draft_id = _determine_draft_id_from_inputs(yaml_config=yaml_config, draft_id=None)
            draft_id = resolved_draft_id
            logger.info(f"Created draft from YAML: {draft_id}")
        else:
            # This also re-validates inputs and echoes original error messages
            resolved_draft_id = _determine_draft_id_from_inputs(yaml_config=None, draft_id=draft_id)
            draft_id = resolved_draft_id

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

            # Pre-render text segments to intermediates to reduce filter graph complexity (existing behavior)
            _attach_prerendered_text(engine, temp_dir, logger)

            # Gate multipass behind environment variable to avoid regressions by default
            use_multipass = str(os.environ.get('CAPCUT_USE_MULTIPASS', '')).strip().lower() in {'1', 'true', 'yes', 'on'}
            if use_multipass:
                used_multipass = False
                try:
                    logger.info("Multipass enabled: building visual tracks…")
                    track_videos, overlay_order = _build_visual_tracks(engine, temp_dir)
                    logger.info(f"Multipass: built {len(track_videos)} visual track(s)")

                    logger.info("Multipass: composing final output from tracks…")
                    _compose_final_from_tracks(
                        engine=engine,
                        track_videos=track_videos,
                        overlay_order=overlay_order,
                        temp_dir=temp_dir,
                        export_config=export_config,
                        output_path=output_path,
                    )
                    used_multipass = True
                except Exception as mp_err:
                    logger.warning(f"Multipass pipeline failed; falling back to monolithic ffmpeg. Reason: {mp_err}")

                if used_multipass:
                    # Success path (multipass)
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

            # Default/backup: monolithic single-command path
                # Generate FFmpeg filter complex (original one-shot flow)
                filter_complex, audio_filter_complex, input_files = engine.generate_ffmpeg_filter_complex(temp_dir)
                logger.info(f"Generated FFmpeg filter complex with {len(input_files)} inputs")

                # Build FFmpeg command using modular helper
                ffmpeg_cmd = _build_ffmpeg_cmd(
                    input_files=input_files,
                    filter_complex=filter_complex,
                    audio_filter_complex=audio_filter_complex,
                    export_config=export_config,
                    output_path=output_path,
                )

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

            # Success path (monolithic)
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
