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

import os
# CapCut project directory
# TODO: add support for custom CapCut project directory
# CAPCUT_PROJECT_DIR = os.path.expanduser("~/Movies/CapCut/User Data/Projects/com.lveditor.draft")

__all__ = [
    # env
    "IS_CAPCUT_ENV",
    "DRAFT_CACHE_DIR",
    # CAPCUT_PROJECT_DIR",
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

    cfg = cfg or {}

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
            return assets.get(key)
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

        # Build args and inject draft_id if not provided
        call_args = build_args(step_args or {})
        call_args.setdefault("draft_id", draft_id)

        # Call the operation
        result = op_map[op_name](**call_args)

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

