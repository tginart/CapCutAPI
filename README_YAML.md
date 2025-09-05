## YAML Script Guide for CapCutAPI

This document explains how to write a YAML script to declaratively construct a CapCut draft.

### Overview

- YAML scripts define assets, defaults, and steps to build a CapCut project
- The script is processed by CapCutAPI to create and modify drafts
- Each step corresponds to a specific editing operation

### Config Structure

- `draft`: optional project settings
- `assets`: optional name → URL/path mapping; referenced via `$assets.<name>`
- `steps`: ordered list of operations

#### Note
- `steps` must be a list. Each step must be one of the supported operations.

Supported operations:
`add_video`, `add_audio`, `add_image`, `add_text`, `add_subtitle`, `add_effect`, `add_sticker`, `add_video_keyframe`.

### Minimal Example

```yaml
draft:
  width: 1080
  height: 1920

assets:
  bg: https://example.com/background.mp4

steps:
  - add_video:
      video_url: $assets.bg
      start: 0
      end: 8

  - add_text:
      text: "Hello"
      start: 0
      end: 3
      font_size: 48
```

### Using Assets

Use `$assets.<name>` to reference entries defined in `assets`:

```yaml
assets:
  song: ./audio/track.m4a

steps:
  - add_audio:
      audio_url: $assets.song
      start: 0
      end: 10
      volume: 0.7
```

### Keyframes Example

```yaml
steps:
  - add_video:
      video_url: https://example.com/clip.mp4
      start: 0
      end: 6

  - add_video_keyframe:
      track_name: main
      property_types: [scale_x, scale_y, alpha]
      times: [0, 2, 4]
      values: ["1.0", "1.2", "0.8"]
```

### Canvas Coordinates & Transforms

- Position (`transform_x`, `transform_y`) use a normalized canvas space with the center at `(0, 0)`.
  - Negative `transform_x` moves left, positive moves right.
  - Negative `transform_y` moves up, positive moves down.
- Scale (`scale_x`, `scale_y`) of `1.0` keeps original size; values > `1.0` enlarge, < `1.0` shrink.
- Rotation values (where supported) are in degrees, clockwise positive.
- Typical useful range is approximately `[-1.0, 1.0]`, but values outside this range can position content off-canvas intentionally.

### Operations Reference

#### add_video
- Purpose: Add a video segment
- Required:
  - **video_url** (string): Remote URL or local file path; local supports .mp4 and .mov
- Optional:
  - **draft_folder** (string): Drafts root path used to write asset `replace_path` (does not change where media is copied during save)
  - **width** (int, default 1080): Project width in pixels
  - **height** (int, default 1920): Project height in pixels
  - **start** (float, default 0): Source clip start time (seconds)
  - **end** (float|null): Source clip end time; if omitted and `duration` not set, initial duration is 0 and probed on save
  - **target_start** (float, default 0): Where to place on the project timeline (seconds)
  - **draft_id** (string|null): Draft ID; if omitted a new draft is created (or the current one is used)
  - **transform_y** (float, default 0): Vertical position in normalized canvas coordinates
  - **scale_x** (float, default 1): Horizontal scale factor
  - **scale_y** (float, default 1): Vertical scale factor
  - **transform_x** (float, default 0): Horizontal position in normalized canvas coordinates
  - **speed** (float, default 1.0): Playback speed; target duration is `(end - start) / speed`
  - **track_name** (string, default "main"): Video track name
  - **relative_index** (int, default 0): Layer order among same-type tracks; higher renders above lower
  - **duration** (float|null): Explicit source duration (seconds); skips duration probing
  - **transition** (string|null): Transition name (must match environment enum)
  - **transition_duration** (float|null, default 0.5): Transition duration in seconds
  - Mask params:
    - **mask_type** (string|null): One of `linear`, `mirror`, `circle`, `rectangle`, `heart`, `star`
    - **mask_center_x** (float, default 0.5): Center X in 0–1 relative to material
    - **mask_center_y** (float, default 0.5): Center Y in 0–1 relative to material
    - **mask_size** (float, default 1.0): Primary size in 0–1 relative to material height
    - **mask_rotation** (float, default 0.0): Rotation in degrees
    - **mask_feather** (float, default 0.0): Feather in 0–100 scale
    - **mask_invert** (bool, default false): Invert the mask region
    - **mask_rect_width** (float|null): Rectangle width in 0–1 of material width (rectangle mask only)
    - **mask_round_corner** (float|null, 0–100): Rounded corners for rectangle mask
  - **volume** (float, default 1.0): Audio volume multiplier (0.0 mute, 1.0 original)
  - **background_blur** (int|null): 1–4 maps to light→max blur on background filling
- Key notes:
  - If neither `end` nor `duration` is provided, the true duration is backfilled during save
  - `video_url` accepts both remote URLs (e.g., `https://...`) and local file paths (e.g., `/path/to/video.mp4` or `file:///path/to/video.mov`); local supports `.mp4` and `.mov` only
  - **CRITICAL**: You CANNOT have *temporally* overlapping segments on the same track name! Use different `track_name` values for simultaneous or layered content (e.g., "main", "main2", "overlay"). Of course, you can re-use the same track name for content that does NOT overlap in time.
- Example:
```yaml
- add_video:
    video_url: $assets.bg
    start: 0
    end: 10
    transition: Dissolve
    transition_duration: 0.5
```

#### add_audio
- Purpose: Add an audio segment
- Required:
  - **audio_url** (string): Remote URL or local file path; supported local formats: .mp3, .wav, .m4a, .aac, .ogg, .flac
- Optional:
  - **draft_folder** (string): Drafts root path used to write asset `replace_path`
  - **start** (float, default 0): Source clip start time (seconds)
  - **end** (float|null): Source clip end time; if omitted and `duration` not set, initial duration is 0 and probed on save
  - **target_start** (float, default 0): Where to place on the project timeline (seconds)
  - **draft_id** (string|null): Draft ID; if omitted a new draft is created (or the current one is used)
  - **volume** (float, default 1.0): Audio volume multiplier (0.0 mute, 1.0 original)
  - **track_name** (string, default "audio_main"): Audio track name
  - **speed** (float, default 1.0): Playback speed
  - **sound_effects** (list of [name, params] tuples): Effect name plus params list; names must match environment enums
  - **width** (int, default 1080): Project width in pixels
  - **height** (int, default 1920): Project height in pixels
  - **duration** (float|null): Explicit source duration (seconds); skips duration probing
- Key notes:
  - If neither `end` nor `duration` is provided, true duration is probed on save
  - Effect names must match environment enums; unknown effects are skipped with a warning
  - `speed` scales the target duration (`(end - start) / speed`).
  - **CRITICAL**: You CANNOT have temporally overlapping segments on the same track name! Use different `track_name` values for simultaneous audio segments. Of course, you can re-use the same track name for content that does NOT overlap in time.
- Example:
```yaml
- add_audio:
    audio_url: $assets.song
    start: 0
    end: 10
    volume: 0.7
```

#### add_image
- Purpose: Add an image as a photo segment
- Required:
  - **image_url** (string): Remote URL or local file path; supported image formats: .png, .jpg, .jpeg, .gif, .bmp, .tiff, .webp
- Optional:
  - **draft_folder** (string): Drafts root path used to write asset `replace_path`
  - **width** (int, default 1080): Project width in pixels
  - **height** (int, default 1920): Project height in pixels
  - **start** (float, default 0): Start time (seconds)
  - **end** (float, default 3.0): End time (seconds); duration is `end - start`
  - **draft_id** (string|null): Draft ID; if omitted a new draft is created (or the current one is used)
  - **transform_y** (float, default 0): Vertical position in normalized canvas coordinates
  - **scale_x** (float, default 1): Horizontal scale factor
  - **scale_y** (float, default 1): Vertical scale factor
  - **transform_x** (float, default 0): Horizontal position in normalized canvas coordinates
  - **track_name** (string, default "main"): Video track for photo segment
  - **relative_index** (int, default 0): Layer order among same-type tracks; higher renders above lower
  - Animations:
    - **animation** (string|null): Legacy entrance animation name (back-compat); must match environment enum
    - **animation_duration** (float, default 0.5): Legacy entrance animation duration (seconds)
    - **intro_animation** (string|null): Preferred entrance animation; must match environment enum
    - **intro_animation_duration** (float, default 0.5): Duration in seconds
    - **outro_animation** (string|null): Must match environment enum
    - **outro_animation_duration** (float, default 0.5): Duration in seconds
    - **combo_animation** (string|null): Must match environment enum
    - **combo_animation_duration** (float, default 0.5): Duration in seconds
  - Transition:
    - **transition** (string|null): Must match environment enum
    - **transition_duration** (float|null, default 0.5): Duration in seconds
  - Mask params:
    - **mask_type** (string|null): One of `Linear`, `Mirror`, `Circle`, `Rectangle`, `Heart`, `Star`
    - **mask_center_x** (float, default 0.0): Mask center X coordinate (in material pixels)
    - **mask_center_y** (float, default 0.0): Mask center Y coordinate (in material pixels)
    - **mask_size** (float, default 0.5): Main size of the mask, proportion of material height
    - **mask_rotation** (float, default 0.0): Clockwise rotation angle (degrees)
    - **mask_feather** (float, default 0.0): Feather amount, range 0–100
    - **mask_invert** (bool, default false): Whether to invert the mask
    - **mask_rect_width** (float|null): Rectangle mask width, proportion of material width (rectangle mask only)
    - **mask_round_corner** (float|null): Rectangle rounded corner, 0–100 (rectangle mask only)
  - **background_blur** (int|null): 1–4 maps to increasing blur intensity on background filling
- Key notes:
  - Ensure `end > start`; duration is `end - start`
  - Animation, transition, and mask names must match environment enums
  - **CRITICAL**: You CANNOT have temporally overlapping segments on the same track name! Use different `track_name` values for simultaneous images. Of course, you can re-use the same track name for content that does NOT overlap in time.
- Example:
```yaml
- add_image:
    image_url: $assets.logo
    start: 0
    end: 5
    intro_animation: Fade_in
    mask_type: circle
```

#### add_text
- Purpose: Add a text segment with rich styling
- Required:
  - **text** (string): Text content
  - **start** (float): Start time (seconds)
  - **end** (float): End time (seconds)
- Optional:
  - **draft_id** (string|null): Draft ID; if omitted a new draft is created (or the current one is used)
  - **transform_y** (float, default -0.8): Vertical position in normalized canvas coordinates (negative is higher)
  - **transform_x** (float, default 0): Horizontal position in normalized canvas coordinates
  - **font** (string|null): Must match a supported font name in the environment; invalid names raise an error
  - **font_color** (string, default "#ffffff"): Hex color `#RGB` or `#RRGGBB`
  - **font_size** (float, default 8.0): Text size units per environment defaults
  - **track_name** (string, default "text_main"): Text track name
  - **vertical** (bool, default false): Vertical typesetting
  - **font_alpha** (float, default 1.0): Text opacity in 0.0–1.0
  - Border:
    - **border_alpha** (float, default 1.0): Border opacity in 0.0–1.0
    - **border_color** (string, default "#000000"): Border color
    - **border_width** (float, default 0.0): Border width; 0 disables border
  - Background:
    - **background_alpha** (float, default 0.0): Opacity of a box behind the text; 0 disables. When > 0, a rectangle is drawn behind the text.
    - **background_color** (string, default "#000000"): Color of the background box. In the exporter this maps to drawtext `boxcolor` with the alpha above applied.
    - **background_round_radius** (float, default 0.0): Rounded-corner radius for the background box. Not supported by the exporter yet; setting > 0 will raise an error during export.
    - **background_width** (float, default 0.14): Intended logical width of the background box as a fraction of canvas width. Not used by the current exporter; the box auto-sizes to the text's bounding box.
    - **background_height** (float, default 0.14): Intended logical height of the background box as a fraction of canvas height. Not used by the current exporter; the box auto-sizes to the text's bounding box.
    - **background_horizontal_offset** (float, default 0.5): Intended horizontal offset of the background box relative to the text's center. Not used by the current exporter; the background is anchored to the text position.
    - **background_vertical_offset** (float, default 0.5): Intended vertical offset of the background box relative to the text's center. Not used by the current exporter; the background is anchored to the text position.
    - **background_style** (int, default 1): Reserved for future style presets. Not used by the current exporter.
  - Shadow:
    - **shadow_enabled** (bool, default false)
    - **shadow_alpha** (float, default 0.9)
    - **shadow_angle** (float, default -45.0)
    - **shadow_color** (string, default "#000000")
    - **shadow_distance** (float, default 5.0)
    - **shadow_smoothing** (float, default 0.15)
  - Bubble/Effect:
    - **bubble_effect_id** (string|null)
    - **bubble_resource_id** (string|null)
    - **effect_effect_id** (string|null)
  - Animations:
    - **intro_animation** (string|null): Must match environment enum
    - **intro_duration** (float, default 0.5): Duration in seconds
    - **outro_animation** (string|null): Must match environment enum
    - **outro_duration** (float, default 0.5): Duration in seconds
  - Canvas:
    - **width** (int, default 1080)
    - **height** (int, default 1920)
    - **fixed_width** (float, default -1): Ratio of canvas width; >0 converted to pixels
    - **fixed_height** (float, default -1): Ratio of canvas height; >0 converted to pixels
  - **text_styles** (list of ranges|null): Multi-style text ranges; each range must satisfy `0 <= start < end <= len(text)`
- Key notes:
  - `font` must be a valid font name in the environment; invalid names raise an error
  - Hex colors support `#RGB` and `#RRGGBB`
  - Background is emitted only if `background_alpha > 0`; border only if `border_width > 0`; shadow only when `shadow_enabled=True`.  
  - `text_styles` ranges must satisfy `0 <= start < end <= len(text)`
  - **CRITICAL**: You CANNOT have temporally overlapping segments on the same track name! Use different `track_name` values for simultaneous text segments. Of course, you can re-use the same track name for content that does NOT overlap in time.
  - `fixed_width`/`fixed_height` > 0 are converted to pixels by multiplying project width/height; `-1` disables fixed sizing.
- Example:
```yaml
- add_text:
    text: "Welcome"
    start: 0
    end: 3
    font_size: 48
    shadow_enabled: true
    background_color: "#000000"
```
**Available Fonts:**

```[
    'Roboto_BlkCn',
    'Poppins_Regular',
    'Poppins_Bold',
    'Nunito',
    'PlayfairDisplay_Bold',
    'Pacifico_Regular',
    'Caveat_Regular',
    'Grandstander_Regular',
    'DMSans_BoldItalic',
    'Exo',
    'Cabin_Rg',
    'Kanit_Regular',
    'Kanit_Black',
    'Staatliches_Regular',
    'Bungee_Regular',
    'Inter_Black',
    'SansitaSwashed_Regular',
    'SecularOne_Regular',
    'Sora_Regular',
    'Zapfino',
    'OldStandardTT_Regular',
    'Coiny_Regular',
    'HeptaSlab_ExtraBold',
    'HeptaSlab_Light',
    'Giveny'
]
```


#### add_subtitle
- Purpose: Import SRT as styled text
- Required:
  - **srt_path** (string): URL, local file path, or raw SRT content
- Optional:
  - **draft_id** (string|null): Draft ID; if omitted a new draft is created (or the current one is used)
  - **track_name** (string, default "subtitle")
  - **time_offset** (float, default 0): Shift all subtitle times (seconds)
  - Style:
    - **font** (string|null)
    - **font_size** (float, default 8.0)
    - **bold** (bool, default false)
    - **italic** (bool, default false)
    - **underline** (bool, default false)
    - **font_color** (string, default "#FFFFFF")
    - Border/background same as `add_text`:
      - **border_alpha** (float, default 1.0)
      - **border_color** (string, default "#000000")
      - **border_width** (float, default 0.0)
      - **background_color** (string, default "#000000")
      - **background_style** (int, default 1)
      - **background_alpha** (float, default 0.0)
    - Bubble/Effect:
      - **bubble_effect_id** (string|null)
      - **bubble_resource_id** (string|null)
      - **effect_effect_id** (string|null)
  - Transform:
    - **transform_x** (float, default 0.0)
    - **transform_y** (float, default -0.8)
    - **scale_x** (float, default 1.0)
    - **scale_y** (float, default 1.0)
    - **rotation** (float, default 0.0)
  - Other:
    - **style_reference** (Text segment reference|null)
    - **vertical** (bool, default true)
    - **alpha** (float, default 0.4)
    - **width** (int, default 1080)
    - **height** (int, default 1920)
- Key notes:
  - URLs are fetched; local files read as UTF-8; raw content is accepted
  - Border/background emitted only when their enabling values are set
  - **CRITICAL**: You CANNOT have temporally overlapping segments on the same track name! Use different `track_name` values for simultaneous subtitle segments. Of course, you can re-use the same track name for content that does NOT overlap in time.
- Example:
```yaml
- add_subtitle:
    srt_path: ./subs/movie.srt
    font_size: 10
    font_color: "#FFFFFF"
```

#### add_effect
- Purpose: Add a video effect on an effect track
- Required:
  - **effect_type** (string): Must match environment enum
  - **effect_category** (string): "scene" or "character"
- Optional:
  - **start** (float, default 0)
  - **end** (float, default 3.0)
  - **draft_id** (string|null): Draft ID; if omitted a new draft is created (or the current one is used)
  - **track_name** (string, default "effect_01")
  - **params** (list of float|null): Effect params
  - **width** (int, default 1080)
  - **height** (int, default 1920)
- Key notes:
  - Unknown `effect_type` raises an error
  - **CRITICAL**: You CANNOT have temporally overlapping effects on the same track name! Use different `track_name` values for simultaneous effects. Of course, you can re-use the same track name for content that does NOT overlap in time.
- Example:
```yaml
- add_effect:
    effect_category: scene
    effect_type: Blur
    start: 0
    end: 2
```

#### add_sticker
- Purpose: Add a sticker segment
- Required:
  - **resource_id** (string): Sticker resource ID
  - **start** (float): Start time (seconds)
  - **end** (float): End time (seconds)
- Optional:
  - **draft_id** (string|null): Draft ID; if omitted a new draft is created (or the current one is used)
  - **transform_y** (float, default 0): Vertical position in normalized canvas coordinates
  - **transform_x** (float, default 0): Horizontal position in normalized canvas coordinates
  - **alpha** (float, default 1.0): Opacity in 0.0–1.0
  - **flip_horizontal** (bool, default false)
  - **flip_vertical** (bool, default false)
  - **rotation** (float, default 0.0): Clockwise degrees
  - **scale_x** (float, default 1.0): Horizontal scale factor
  - **scale_y** (float, default 1.0): Vertical scale factor
  - **track_name** (string, default "sticker_main")
  - **relative_index** (int, default 0): Layer order among same-type tracks; higher renders above lower
  - **width** (int, default 1080)
  - **height** (int, default 1920)
- Key notes:
  - **CRITICAL**: You CANNOT have temporally overlapping stickers on the same track name! Use different `track_name` values for simultaneous stickers. Of course, you can re-use the same track name for content that does NOT overlap in time.
- Example:
```yaml
- add_sticker:
    resource_id: some-sticker-id
    start: 1
    end: 4
    scale_x: 1.2
    scale_y: 1.2
```

#### add_video_keyframe
- Purpose: Add one or more keyframes to the first segment in the specified video track
- Required (single mode):
  - **property_type** (string, default "alpha")
  - **time** (float, default 0.0): Seconds relative to the segment start
  - **value** (string, default "1.0"): See value formats below
- Required (batch mode, use together):
  - **property_types** (list[string])
  - **times** (list[float])
  - **values** (list[string])
- Optional:
  - **track_name** (string, default "main")
  - **draft_id** (string|null): Draft ID; if omitted a new draft is created (or the current one is used)
- Key notes:
  - Batch mode requires all three lists with equal length; otherwise error
  - Supported properties: `position_x`, `position_y`, `rotation`, `scale_x`, `scale_y`, `uniform_scale`, `alpha`, `saturation`, `contrast`, `brightness`, `volume`
  - Value formats:
    - `position_x`/`position_y`: normalized coordinates (accepted range `[-10, 10]`; typical canvas range is `[-1, 1]`, e.g., "0.0", "-0.3")
    - `rotation`: degrees (e.g., "45deg" or numeric)
    - `scale_x`/`scale_y`/`uniform_scale`: numeric factors (e.g., "1.2")
    - `alpha`, `volume`: percent (e.g., "50%") or numeric 0..1
    - `saturation`/`contrast`/`brightness`: relative deltas like "+0.5", "-0.5", or numeric
- Example:
```yaml
- add_video_keyframe:
    track_name: main
    property_types: [scale_x, scale_y, alpha]
    times: [0, 2, 4]
    values: ["1.0", "1.2", "0.8"]
```


