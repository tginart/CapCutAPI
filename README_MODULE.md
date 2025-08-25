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

### 1. Create a draft and add edits, then save and move into CapCut's drafts path:

```python
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
capcut_drafts = "~/Movies/CapCut/User Data/Projects/com.lveditor.draft"
# For JianYing (CN): "~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft"

# Save draft (writes ./<draft_id> and sets replace_path to capcut_drafts)
cc.save_draft(draft_id, draft_folder=capcut_drafts)

# Move into CapCut drafts directory so the app detects it
dst = cc.move_into_capcut(draft_id, capcut_drafts, overwrite=True)
print("Draft available at:", dst)
```

## YAML Script Support

The module provides a declarative YAML interface for building drafts. Instead of calling Python functions directly, you can define your edits in a YAML file and process it programmatically.

### Usage

```python
import CapCutAPI as cc

# Process YAML script
result = cc.parse_yaml_config("project.yml")
draft_id = result["draft_id"]

# Optionally save the resulting draft
cc.save_draft(draft_id)
```

### Supported Formats

- **YAML** (`.yml`, `.yaml`): Requires `pip install pyyaml`
- **JSON** (`.json`): No extra dependencies
- **JSON5** (`.json5`): Requires `pip install json5`

### YAML Structure

```yaml
draft:
  width: 1080
  height: 1920

assets:
  bg: https://example.com/background.mp4
  logo: ./images/logo.png

defaults:
  track_name: main
  width: 1080
  height: 1920

steps:
  - add_video:
      video_url: $assets.bg
      start: 0
      end: 10

  - add_image:
      image_url: $assets.logo
      start: 0
      end: 5
      scale_x: 0.5
      scale_y: 0.5

  - add_text:
      text: "Hello World"
      start: 0
      end: 3
      font_size: 48
```

### Key Features

- **`draft`**: Optional project settings; can include `draft_id` to reuse existing drafts
- **`assets`**: Name-to-URL/path mappings; reference with `$assets.<name>`
- **`defaults`**: Default values applied to all steps (step values take precedence)
- **`steps`**: Ordered list of editing operations

### Supported Operations

All the core editing functions are available as YAML steps:
`create_draft`, `add_video`, `add_audio`, `add_image`, `add_text`, `add_subtitle`, `add_effect`, `add_sticker`, `add_video_keyframe`, `save_draft`

### Step Syntax

**Single-key mapping (preferred):**
```yaml
steps:
  - add_video:
      video_url: https://example.com/clip.mp4
      start: 0
      end: 10
```

**Explicit op field (also supported):**
```yaml
steps:
  - op: add_video
    video_url: https://example.com/clip.mp4
    start: 0
    end: 10
```

See `README_YAML.md` for complete syntax documentation and examples.

### Function: `parse_yaml_config`

- **Signature**: `parse_yaml_config(filepath: str) -> dict`
- **Description**: Parse a YAML/JSON config and execute editing steps.
- **Top-level keys**: `draft`, `assets`, `defaults`, `steps`
- **Step formats**:
  - Single-key mapping:
    ```yaml
    - add_video: { video_url: https://..., start: 0, end: 3 }
    ```
  - Explicit `op` field:
    ```yaml
    - op: add_video
      video_url: https://...
      start: 0
      end: 3
    ```
- **Saving**: Not performed here; call `save_draft` yourself when ready.
- **Return value**: The last step's result (`dict`). If no steps are provided, returns a `dict` containing at least `draft_id` and `draft_url`.

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

**Returns:**
- `script` (`pyJianYingDraft.Script_file`): The draft script object
- `draft_id` (`str`): Generated draft identifier string

**Key Notes:**
- Drafts are stored in an in-memory cache; persist them with `save_draft`.
- Returned tuple order is `(script, draft_id)`.

#### `get_or_create_draft(draft_id=None, width=1080, height=1920) -> (draft_id, script)`

Get an existing draft from cache by `draft_id` or create a new draft if not found.

**Arguments:**
- `draft_id` (`str|None`): Existing draft id; if `None` or missing, a new one is created
- `width` (`int`): Canvas width in pixels. Used only when creating a new draft. Default `1080`
- `height` (`int`): Canvas height in pixels. Used only when creating a new draft. Default `1920`

**Returns:**
- `draft_id` (`str`): The draft identifier (existing or newly created)
- `script` (`pyJianYingDraft.Script_file`): The draft script object

**Key Notes:**
- Returned tuple order is `(draft_id, script)` (note the order vs `create_draft`).
- Access refreshes the draft's last-used time in cache.

#### `clone_draft(source_draft_name: str, *, source_root: str | None = None) -> (script, draft_id)`

Clone an existing CapCut/JianYing draft folder from the real projects directory into this repo, load it, and cache it.

**Arguments:**
- `source_draft_name` (`str`): Folder name of the draft inside the CapCut/JianYing projects directory
- `source_root` (`str|None`): Absolute path to the drafts root; if `None`, a sensible OS-specific default is used

**Returns:**
- `script` (`pyJianYingDraft.Script_file`): The loaded draft script object
- `draft_id` (`str`): Generated draft identifier for the cloned draft

**Key Notes:**
- Copies `<source_root>/<source_draft_name>` to `./<draft_id>` inside this repo
- Loads the copied `draft_info.json` in template mode and updates the in-memory cache
- Raises `FileNotFoundError` if source draft or root directory doesn't exist

#### `copy_draft(source_draft_id: str, *, new_draft_id: str | None = None) -> (script, new_draft_id)`

Create a copy of an existing draft in the cache with a new draft identifier.

**Arguments:**
- `source_draft_id` (`str`): The draft id of the existing draft to copy
- `new_draft_id` (`str|None`): Optional custom draft id for the copy; if `None`, a unique id is auto-generated

**Returns:**
- `script` (`pyJianYingDraft.Script_file`): The copied draft script object
- `new_draft_id` (`str`): The draft identifier for the new copy

**Key Notes:**
- Copies the entire draft folder from `<DRAFT_CACHE_DIR>/<source_draft_id>` to `<DRAFT_CACHE_DIR>/<new_draft_id>`
- Loads the copied `draft_info.json` in template mode and updates the in-memory cache
- Raises `FileNotFoundError` if the source draft doesn't exist in the cache
- Raises `FileExistsError` if the destination draft_id already exists

#### `save_draft(draft_id: str, draft_folder: str | None = None) -> dict`

Materializes the in-memory draft into a folder under the repo directory named `draft_id`, downloads assets, and writes `draft_info.json`.

**Arguments:**
- `draft_id` (`str`): Target draft id to save
- `draft_folder` (`str|None`): CapCut/JianYing drafts directory. Used to set asset `replace_path` to `<draft_folder>/<draft_id>/assets/...` so CapCut opens the project correctly

**Returns:**
- `dict` with keys:
  - `"success"` (`bool`): Whether the save operation was successful
  - `"draft_url"` (`str`): URL to access the saved draft (if uploaded to OSS)

**Key Notes:**
- Overwrites any existing local folder named `draft_id` in the repo directory.
- Downloads each referenced media file into `./<draft_id>/assets/{video|audio|image}/...` with up to 16 concurrent downloads.
- If metadata (duration, width/height) was unknown when adding segments, it's probed via `ffprobe` and backfilled here; ensure FFmpeg is installed and on `PATH`.
- When `is_upload_draft=true`, the local draft folder is zipped, uploaded via OSS, and then deleted locally.
- Processes any pending keyframes queued by `add_video_keyframe` during this save.

#### `move_into_capcut(draft_id: str, drafts_root: str, overwrite: bool = True) -> str`

Copy the saved draft folder from the repo root (`./<draft_id>`) into the CapCut/JianYing drafts directory (`<drafts_root>/<draft_id>`), so the project appears in the app.

**Arguments:**
- `draft_id` (`str`): Previously saved draft id
- `drafts_root` (`str`): CapCut/JianYing drafts root path (can be `~`-prefixed)
- `overwrite` (`bool`): Remove existing destination folder first if present. Default `True`

**Returns:**
- `str`: Destination path as a string

**Key Notes:**
- Raises if the source `./<draft_id>` does not exist (call `save_draft` first)
- Does not modify/recache the draft; purely a filesystem publish step

#### `summarize_draft(draft_id: str, *, include_materials: bool = True, max_text_len: int = 120, force_update: bool = False) -> str`

Return a human-readable summary of the current draft: canvas, duration, tracks, segments, and an optional materials appendix.

**Arguments:**
- `draft_id` (`str`): Target draft id to summarize
- `include_materials` (`bool`): Whether to include materials appendix in summary. Default `True`
- `max_text_len` (`int`): Maximum length for text segment contents before truncation. Default `120`
- `force_update` (`bool`): Whether to refresh media metadata before summarizing. Default `False`

**Returns:**
- `str`: Human-readable summary of the draft

**Key Notes:**
- If `force_update=True`, refreshes media metadata before summarizing
- Truncates long text segment contents to `max_text_len`

#### `parse_draft(draft_id: str, *, force_update: bool = False, include_assets: bool = True, use_asset_refs: bool = True) -> str`

Export the current draft as a declarative YAML script that follows the structure described in `README_YAML.md` (`draft`, optional `assets`, and `steps`).

**Arguments:**
- `draft_id` (`str`): Target draft id in cache
- `force_update` (`bool`): Refresh media metadata before exporting. Default `False`
- `include_assets` (`bool`): Include a top-level `assets` map. Default `True`
- `use_asset_refs` (`bool`): Reference media via `$assets.<name>` in steps when possible; otherwise embed URLs/paths inline. Default `True`

**Returns:**
- `str`: YAML text of the script. If PyYAML is unavailable, returns a JSON string with a hint comment

**Key Notes:**
- Emits steps for videos/images (`add_video`/`add_image`), audio (`add_audio`), and text (`add_text`); unsupported segments are skipped
- Times are exported in seconds; width/height are included under the top-level `draft`
- Track order respects render order; `track_name` is preserved when available

**Example:**
```python
import CapCutAPI as cc

# Export the current draft to a YAML script file
yaml_text = cc.parse_draft(draft_id)
with open("project.yml", "w", encoding="utf-8") as f:
    f.write(yaml_text)
```

#### `query_task_status(task_id: str) -> dict`

Return last known status of a save task. Current implementation uses `draft_id` as `task_id`.

**Arguments:**
- `task_id` (`str`): Task identifier to query

**Returns:**
- `dict`: Task status information

**Key Notes:**
- For synchronous local saves, status is updated during the run; the final state is `completed` or `failed`.

#### `query_script_impl(draft_id: str, force_update: bool = True)`

Fetch the in-memory script (optionally refreshes media metadata). Returns a `pyJianYingDraft.Script_file`.

**Arguments:**
- `draft_id` (`str`): Target draft id
- `force_update` (`bool`): Whether to refresh media metadata. Default `True`

**Returns:**
- `pyJianYingDraft.Script_file`: The draft script object

**Key Notes:**
- If `force_update=True`, this will run `ffprobe` on media; ensure FFmpeg is installed.

#### `download_script(draft_id: str, draft_folder: str, script_data: dict | None = None) -> dict`

Create a draft folder from a script JSON (either fetched from a remote endpoint or provided via `script_data`), downloading referenced assets and writing `draft_info.json`.

**Arguments:**
- `draft_id` (`str`): Target draft id for the downloaded script
- `draft_folder` (`str`): Target folder path for the downloaded script
- `script_data` (`dict|None`): Script JSON data; if `None`, fetched from remote endpoint

**Returns:**
- `dict`: Operation result with success/error information

**Key Notes:**
- The target folder `<draft_folder>/<draft_id>` is (re)created; existing contents are removed.
- When `script_data` is `None`, a remote endpoint is queried; failures are surfaced with an error response.
- Media downloads continue even if individual files fail; errors are logged and the process proceeds with remaining items.

#### `list_drafts(*, source_root: str | None = None) -> list[dict]`

List drafts from both the in-memory cache and the real CapCut/JianYing projects directory.

**Arguments:**
- `source_root` (`str|None`): Optional absolute path to the CapCut/JianYing drafts root. If omitted, a sensible OS-specific default is used

**Returns:**
- `list[dict]`: A list of dicts with keys:
  - `"draft_id"` (`str`): The draft identifier (folder name or cache key)
  - `"type"` (`str`): One of `"cached draft"` or `"project draft"`

**Key Notes:**
- If `source_root` is omitted, an OS-specific default is used based on environment
- Duplicates may appear if a draft exists in both places

#### `generate_draft_url(draft_id: str) -> str`

Builds a preview URL as `<draft_domain><preview_router>?draft_id=...&is_capcut=0|1` (used for hosted previews; not needed for local workflows).

**Arguments:**
- `draft_id` (`str`): Draft identifier for URL generation

**Returns:**
- `str`: Generated preview URL

**Key Notes:**
- Driven by `settings.local` values `DRAFT_DOMAIN` and `PREVIEW_ROUTER`; adjust `config.json` if hosting your own preview service.
- For local-only workflows, this URL is informational and not required.

#### `get_video_duration(video_url: str) -> dict`

Returns video duration using ffprobe with retries.

**Arguments:**
- `video_url` (`str`): URL or local file path to video

**Returns:**
- `dict` with keys:
  - `"success"` (`bool`): Whether duration retrieval was successful
  - `"output"` (`float`): Duration in seconds (if successful)
  - `"error"` (`str|None`): Error message (if failed)

**Key Notes:**
- Remote URLs must be reachable; network errors will be reflected in the `error` field.
- Requires FFmpeg tools available on `PATH`.

### Content Addition Functions

#### `add_video(...) -> dict`

Add a video segment.

**Arguments:**
- `video_url` (`str`): URL or local file path to video file
- `draft_folder` (`str|None`): Draft folder path, optional parameter
- `width` (`int`): Video width, default `1080`
- `height` (`int`): Video height, default `1920`
- `start` (`float`): Source video start time (seconds), default `0`
- `end` (`float|None`): Source video end time (seconds), default `None` (use total video duration)
- `target_start` (`float`): Target video start time (seconds), default `0`
- `draft_id` (`str|None`): Draft ID, if `None` or corresponding zip file not found, create new draft
- `transform_y` (`float`): Y-axis transform, default `0`
- `scale_x` (`float`): X-axis scale, default `1`
- `scale_y` (`float`): Y-axis scale, default `1`
- `transform_x` (`float`): X-axis transform, default `0`
- `speed` (`float`): Video playback speed, default `1.0`
- `track_name` (`str`): Track name, default `"main"`
- `relative_index` (`int`): Track rendering order index, default `0`
- `duration` (`float|None`): Video duration (seconds), if provided, skip duration detection
- `transition` (`str|None`): Transition type, optional parameter
- `transition_duration` (`float|None`): Transition duration (seconds), default uses the default duration of transition type
- `mask_type` (`str|None`): Mask type (`linear`, `mirror`, `circle`, `rectangle`, `heart`, `star`), optional parameter
- `mask_center_x` (`float`): Mask center X coordinate (0-1), default `0.5`
- `mask_center_y` (`float`): Mask center Y coordinate (0-1), default `0.5`
- `mask_size` (`float`): Mask size (0-1), default `1.0`
- `mask_rotation` (`float`): Mask rotation angle (degrees), default `0.0`
- `mask_feather` (`float`): Mask feather level (0-1), default `0.0`
- `mask_invert` (`bool`): Whether to invert mask, default `False`
- `mask_rect_width` (`float|None`): Rectangle mask width (only for rectangle mask)
- `mask_round_corner` (`float|None`): Rectangle mask rounded corner (only for rectangle mask, 0-100)
- `volume` (`float`): Volume level, default `1.0`

**Returns:**
- `dict`: Updated draft information including `draft_id` and `draft_url`

**Key Notes:**
- If neither `end` nor `duration` is provided, the initial source duration is set to `0.0`. The true duration is probed on save. If `start > 0` with no `end/duration`, initial duration can be non-positive; the save step adjusts it, but segments with invalid ranges may be skipped. Prefer providing `end` or `duration`.
- `video_url` accepts both remote URLs (e.g., `https://example.com/video.mp4`) and local file paths (e.g., `/path/to/video.mp4` or `file:///path/to/video.mp4`). Only `.mp4` files are supported for local paths.
- For remote URLs, media is downloaded during `save_draft()` and stored under `./<draft_id>/assets/video/...`. For local files, the file is copied during `save_draft()`.
- `draft_folder` only affects `replace_path` written into the draft; media still gets copied/downloaded under `./<draft_id>/assets/...` when saving.
- `transition` must match the enum for your environment (`CapCut_Transition_type` or `Transition_type`); invalid names raise an error.
- `mask_type` must match the environment's enum; invalid names raise an error. Rectangle-specific params apply only to rectangle masks.
- `relative_index` controls layer order among tracks of the same type; higher means closer to the foreground.
- Windows vs POSIX `draft_folder` paths are handled automatically; prefer absolute paths.
- Overlapping segments are not supported. Use different `track_name` values for simultaneous or layered content.

#### `add_audio(...) -> dict`

Add an audio segment at `target_start`.

**Arguments:**
- `audio_url` (`str`): URL or local file path to audio file
- `draft_folder` (`str|None`): Draft folder path, optional parameter
- `start` (`float`): Start time (seconds), default `0`
- `end` (`float|None`): End time (seconds), default `None` (use total audio duration)
- `target_start` (`float`): Target track insertion position (seconds), default `0`
- `draft_id` (`str|None`): Draft ID, if `None` or corresponding zip file not found, create new draft
- `volume` (`float`): Volume level, range 0.0-1.0, default `1.0`
- `track_name` (`str`): Track name, default `"audio_main"`
- `speed` (`float`): Playback speed, default `1.0`
- `sound_effects` (`list[Tuple[str, Optional[List[Optional[float]]]]]|None`): Scene sound effect list, each element is a tuple containing effect type name and parameter list, default `None`
- `width` (`int`): Video width, default `1080`
- `height` (`int`): Video height, default `1920`
- `duration` (`float|None`): Audio duration (seconds), if provided, skip duration detection

**Returns:**
- `dict`: Updated draft information

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

**Arguments:**
- `image_url` (`str`): URL or local file path to image file
- `draft_folder` (`str|None`): Draft folder path, optional parameter
- `width` (`int`): Video width, default `1080`
- `height` (`int`): Video height, default `1920`
- `start` (`float`): Start time (seconds), default `0`
- `end` (`float`): End time (seconds), default `3.0` (3 seconds display time)
- `draft_id` (`str|None`): Draft ID, if `None` or corresponding zip file not found, create new draft
- `transform_y` (`float`): Y-axis transformation, default `0`
- `scale_x` (`float`): X-axis scaling, default `1`
- `scale_y` (`float`): Y-axis scaling, default `1`
- `transform_x` (`float`): X-axis transformation, default `0`
- `track_name` (`str`): Track name, default `"main"`
- `relative_index` (`int`): Track rendering order index, default `0`
- `animation` (`str|None`): Entrance animation name (backward compatibility), supported animations include: Zoom Out, Fade In, Zoom In, Rotate, Kira Float, Shake Down, Mirror Flip, Rotate Open, Fold Open, Vortex Rotate, Jump Open, etc.
- `animation_duration` (`float`): Entrance animation duration (seconds), default `0.5`
- `intro_animation` (`str|None`): New entrance animation parameter, higher priority than animation
- `intro_animation_duration` (`float`): New entrance animation duration (seconds), default `0.5`
- `outro_animation` (`str|None`): Exit animation parameter
- `outro_animation_duration` (`float`): Exit animation duration (seconds), default `0.5`
- `combo_animation` (`str|None`): Combo animation parameter
- `combo_animation_duration` (`float`): Combo animation duration (seconds), default `0.5`
- `transition` (`str|None`): Transition type, supported transitions include: Dissolve, Move Up, Move Down, Move Left, Move Right, Split, Compress, Anime Cloud, Anime Vortex, etc.
- `transition_duration` (`float|None`): Transition duration (seconds), default `0.5`
- `mask_type` (`str|None`): Mask type (`Linear`, `Mirror`, `Circle`, `Rectangle`, `Heart`, `Star`)
- `mask_center_x` (`float`): Mask center X coordinate (in material pixels), default set at material center
- `mask_center_y` (`float`): Mask center Y coordinate (in material pixels), default set at material center
- `mask_size` (`float`): Main size of the mask, represented as a proportion of material height, default `0.5`
- `mask_rotation` (`float`): Clockwise rotation angle of the mask, default no rotation
- `mask_feather` (`float`): Mask feather parameter, range 0~100, default no feathering
- `mask_invert` (`bool`): Whether to invert the mask, default not inverted
- `mask_rect_width` (`float|None`): Rectangle mask width, only allowed when mask type is rectangle, represented as a proportion of material width
- `mask_round_corner` (`float|None`): Rectangle mask rounded corner parameter, only allowed when mask type is rectangle, range 0~100
- `background_blur` (`int|None`): Background blur level, 1-4, corresponding to four blur intensity levels

**Returns:**
- `dict`: Updated draft information including `draft_id` and `draft_url`

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

**Arguments:**
- `text` (`str`): Text content
- `start` (`float`): Start time (seconds)
- `end` (`float`): End time (seconds)
- `draft_id` (`str|None`): Draft ID, if `None` or corresponding zip file not found, create new draft
- `transform_y` (`float`): Y-axis position, default `-0.8` (bottom of screen)
- `transform_x` (`float`): X-axis position, default `0` (center of screen)
- `font` (`str|None`): Font name (supports all fonts in `Font_type`)
- `font_color` (`str`): Font color in hex format, default `"#ffffff"`
- `font_size` (`float`): Font size, default `8.0`
- `track_name` (`str`): Track name, default `"text_main"`
- `vertical` (`bool`): Whether to display vertically, default `False`
- `font_alpha` (`float`): Text transparency, range 0.0-1.0, default `1.0`
- `border_alpha` (`float`): Border transparency, range 0.0-1.0, default `1.0`
- `border_color` (`str`): Border color in hex format, default `"#000000"`
- `border_width` (`float`): Border width, default `0.0` (no border)
- `background_color` (`str`): Background color in hex format, default `"#000000"`
- `background_style` (`int`): Background style, default `1`
- `background_alpha` (`float`): Background transparency, default `0.0` (no background)
- `background_round_radius` (`float`): Background corner radius, range 0.0-1.0, default `0.0`
- `background_height` (`float`): Background height, range 0.0-1.0, default `0.14`
- `background_width` (`float`): Background width, range 0.0-1.0, default `0.14`
- `background_horizontal_offset` (`float`): Background horizontal offset, default `0.5`
- `background_vertical_offset` (`float`): Background vertical offset, default `0.5`
- `shadow_enabled` (`bool`): Whether shadow is enabled, default `False`
- `shadow_alpha` (`float`): Shadow transparency, default `0.9`
- `shadow_angle` (`float`): Shadow angle, default `-45.0`
- `shadow_color` (`str`): Shadow color in hex format, default `"#000000"`
- `shadow_distance` (`float`): Shadow distance, default `5.0`
- `shadow_smoothing` (`float`): Shadow smoothing, default `0.15`
- `bubble_effect_id` (`str|None`): Bubble effect ID
- `bubble_resource_id` (`str|None`): Bubble resource ID
- `effect_effect_id` (`str|None`): Text effect ID
- `intro_animation` (`str|None`): Intro animation name
- `intro_duration` (`float`): Intro animation duration (seconds), default `0.5`
- `outro_animation` (`str|None`): Outro animation name
- `outro_duration` (`float`): Outro animation duration (seconds), default `0.5`
- `width` (`int`): Video width, default `1080`
- `height` (`int`): Video height, default `1920`
- `fixed_width` (`float`): Text fixed width ratio, default `-1` (not fixed)
- `fixed_height` (`float`): Text fixed height ratio, default `-1` (not fixed)
- `text_styles` (`list[TextStyleRange]|None`): List of text style ranges for different text portions

**Returns:**
- `dict`: Updated draft information including `draft_id` and `draft_url`

**Key Notes:**
- `font` must match a member of `pyJianYingDraft.metadata.Font_type`; invalid names raise an error listing available fonts.
- `font_color`, `border_color` accept `#RGB` and `#RRGGBB` hex; invalid hex raises an error.
- Background is emitted only if `background_alpha > 0`; border only if `border_width > 0`; shadow only when `shadow_enabled=True`.
- Bubbles require both `bubble_effect_id` and `bubble_resource_id`.
- `fixed_width`/`fixed_height` > 0 are converted to pixels by multiplying project width/height; `-1` disables fixed sizing.
- `text_styles` ranges must satisfy `0 <= start < end <= len(text)`; invalid ranges raise an error. Ranges are applied as half-open intervals `[start, end)`.
- Animation names must match environment enums (`CapCut_Text_intro/CapCut_Text_outro` or `Text_intro/Text_outro`); invalid names are ignored with a warning.
- Keep `track_name` non-`None` to avoid creating unintended tracks.
- Overlapping segments are not supported. Use different `track_name` values for simultaneous or layered content.
- There is no `relative_index` arg for text.

**Available Fonts:**

```['Amigate', 'Anson', 'BlackMango_Black', 'BlackMango_Regular', 'Bungee_Regular', 'CC_Captial', 'CC_Moderno', 'Cabin_Rg', 'Caveat_Regular', 'Climate', 'Coiny_Regular', 'DMSans_BoldItalic', 'Exo', 'Gallery', 'Giveny', 'Grandstander_Regular', 'Gratefulness', 'HarmonyOS_Sans_SC_Bold', 'HarmonyOS_Sans_SC_Medium', 'HarmonyOS_Sans_SC_Regular', 'HarmonyOS_Sans_TC_Bold', 'HarmonyOS_Sans_TC_Light', 'HarmonyOS_Sans_TC_Medium', 'HarmonyOS_Sans_TC_Regular', 'HeptaSlab_ExtraBold', 'HeptaSlab_Light', 'Huben', 'Ingram', 'Integrity', 'Inter_Black', 'JYruantang', 'JYshiduo', 'JYzhuqingting', 'Kanit_Black', 'Kanit_Regular', 'Koulen_Regular', 'LXGWWenKai_Bold', 'LXGWWenKai_Light', 'LXGWWenKai_Regular', 'Love', 'Luxury', 'Merry_Christmas', 'MiSans_Heavy', 'MiSans_Regular', 'Modern', 'MyFont凌渡哥哥简', 'Nunito', 'OldStandardTT_Regular', 'Pacifico_Regular', 'PlayfairDisplay_Bold', 'Plunct', 'Polly', 'Poppins_Bold', 'Poppins_Regular', 'RedHatDisplay_BoldItalic', 'RedHatDisplay_Light', 'ResourceHanRoundedCN_Md', 'ResourceHanRoundedCN_Nl', 'Roboto_BlkCn', 'SansitaSwashed_Regular', 'SecularOne_Regular', 'Signature', 'Soap', 'Sora_Bold', 'Sora_Regular', 'SourceHanSansCN_Bold', 'SourceHanSansCN_Light', 'SourceHanSansCN_Medium', 'SourceHanSansCN_Normal', 'SourceHanSansCN_Regular', 'SourceHanSansTW_Bold', 'SourceHanSansTW_Light', 'SourceHanSansTW_Medium', 'SourceHanSansTW_Normal', 'SourceHanSansTW_Regular', 'SourceHanSerifCN_Light', 'SourceHanSerifCN_Medium', 'SourceHanSerifCN_Regular', 'SourceHanSerifCN_SemiBold', 'SourceHanSerifTW_Bold', 'SourceHanSerifTW_Light', 'SourceHanSerifTW_Medium', 'SourceHanSerifTW_Regular', 'SourceHanSerifTW_SemiBold', 'Staatliches_Regular', 'Sunset', 'Thrive', 'Thunder', 'Tronica', 'Vintage', 'ZYLAA_Demure', 'ZYLantastic', 'ZYLullaby', 'ZYSilhouette', 'ZYWitty', 'ZY_Balloonbillow', 'ZY_Blossom', 'ZY_Brief', 'ZY_Courage', 'ZY_Daisy', 'ZY_Dexterous', 'ZY_Earnest', 'ZY_Elixir', 'ZY_Fabulous', 'ZY_Fantasy', 'ZY_Flourishing_Italic', 'ZY_Fortitude', 'ZY_Kindly_Breeze', 'ZY_Loyalty', 'ZY_Modern', 'ZY_Multiplicity', 'ZY_Panacea', 'ZY_Relax', 'ZY_Slender', 'ZY_Spunk', 'ZY_Squiggle', 'ZY_Starry', 'ZY_Timing', 'ZY_Trend', 'ZY_Vigorous', 'ZY_Vigorous_Medium', 'Zapfino']```


#### `add_subtitle(...) -> dict`

Import SRT content from a URL, local file, or direct text. Applies provided text style/background/bubble/effect and positioning.

**Arguments:**
- `srt_path` (`str`): URL, local file path, or raw SRT content
- `draft_id` (`str|None`): Draft ID, if `None` or corresponding zip file not found, create new draft
- `track_name` (`str`): Track name, default `"subtitle"`
- `time_offset` (`float`): Time offset in seconds, default `0`
- `font` (`str|None`): Font name
- `font_size` (`float`): Font size, default `8.0`
- `bold` (`bool`): Whether text is bold, default `False`
- `italic` (`bool`): Whether text is italic, default `False`
- `underline` (`bool`): Whether text is underlined, default `False`
- `font_color` (`str`): Font color in hex format, default `"#FFFFFF"`
- `border_alpha` (`float`): Border transparency, range 0.0-1.0, default `1.0`
- `border_color` (`str`): Border color in hex format, default `"#000000"`
- `border_width` (`float`): Border width, default `0.0` (no border)
- `background_color` (`str`): Background color in hex format, default `"#000000"`
- `background_style` (`int`): Background style, default `1`
- `background_alpha` (`float`): Background transparency, default `0.0` (no background)
- `bubble_effect_id` (`str|None`): Bubble effect ID
- `bubble_resource_id` (`str|None`): Bubble resource ID
- `effect_effect_id` (`str|None`): Text effect ID
- `transform_x` (`float`): X-axis position, default `0.0`
- `transform_y` (`float`): Y-axis position, default `-0.8` (bottom)
- `scale_x` (`float`): X-axis scaling, default `1.0`
- `scale_y` (`float`): Y-axis scaling, default `1.0`
- `rotation` (`float`): Rotation angle, default `0.0`
- `style_reference` (`draft.Text_segment|None`): Style reference segment
- `vertical` (`bool`): Whether to display vertically, default `True`
- `alpha` (`float`): Text transparency, default `0.4`
- `width` (`int`): Video width, default `1080`
- `height` (`int`): Video height, default `1920`

**Returns:**
- `dict`: Updated draft information including `draft_id` and `draft_url`

**Key Notes:**
- URLs are fetched via HTTP; local files are read with `utf-8-sig`; raw content has `\n` and `/n` normalized to newlines.
- Text alignment defaults to center; `vertical` and `alpha` are applied to the style.
- Border/background emitted only when `border_width > 0` or `background_alpha > 0` respectively.
- `time_offset` is converted to microseconds internally.

#### `add_effect(...) -> dict`

Adds a video effect on an effect track.

**Arguments:**
- `effect_type` (`str`): Effect type name (must match enum for selected category)
- `effect_category` (`Literal["scene", "character"]`): Effect category
- `start` (`float`): Start time (seconds), default `0`
- `end` (`float`): End time (seconds), default `3.0`
- `draft_id` (`str|None`): Draft ID, if `None` or corresponding zip file not found, create new draft
- `track_name` (`str|None`): Track name, default `"effect_01"`
- `params` (`list[Optional[float]]|None`): Effect parameter list
- `width` (`int`): Video width, default `1080`
- `height` (`int`): Video height, default `1920`

**Returns:**
- `dict`: Updated draft information including `draft_id` and `draft_url`

**Key Notes:**
- Effect enums depend on environment:
  - CapCut: `CapCut_Video_scene_effect_type` / `CapCut_Video_character_effect_type`
  - JianYing: `Video_scene_effect_type` / `Video_character_effect_type`
- Unknown `effect_type` raises an error.
- `params` are reversed internally before application (`params[::-1]`); if ordering matters, account for this.
- If the effect track named `track_name` does not exist, it is created.

#### `add_sticker(...) -> dict`

Adds a sticker segment with transform/alpha/flip/rotation controls.

**Arguments:**
- `resource_id` (`str`): Sticker resource ID
- `start` (`float`): Start time (seconds)
- `end` (`float`): End time (seconds)
- `draft_id` (`str|None`): Draft ID, if `None` or corresponding zip file not found, create new draft
- `transform_y` (`float`): Y-axis position, default `0` (center)
- `transform_x` (`float`): X-axis position, default `0` (center)
- `alpha` (`float`): Image opacity, range 0-1, default `1.0`
- `flip_horizontal` (`bool`): Whether to flip horizontally, default `False`
- `flip_vertical` (`bool`): Whether to flip vertically, default `False`
- `rotation` (`float`): Clockwise rotation angle, default `0.0`
- `scale_x` (`float`): Horizontal scale ratio, default `1.0`
- `scale_y` (`float`): Vertical scale ratio, default `1.0`
- `track_name` (`str`): Track name, default `"sticker_main"`
- `relative_index` (`int`): Relative layer position, higher means closer to foreground, default `0`
- `width` (`int`): Video width, default `1080`
- `height` (`int`): Video height, default `1920`

**Returns:**
- `dict`: Updated draft information including `draft_id` and `draft_url`

**Key Notes:**
- If the sticker track named `track_name` does not exist, it is created.
- Keep `alpha` in `0..1`; extreme values may make stickers invisible or fully opaque.

#### `add_video_keyframe(...) -> dict`

Adds one or more keyframes on the first segment in the given video track.

**Arguments:**
- `draft_id` (`str|None`): Draft ID, if `None` or corresponding zip file not found, create new draft
- `track_name` (`str`): Track name, default `"main"`
- `property_type` (`str`): Keyframe property type, default `"alpha"`
- `time` (`float`): Keyframe time point (seconds), default `0.0`
- `value` (`str`): Keyframe value, default `"1.0"`
- `property_types` (`list[str]|None`): Batch mode: List of keyframe property types
- `times` (`list[float]|None`): Batch mode: List of keyframe time points (seconds)
- `values` (`list[str]|None`): Batch mode: List of keyframe values

**Returns:**
- `dict`: Updated draft information including `draft_id` and `draft_url`

**Key Notes:**
- Supported properties: `position_x`, `position_y`, `rotation`, `scale_x`, `scale_y`, `uniform_scale`, `alpha`, `saturation`, `contrast`, `brightness`, `volume`.
- Value formats:
  - `rotation`: `"45deg"` or numeric degrees
  - `alpha`, `volume`: percent (e.g., `"50%"`) or numeric 0..1
  - `saturation`/`contrast`/`brightness`: `"+0.5"`, `"-0.5"`, or numeric
  - Positions/scales: numeric (positions accepted range `[-10, 10]`; typical canvas range is `[-1, 1]`)
- Batch mode requires all three lists present and of equal length, otherwise an error is raised.
- Keyframes are added as "pending" and are applied during `save_draft` (processing step); ensure you call `save_draft` to bake them.
- Times should fall within the segment's target time range for visible results.

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
| `copy_draft` | `copy_draft.copy_draft` |
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
| `move_into_capcut` | `util.move_into_capcut` |

## Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| **Draft didn't appear in CapCut** | Ensure you copied the saved folder (`repo_dir/draft_id`) into the CapCut drafts directory |
| **No assets when opening in CapCut** | Ensure you passed `draft_folder` to saving/edit functions so `replace_path` points to `<draft_folder>/<draft_id>/assets/...` and the save step downloaded assets into `repo_dir/draft_id/assets/` |
| **ffprobe not found** | Install FFmpeg and ensure it's on PATH |

---

*For more advanced usage, see the individual implementation files and the MCP server documentation.*
