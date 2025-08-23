"""CapCutAPI unified import surface.

Usage:

    import CapCutAPI as cc
    script, draft_id = cc.create_draft(width=1080, height=1920)
    cc.add_text(text="Hello", start=0, end=3, draft_id=draft_id)
    cc.save_draft(draft_id, draft_folder="/path/to/CapCut/drafts")
"""

from settings.local import IS_CAPCUT_ENV  # re-export environment flag

# Core draft lifecycle
from create_draft import create_draft, get_or_create_draft
from clone_draft import clone_draft
from save_draft_impl import (
    save_draft_impl as save_draft,
    query_task_status,
    query_script_impl,
    summarize_draft,
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

__all__ = [
    # env
    "IS_CAPCUT_ENV",
    # lifecycle
    "create_draft",
    "get_or_create_draft",
    "clone_draft",
    "save_draft",
    "query_task_status",
    "query_script_impl",
    "summarize_draft",
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
]

__version__ = "1.0.0"


