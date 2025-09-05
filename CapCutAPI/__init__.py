"""CapCutAPI unified import surface.

Usage:

    import CapCutAPI as cc
    script, draft_id = cc.create_draft(width=1080, height=1920)
    cc.add_text(text="Hello", start=0, end=3, draft_id=draft_id)
    script_copy, new_draft_id = cc.copy_draft(draft_id)  # Make a copy
    cc.save_draft(new_draft_id, draft_folder="/path/to/CapCut/drafts")
"""

from settings.local import IS_CAPCUT_ENV  # re-export environment flag
from settings.local import DRAFT_CACHE_DIR
# Core draft lifecycle
from create_draft import create_draft, get_or_create_draft
from clone_draft import clone_draft
from copy_draft import copy_draft
from save_draft_impl import (
    save_draft_impl as save_draft,
    query_task_status,
    query_script_impl,
    summarize_draft,
    parse_draft,
    download_script,
)

# Editing operations
from add_video_track import add_video_track as add_video
from add_audio_track import add_audio_track as add_audio
from add_image_impl import add_image_impl as add_image
from add_text_impl import add_text_impl as add_text
from add_subtitle_impl import add_subtitle_impl as add_subtitle
from add_effect_impl import add_effect_impl as add_effect
from add_sticker_impl import add_sticker_impl as add_sticker
from add_video_keyframe_impl import add_video_keyframe_impl as add_video_keyframe

# Utilities
from util import generate_draft_url
from util import move_into_capcut
from list_drafts import list_drafts

# Video export
from export_to_video_impl import export_to_video_impl, VideoExportConfig

import os
# CapCut project directory
CAPCUT_PROJECT_DIR = os.path.expanduser("~/Movies/CapCut/User Data/Projects/com.lveditor.draft")
DEFAULT_VIDEO_EXPORT_DIR = os.path.expanduser("/Users/tginart/Documents/LocalDev/ai-capcut/CapCutAPI/default_video_export")

__all__ = [
    # env
    "IS_CAPCUT_ENV",
    "DRAFT_CACHE_DIR",
    "CAPCUT_PROJECT_DIR",
    "DEFAULT_VIDEO_EXPORT_DIR",
    # lifecycle
    "create_draft",
    "get_or_create_draft",
    "clone_draft",
    "copy_draft",
    "save_draft",
    "query_task_status",
    "query_script_impl",
    "summarize_draft",
    "parse_draft",
    "download_script",
    # ops
    "add_video",
    "add_audio",
    "add_image",
    "add_text",
    "add_subtitle",
    "add_effect",
    "add_sticker",
    "add_video_keyframe",
    # utils
    "generate_draft_url",
    "list_drafts",
    "move_into_capcut",
    "parse_yaml_config",
    # video export
    "export_to_video",
    "VideoExportConfig",
] 

__version__ = "1.0.0"


# --- YAML script parser ---
def parse_yaml_config(filepath: str):
    """Parse a YAML/JSON config and execute editing steps.

    The config supports keys: `draft`, `assets`, `defaults`, `steps`.

    Steps can be in one of two formats:
      - Single-key mapping: `- add_video: { video_url: ..., start: 0, end: 3 }`
      - Explicit op field:  `- op: add_video\n    video_url: ...\n    start: 0\n    end: 3`

    Saving is not performed here; control logic should handle it.

    Returns the last step's result (dict) or a dict containing at least
    `draft_id` and `draft_url` if no steps are provided.
    """
    import os
    import json

    # Lazy import YAML/JSON5 parsers if available
    yaml = None
    json5 = None
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".yml", ".yaml"):
        try:
            import yaml as _yaml  # type: ignore
            yaml = _yaml
        except Exception as e:
            raise RuntimeError(
                "PyYAML is required to parse YAML files. Install with `pip install pyyaml` "
                "or provide a JSON/JSON5 config."
            )
    if ext == ".json5":
        try:
            import json5 as _json5  # type: ignore
            json5 = _json5
        except Exception:
            json5 = None

    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    if yaml is not None:
        cfg = yaml.safe_load(text)
    elif json5 is not None:
        cfg = json5.loads(text)
    else:
        # Fallback to strict JSON
        cfg = json.loads(text)

    # Ensure cfg is always a dictionary
    if not isinstance(cfg, dict):
        if cfg is None:
            cfg = {}
        else:
            # If YAML contains just a string or other non-dict value, wrap it
            cfg = {"content": cfg}
            # Log a warning for debugging purposes
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"YAML/JSON content parsed to non-dict type {type(cfg).__name__}: {cfg!r}. Wrapped as {{'content': value}}.")

    draft_cfg = cfg.get("draft") or {}
    assets = cfg.get("assets") or {}
    defaults = cfg.get("defaults") or {}
    steps = cfg.get("steps") or []

    if not isinstance(steps, list):
        raise ValueError("`steps` must be a list")

    # Helper: resolve $assets.* references recursively
    def resolve_value(value):
        if isinstance(value, str) and value.startswith("$assets."):
            key = value.split(".", 1)[1]
            if key not in assets or assets.get(key) is None:
                raise KeyError(f"Unknown asset reference '$assets.{key}'. Define it under 'assets' at the top level.")
            return assets[key]
        if isinstance(value, list):
            return [resolve_value(v) for v in value]
        if isinstance(value, dict):
            return {k: resolve_value(v) for k, v in value.items()}
        return value

    # Map op names to callables re-exported above
    op_map = {
        "create_draft": create_draft,
        "add_video": add_video,
        "add_audio": add_audio,
        "add_image": add_image,
        "add_text": add_text,
        "add_subtitle": add_subtitle,
        "add_effect": add_effect,
        "add_sticker": add_sticker,
        "add_video_keyframe": add_video_keyframe,
        "save_draft": save_draft,
    }

    # Current draft id (carried across steps)
    draft_id = draft_cfg.get("draft_id")

    last_result = None

    # Utility to merge defaults with step args (step wins)
    def build_args(step_args):
        args = {}
        args.update(defaults)
        args.update(step_args)
        # Resolve variables
        args = resolve_value(args)
        # Drop None values (avoid overriding callee defaults)
        return {k: v for k, v in args.items() if v is not None}

    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ValueError(f"Each step must be a mapping, got: {type(step).__name__} at index {idx}")

        # Determine op and raw args
        if "op" in step:
            op_name = step.get("op")
            step_args = {k: v for k, v in step.items() if k != "op"}
        else:
            if len(step) != 1:
                raise ValueError(
                    f"Single-key step mapping expected (e.g., - add_video: {{...}}). Got keys: {list(step.keys())}"
                )
            op_name, step_args = next(iter(step.items()))

        if op_name not in op_map:
            raise ValueError(f"Unsupported op: {op_name}")

        # Handle draft creation and propagation
        if op_name == "create_draft":
            # Allow per-step width/height override; fallback to top-level draft config
            width = step_args.get("width", draft_cfg.get("width", 1080))
            height = step_args.get("height", draft_cfg.get("height", 1920))
            draft_id_tuple = create_draft(width=width, height=height)
            # create_draft returns (draft_id, script)
            draft_id = draft_id_tuple[0]
            last_result = {"draft_id": draft_id, "draft_url": generate_draft_url(draft_id)}
            continue

        # For other ops, ensure we have a draft_id
        if draft_id is None:
            width = draft_cfg.get("width", 1080)
            height = draft_cfg.get("height", 1920)
            draft_id_tuple = create_draft(width=width, height=height)
            draft_id = draft_id_tuple[0]

        # Call the operation with contextual error reporting
        try:
            # Build args and inject draft_id if not provided
            call_args = build_args(step_args or {})
            call_args.setdefault("draft_id", draft_id)

            # Convert YAML text_styles dicts → TextStyleRange objects for add_text
            if op_name == "add_text" and isinstance(call_args.get("text_styles"), list) and call_args["text_styles"]:
                try:
                    from pyJianYingDraft.text_segment import TextStyleRange, Text_style, Text_border
                    from util import hex_to_rgb

                    converted_ranges = []
                    for style_data in call_args["text_styles"]:
                        # Skip if already a TextStyleRange (programmatic callers)
                        if hasattr(style_data, "__class__") and style_data.__class__.__name__ == "TextStyleRange":
                            converted_ranges.append(style_data)
                            continue

                        if not isinstance(style_data, dict):
                            raise ValueError(f"text_styles entries must be dicts or TextStyleRange; got {type(style_data).__name__}")

                        start_pos = int(style_data.get("start", 0))
                        end_pos = int(style_data.get("end", 0))

                        # Support nested style dict or flat keys
                        style_dict = style_data.get("style", style_data)

                        size = style_dict.get("size", call_args.get("font_size"))
                        bold = bool(style_dict.get("bold", False))
                        italic = bool(style_dict.get("italic", False))
                        underline = bool(style_dict.get("underline", False))
                        color_hex = style_dict.get("color", call_args.get("font_color", "#FFFFFF"))
                        alpha = style_dict.get("alpha", call_args.get("font_alpha", 1.0))
                        align = style_dict.get("align", 1)
                        vertical = style_dict.get("vertical", call_args.get("vertical", False))
                        letter_spacing = style_dict.get("letter_spacing", 0)
                        line_spacing = style_dict.get("line_spacing", 0)

                        rgb_color = hex_to_rgb(color_hex)

                        style_obj = Text_style(
                            size=size,
                            bold=bold,
                            italic=italic,
                            underline=underline,
                            color=rgb_color,
                            alpha=alpha,
                            align=align,
                            vertical=vertical,
                            letter_spacing=letter_spacing,
                            line_spacing=line_spacing,
                        )

                        # Border: support nested border dict or flat border_* keys
                        border_dict = style_data.get("border", {}) or {}
                        if not border_dict and any(k in style_data for k in ("border_width", "border_color", "border_alpha")):
                            border_dict = {
                                "width": style_data.get("border_width", 0.0),
                                "color": style_data.get("border_color", call_args.get("border_color", "#000000")),
                                "alpha": style_data.get("border_alpha", call_args.get("border_alpha", 1.0)),
                            }

                        border_obj = None
                        try:
                            width_val = float(border_dict.get("width", 0.0))
                        except Exception:
                            width_val = 0.0
                        if width_val > 0:
                            border_obj = Text_border(
                                alpha=border_dict.get("alpha", call_args.get("border_alpha", 1.0)),
                                color=hex_to_rgb(border_dict.get("color", call_args.get("border_color", "#000000"))),
                                width=border_dict.get("width", call_args.get("border_width", 0.0)),
                            )

                        font_str = style_data.get("font", call_args.get("font"))

                        style_range = TextStyleRange(
                            start=start_pos,
                            end=end_pos,
                            style=style_obj,
                            border=border_obj,
                            font_str=font_str,
                        )
                        converted_ranges.append(style_range)

                    call_args["text_styles"] = converted_ranges
                except Exception as conv_e:
                    raise conv_e.__class__(f"Failed to convert YAML text_styles to TextStyleRange: {conv_e}") from conv_e

            result = op_map[op_name](**call_args)
        except Exception as e:
            # Enrich error with step index, operation name, and step config for easier debugging
            step_descriptor = f"step {idx + 1} ({op_name})"
            step_obj = step
            try:
                if yaml is not None:
                    subyaml = yaml.safe_dump(step_obj, sort_keys=False, allow_unicode=True).strip()
                else:
                    subyaml = json.dumps(step_obj, indent=2, ensure_ascii=False)
            except Exception:
                subyaml = str(step_obj)
            raise e.__class__(f"{step_descriptor} failed: {e}\nStep config:\n{subyaml}") from e

        # Harmonize and carry draft_id forward
        if isinstance(result, tuple):
            draft_id = result[0]
            last_result = {"draft_id": draft_id, "draft_url": generate_draft_url(draft_id)}
        elif isinstance(result, dict):
            if "draft_id" in result:
                draft_id = result["draft_id"] or draft_id
            last_result = result
        else:
            last_result = {"draft_id": draft_id, "draft_url": generate_draft_url(draft_id)}

    # If no steps, return the current draft info (create if top-level provided draft only)
    if last_result is None:
        if draft_id is None:
            width = draft_cfg.get("width", 1080)
            height = draft_cfg.get("height", 1920)
            draft_id_tuple = create_draft(width=width, height=height)
            draft_id = draft_id_tuple[0]
        last_result = {"draft_id": draft_id, "draft_url": generate_draft_url(draft_id)}

    return last_result


# --- Video Export Function ---
def export_to_video(
    output_path: str = None,
    yaml_config: str = None,
    draft_id: str = None,
    width: int = None,
    height: int = None,
    fps: int = None,
    video_bitrate: str = None,
    audio_bitrate: str = None,
    audio_channels: int = None,
    audio_sample_rate: int = None,
    audio_codec: str = None,
    codec: str = None,
    preset: str = None,
    crf: str = None
) -> dict:
    """Export a CapCut draft to video using FFmpeg.

    Args:
        output_path (str): Path where the output video will be saved.
                          If None, saves to DEFAULT_VIDEO_EXPORT_DIR with auto-generated name.
        yaml_config (str): Path to YAML config file, raw YAML content, or None.
        draft_id (str): ID of existing draft in cache, or None.
        width (int): Output video width. If None, uses draft canvas width.
        height (int): Output video height. If None, uses draft canvas height.
        fps (int): Output video FPS. If None, uses draft FPS.
        video_bitrate (str): Video bitrate (e.g., "8000k"). Default "8000k".
        audio_bitrate (str): Audio bitrate (e.g., "128k"). Default "128k".

    Returns:
        dict: Export result with success status and metadata.

    Note:
        Either yaml_config or draft_id must be provided (not both).

    Example:
        ```python
        import CapCutAPI as cc

        # Export from YAML config
        result = cc.export_to_video(
            output_path="output.mp4",
            yaml_config="project.yml"
        )

        # Export from existing draft
        result = cc.export_to_video(
            output_path="output.mp4",
            draft_id="dfd_cat_123456789_abc123"
        )
        ```
    """
    import os
    import uuid
    from datetime import datetime

    # Validate inputs
    if yaml_config and draft_id:
        raise ValueError("Cannot specify both yaml_config and draft_id")
    if not yaml_config and not draft_id:
        raise ValueError("Must specify either yaml_config or draft_id")

    # Generate output path if not provided
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(DEFAULT_VIDEO_EXPORT_DIR, f"export_{timestamp}_{uuid.uuid4().hex[:8]}.mp4")

    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    os.makedirs(output_dir, exist_ok=True)

    # Create export config
    # Guard against passing None for fps which would propagate to FFmpeg as an invalid value
    export_config = VideoExportConfig(
        output_path=output_path,
        width=width,
        height=height,
        fps=(fps if fps is not None else 30),
        video_bitrate=video_bitrate or "8000k",
        audio_bitrate=audio_bitrate or "128k",
        audio_codec=audio_codec or "aac",
        audio_channels=(audio_channels if audio_channels is not None else 2),
        audio_sample_rate=(audio_sample_rate if audio_sample_rate is not None else 44100),
        codec=codec or "libx264",
        preset=preset or "medium",
        crf=crf or "23"
    )

    # Call implementation
    return export_to_video_impl(
        output_path=output_path,
        yaml_config=yaml_config,
        draft_id=draft_id,
        export_config=export_config
    )

