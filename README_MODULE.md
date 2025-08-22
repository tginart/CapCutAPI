# CapCutAPI Python Module – Full Usage Guide

## Overview

- **Programmatically build** CapCut/JianYing drafts by creating the project structure and writing `draft_info.json` via `pyJianYingDraft`
- **Use from plain Python scripts**; no HTTP/MCP server required for local workflows
- **Drafts live in memory** until saved; saving writes a folder under the repo directory named by `draft_id`
- **Copy that folder** into your CapCut/JianYing drafts directory to open in the app

## Installation (Local, Editable)

```bash
# Activate your conda environment
conda activate capcutapi

# From the repo root
pip install -e .
```

## Unified Import Surface

All public tools are re-exported under the `CapCutAPI` package:

```python
import CapCutAPI as cc
```

## Quick Start

### 1. Create a draft and add edits, then save and copy into CapCut's drafts path:

```python
import os
import shutil
import CapCutAPI as cc

# Create draft
script, draft_id = cc.create_draft(width=1080, height=1920)

# Add text
cc.add_text(
    text="Hello", 
    start=0, 
    end=3, 
    draft_id=draft_id,
    font_size=8.0, 
    font_color="#FFFFFF", 
    width=1080, 
    height=1920
)

# Set CapCut drafts directory
capcut_drafts = os.path.expanduser("~/Movies/CapCut/User Data/Projects/com.lveditor.draft")
# For JianYing (CN): ~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft

# Save draft
cc.save_draft(draft_id, draft_folder=capcut_drafts)

# Copy to CapCut drafts directory
repo_dir = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(repo_dir, draft_id)
dst = os.path.join(capcut_drafts, draft_id)

if os.path.exists(dst):
    shutil.rmtree(dst)
shutil.copytree(src, dst)

print("Draft available at:", dst)
```

## Notes on Saving and Paths

- **`save_draft`** writes the draft folder into the current repository directory, named by `draft_id` (e.g., `dfd_cat_1690000000_abc12345`)
- The **`draft_folder`** argument does not change the output location. It writes `replace_path` values inside `draft_info.json` so CapCut resolves assets under `<draft_folder>/<draft_id>/assets/`
- **To appear in CapCut**, copy the saved folder into the OS-specific drafts directory
- If **`is_upload_draft`** (`config.json`) is `true`, the draft is zipped and uploaded to OSS; the local temporary folder is then removed. Keep it `false` for local workflows

## Configuration (Optional)

`config.json` (JSON5 supported) is read by `settings.local`:

| Key | Type | Description |
|-----|------|-------------|
| `is_capcut_env` | `bool` | `True` for CapCut, `False` for JianYing (affects enums) |
| `draft_domain`, `preview_router` | `str` | Only relevant for hosted preview URLs |
| `is_upload_draft` | `bool` | If `True`, uploads zip to OSS; otherwise stays local |
| `oss_config`, `mp4_oss_config` | `dict` | Aliyun OSS credentials/domains |

## API Reference

### Core Draft Lifecycle

#### `create_draft(width=1080, height=1920) -> (script, draft_id)`

Create a new in-memory draft (`pyJianYingDraft.Script_file`). Returns the script object and a generated `draft_id` string.

**Arguments:**
- `width` (`int`): Canvas width in pixels. Default `1080`
- `height` (`int`): Canvas height in pixels. Default `1920`

**Key Notes:**
- Drafts are stored in an in-memory cache; persist them with `save_draft`.
- Returned tuple order is `(script, draft_id)`.

#### `get_or_create_draft(draft_id=None, width=1080, height=1920) -> (draft_id, script)`

Get an existing draft from cache by `draft_id` or create a new draft if not found.

**Arguments:**
- `draft_id` (`str|None`): Existing draft id; if `None` or missing, a new one is created
- `width`, `height` (`int`): Used only when creating a new draft

**Key Notes:**
- Returned tuple order is `(draft_id, script)` (note the order vs `create_draft`).
- Access refreshes the draft’s last-used time in cache.

#### `clone_draft(source_draft_name: str, *, source_root: str | None = None) -> (script, draft_id)`

Clone an existing CapCut/JianYing draft folder from the real projects directory into this repo, load it, and cache it.

**Arguments:**
- `source_draft_name` (`str`): Folder name of the draft inside the CapCut/JianYing projects directory
- `source_root` (`str|None`): Absolute path to the drafts root; if `None`, a sensible OS-specific default is used

**Returns:** `(script, draft_id)`

**Key Notes:**
- Copies `<source_root>/<source_draft_name>` to `./<draft_id>` inside this repo
- Loads the copied `draft_info.json` in template mode and updates the in-memory cache

#### `save_draft(draft_id: str, draft_folder: str | None = None) -> dict`

Materializes the in-memory draft into a folder under the repo directory named `draft_id`, downloads assets, and writes `draft_info.json`.

**Arguments:**
- `draft_id` (`str`): Target draft id to save
- `draft_folder` (`str|None`): CapCut/JianYing drafts directory. Used to set asset `replace_path` to `<draft_folder>/<draft_id>/assets/...` so CapCut opens the project correctly

**Returns:** `{"success": bool, "draft_url": str}`

**Key Notes:**
- Overwrites any existing local folder named `draft_id` in the repo directory.
- Downloads each referenced media file into `./<draft_id>/assets/{video|audio|image}/...` with up to 16 concurrent downloads.
- If metadata (duration, width/height) was unknown when adding segments, it’s probed via `ffprobe` and backfilled here; ensure FFmpeg is installed and on `PATH`.
- Overlapping segments within the same track are automatically resolved by deleting the later-added segment.
- When `is_upload_draft=true`, the local draft folder is zipped, uploaded via OSS, and then deleted locally.
- Processes any pending keyframes queued by `add_video_keyframe` during this save.

#### `summarize_draft(draft_id: str, *, include_materials: bool = True, max_text_len: int = 120, force_update: bool = False) -> str`

Return a human-readable summary of the current draft: canvas, duration, tracks, segments, and an optional materials appendix.

**Key Notes:**
- If `force_update=True`, refreshes media metadata before summarizing
- Truncates long text segment contents to `max_text_len`

#### `query_task_status(task_id: str) -> dict`

Return last known status of a save task. Current implementation uses `draft_id` as `task_id`.

**Key Notes:**
- For synchronous local saves, status is updated during the run; the final state is `completed` or `failed`.

#### `query_script_impl(draft_id: str, force_update: bool = True)`

Fetch the in-memory script (optionally refreshes media metadata). Returns a `pyJianYingDraft.Script_file`.

**Key Notes:**
- If `force_update=True`, this will run `ffprobe` on media; ensure FFmpeg is installed.

#### `download_script(draft_id: str, draft_folder: str, script_data: dict | None = None) -> dict`

Create a draft folder from a script JSON (either fetched from a remote endpoint or provided via `script_data`), downloading referenced assets and writing `draft_info.json`.

**Key Notes:**
- The target folder `<draft_folder>/<draft_id>` is (re)created; existing contents are removed.
- When `script_data` is `None`, a remote endpoint is queried; failures are surfaced with an error response.
- Media downloads continue even if individual files fail; errors are logged and the process proceeds with remaining items.

### Content Addition Functions

#### `add_video(...) -> dict`

Add a video segment.

**Key Parameters:**
- `video_url` (`str` - URL or local file path), `draft_id` (`str|None`), `start` (`float`), `end` (`float|None`), `target_start` (`float`)
- `width`, `height` (`int`), `transform_x`, `transform_y` (`float`), `scale_x`, `scale_y` (`float`), `speed` (`float`)
- `track_name` (`str`), `relative_index` (`int`), `volume` (`float`)
- `transition` (`str|None`), `transition_duration` (`float`)
- `mask_type` (`str|None`) and mask params, `background_blur` (`int|None`)

**Key Notes:**
- If neither `end` nor `duration` is provided, the initial source duration is set to `0.0`. The true duration is probed on save. If `start > 0` with no `end/duration`, initial duration can be non-positive; the save step adjusts it, but segments with invalid ranges may be skipped. Prefer providing `end` or `duration`.
- `video_url` accepts both remote URLs (e.g., `https://example.com/video.mp4`) and local file paths (e.g., `/path/to/video.mp4` or `file:///path/to/video.mp4`). Only `.mp4` files are supported for local paths.
- For remote URLs, media is downloaded during `save_draft()` and stored under `./<draft_id>/assets/video/...`. For local files, the file is copied during `save_draft()`.
- `draft_folder` only affects `replace_path` written into the draft; media still gets copied/downloaded under `./<draft_id>/assets/...` when saving.
- `transition` must match the enum for your environment (`CapCut_Transition_type` or `Transition_type`); invalid names raise an error.
- `mask_type` must match the environment's enum; invalid names raise an error. Rectangle-specific params apply only to rectangle masks.
- `background_blur` must be one of `{1,2,3,4}`; anything else raises an error.
- `relative_index` controls layer order among tracks of the same type; higher means closer to the foreground.
- Windows vs POSIX `draft_folder` paths are handled automatically; prefer absolute paths.

#### `add_audio(...) -> dict`

Add an audio segment at `target_start`.

**Key Parameters:**
- `audio_url` (`str` - URL or local file path), `draft_id` (`str|None`), `start`/`end` (`float`), `target_start` (`float`)
- `volume` (`float` 0.0–1.0), `speed` (`float`), `track_name` (`str`), `duration` (`float|None`)
- `sound_effects` (`list[(effect_name, params)]|None`)

**Key Notes:**
- If neither `end` nor `duration` is provided, initial duration is `0.0` and the real duration is probed on save; prefer specifying one to avoid non-positive ranges when `start>0`.
- `audio_url` accepts both remote URLs (e.g., `https://example.com/audio.mp3`) and local file paths (e.g., `/path/to/audio.mp3` or `file:///path/to/audio.mp3`). Supported audio formats: .mp3, .wav, .m4a, .aac, .ogg, .flac.
- For remote URLs, media is downloaded during `save_draft()` and stored under `./<draft_id>/assets/audio/...`. For local files, the file is copied during `save_draft()`.
- `sound_effects` are matched by name against enums:
  - CapCut: `CapCut_Voice_filters_effect_type`, `CapCut_Voice_characters_effect_type`, `CapCut_Speech_to_song_effect_type`
  - JianYing: `Audio_scene_effect_type`, then `Tone_effect_type`, then `Speech_to_song_type`
  Unknown names are skipped with a warning.
- `draft_folder` affects only `replace_path`; use absolute, OS-correct paths.
- `speed` scales the target duration (`duration / speed`).

#### `add_image(...) -> dict`

Add an image as a video segment of type photo. Supports intro/outro/combo animations, transitions, masks, background blur.

**Key Parameters:**
- `image_url` (`str` - URL or local file path), `draft_id` (`str|None`), `start`/`end` (`float`)
- `width`, `height` (`int`), transforms/scales (`float`), `track_name` (`str`), `relative_index` (`int`)
- `intro_animation`, `outro_animation`, `combo_animation` (`str|None`) and their durations
- `transition` (`str|None`), `transition_duration` (`float|None`)
- `mask_type` (`str|None`) and mask params, `background_blur` (`int|None`)

**Key Notes:**
- Ensure `end > start`; the function uses `end - start` for duration (no probe here).
- `image_url` accepts both remote URLs (e.g., `https://example.com/image.jpg`) and local file paths (e.g., `/path/to/image.jpg` or `file:///path/to/image.jpg`). Supported image formats: .png, .jpg, .jpeg, .gif, .bmp, .tiff, .webp.
- For remote URLs, media is downloaded during `save_draft()` and stored under `./<draft_id>/assets/image/...`. For local files, the file is copied during `save_draft()`.
- `intro_animation` takes precedence over legacy `animation`; invalid names raise an error.
- `transition` and `mask_type` must match the environment enums; invalid names raise an error.
- `background_blur` must be in `{1,2,3,4}`; invalid values raise an error.
- `relative_index` controls layer order.

#### `add_text(...) -> dict`

Add a text segment with comprehensive style/background/shadow/animation controls.

**Key Parameters:**
- Content & timing: `text` (`str`), `start`/`end` (`float`)
- Positioning: `transform_x`, `transform_y` (`float`)
- Typography: `font` (`str|None`, must exist in `Font_type`), `font_color` (hex), `font_size` (`float`)
- Track: `track_name` (`str`)
- Styling: `font_alpha`, `border_*`, `background_*`, `shadow_*`
- Effects: `bubble_effect_id`/`bubble_resource_id`, `effect_effect_id`
- Animations: `intro_animation`/`outro_animation` with durations
- Layout: `fixed_width`/`fixed_height` ratios (0..1)
- Multi-style: `text_styles` (`list[TextStyleRange]`)

**Key Notes:**
- `font` must match a member of `pyJianYingDraft.metadata.Font_type`; invalid names raise an error listing available fonts.
- `font_color`, `border_color` accept `#RGB` and `#RRGGBB` hex; invalid hex raises an error.
- Background is emitted only if `background_alpha > 0`; border only if `border_width > 0`; shadow only when `shadow_enabled=True`.
- Bubbles require both `bubble_effect_id` and `bubble_resource_id`.
- `fixed_width`/`fixed_height` > 0 are converted to pixels by multiplying project width/height; `-1` disables fixed sizing.
- `text_styles` ranges must satisfy `0 <= start < end <= len(text)`; invalid ranges raise an error. Ranges are applied as half-open intervals `[start, end)`.
- Animation names must match environment enums (`CapCut_Text_intro/CapCut_Text_outro` or `Text_intro/Text_outro`); invalid names are ignored with a warning.
- Keep `track_name` non-`None` to avoid creating unintended tracks.

#### `add_subtitle(...) -> dict`

Import SRT content from a URL, local file, or direct text. Applies provided text style/background/bubble/effect and positioning.

**Key Parameters:**
- `srt_path` (`str`): URL, local file path, or raw SRT content
- Style: font, size, bold/italic/underline, `font_color`
- Decorations: `border_*`, `background_*`, `bubble_effect_id`, `effect_effect_id`
- Transform: `transform_x/y`, `scale_x/y`, `rotation`
- Layout: `vertical` (`bool`), `alpha` (`float`)
- Timing: `time_offset` (`float` seconds)
- Track: `track_name` (`str`)

**Key Notes:**
- URLs are fetched via HTTP; local files are read with `utf-8-sig`; raw content has `\n` and `/n` normalized to newlines.
- Text alignment defaults to center; `vertical` and `alpha` are applied to the style.
- Border/background emitted only when `border_width > 0` or `background_alpha > 0` respectively.
- `time_offset` is converted to microseconds internally.

#### `add_effect(...) -> dict`

Adds a video effect on an effect track.

**Key Parameters:**
- `effect_type` (`str`): Must match a member of the effect enum for the selected category
- `effect_category` (`"scene"|"character"`)
- `start`/`end` (`float`), `track_name` (`str|None`), `params` (`list[float|None]|None`), `width`/`height` (`int`)

**Key Notes:**
- Effect enums depend on environment:
  - CapCut: `CapCut_Video_scene_effect_type` / `CapCut_Video_character_effect_type`
  - JianYing: `Video_scene_effect_type` / `Video_character_effect_type`
- Unknown `effect_type` raises an error.
- `params` are reversed internally before application (`params[::-1]`); if ordering matters, account for this.
- If the effect track named `track_name` does not exist, it is created.

#### `add_sticker(...) -> dict`

Adds a sticker segment with transform/alpha/flip/rotation controls.

**Key Parameters:**
- `resource_id` (`str`), `start`/`end` (`float`)
- Transform: `transform_x/y`, `rotation`, `scale_x/y`
- Appearance: `alpha` (`0..1`), `flip_horizontal`, `flip_vertical`
- Track: `track_name` (`str`), `relative_index` (`int`)

**Key Notes:**
- If the sticker track named `track_name` does not exist, it is created.
- Keep `alpha` in `0..1`; extreme values may make stickers invisible or fully opaque.

#### `add_video_keyframe(...) -> dict`

Adds one or more keyframes on the first segment in the given video track.

**Key Parameters:**
- Single mode: `property_type`, `time`, `value`
- Batch mode: `property_types`, `times`, `values` (all lists, equal length)

**Key Notes:**
- Supported properties: `position_x`, `position_y`, `rotation`, `scale_x`, `scale_y`, `uniform_scale`, `alpha`, `saturation`, `contrast`, `brightness`, `volume`.
- Value formats:
  - `rotation`: `"45deg"` or numeric degrees
  - `alpha`, `volume`: percent (e.g., `"50%"`) or numeric 0..1
  - `saturation`/`contrast`/`brightness`: `"+0.5"`, `"-0.5"`, or numeric
  - Positions/scales: numeric (positions accepted range `[-10, 10]`; typical canvas range is `[-1, 1]`)
- Batch mode requires all three lists present and of equal length, otherwise an error is raised.
- Keyframes are added as "pending" and are applied during `save_draft` (processing step); ensure you call `save_draft` to bake them.
- Times should fall within the segment’s target time range for visible results.

### Utility Functions

#### `get_video_duration(video_url: str) -> dict`

Returns `{"success": bool, "output": float_seconds, "error": str|None}` using ffprobe with retries.

**Key Notes:**
- Remote URLs must be reachable; network errors will be reflected in the `error` field.
- Requires FFmpeg tools available on `PATH`.

#### `list_drafts(*, source_root: str | None = None) -> list[dict]`

List drafts from both the in-memory cache and the real CapCut/JianYing projects directory.

**Returns:** A list of dicts with keys:
- `draft_id`: The draft identifier (folder name or cache key)
- `type`: One of `"cached draft"` or `"project draft"`

**Key Notes:**
- If `source_root` is omitted, an OS-specific default is used based on environment
- Duplicates may appear if a draft exists in both places

#### `generate_draft_url(draft_id: str) -> str`

Builds a preview URL as `<draft_domain><preview_router>?draft_id=...&is_capcut=0|1` (used for hosted previews; not needed for local workflows).

**Key Notes:**
- Driven by `settings.local` values `DRAFT_DOMAIN` and `PREVIEW_ROUTER`; adjust `config.json` if hosting your own preview service.
- For local-only workflows, this URL is informational and not required.

## Environment Flags

| Flag | Type | Description |
|------|------|-------------|
| `IS_CAPCUT_ENV` | `bool` | `True` for CapCut's enums/behavior; `False` for JianYing. Read from `settings.local` via `config.json` |

## Typical CapCut/JianYing Drafts Directories

| Platform | CapCut | JianYing |
|----------|--------|----------|
| **macOS** | `~/Movies/CapCut/User Data/Projects/com.lveditor.draft` | `~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft` |
| **Windows** | `C:\Users\<user>\Documents\CapCut\User Data\Projects\com.lveditor.draft` | `C:\Users\<user>\Documents\JianyingPro\User Data\Projects\com.lveditor.draft` |

## Mapping from CapCutAPI.* to Internal Implementations

| CapCutAPI Function | Internal Module |
|-------------------|-----------------|
| `create_draft` | `create_draft.create_draft` |
| `get_or_create_draft` | `create_draft.get_or_create_draft` |
| `clone_draft` | `clone_draft.clone_draft` |
| `save_draft` | `save_draft_impl.save_draft_impl` |
| `add_video` | `add_video_track.add_video_track` |
| `add_audio` | `add_audio_track.add_audio_track` |
| `add_image` | `add_image_impl.add_image_impl` |
| `add_text` | `add_text_impl.add_text_impl` |
| `add_subtitle` | `add_subtitle_impl.add_subtitle_impl` |
| `add_effect` | `add_effect_impl.add_effect_impl` |
| `add_sticker` | `add_sticker_impl.add_sticker_impl` |
| `add_video_keyframe` | `add_video_keyframe_impl.add_video_keyframe_impl` |
| `summarize_draft` | `save_draft_impl.summarize_draft` |
| `query_task_status` / `query_script_impl` / `download_script` | `save_draft_impl` |
| `list_drafts` | `list_drafts.list_drafts` |
| `generate_draft_url` | `util.generate_draft_url` |

## Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| **Draft didn't appear in CapCut** | Ensure you copied the saved folder (`repo_dir/draft_id`) into the CapCut drafts directory |
| **No assets when opening in CapCut** | Ensure you passed `draft_folder` to saving/edit functions so `replace_path` points to `<draft_folder>/<draft_id>/assets/...` and the save step downloaded assets into `repo_dir/draft_id/assets/` |
| **ffprobe not found** | Install FFmpeg and ensure it's on PATH |

---

*For more advanced usage, see the individual implementation files and the MCP server documentation.*
