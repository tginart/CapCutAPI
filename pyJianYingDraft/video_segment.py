"""Define video segments and related classes

Includes classes for image adjustment settings, animations, effects, transitions, etc.
"""

import uuid
from copy import deepcopy

from typing import Optional, Literal, Union, overload
from typing import Dict, List, Tuple, Any

from pyJianYingDraft.metadata.capcut_effect_meta import CapCut_Video_character_effect_type, CapCut_Video_scene_effect_type
from pyJianYingDraft.metadata.capcut_mask_meta import CapCut_Mask_type
from settings import IS_CAPCUT_ENV

from .time_util import tim, Timerange
from .segment import Visual_segment, Clip_settings
from .local_materials import Video_material
from .animation import Segment_animations, Video_animation

from .metadata import Effect_meta, Effect_param_instance
from .metadata import Mask_meta, Mask_type, Filter_type, Transition_type, CapCut_Transition_type
from .metadata import Intro_type, Outro_type, Group_animation_type
from .metadata import CapCut_Intro_type, CapCut_Outro_type, CapCut_Group_animation_type
from .metadata import Video_scene_effect_type, Video_character_effect_type


class Mask:
    """Mask object"""

    mask_meta: Mask_meta
    """Mask metadata"""
    global_id: str
    """Global mask id, auto-generated"""

    center_x: float
    """Mask center x-coordinate, in units of half material width"""
    center_y: float
    """Mask center y-coordinate, in units of half material height"""
    width: float
    height: float
    aspect_ratio: float

    rotation: float
    invert: bool
    feather: float
    """Feather amount, 0-1"""
    round_corner: float
    """Corner radius for rectangular mask, 0-1"""

    def __init__(self, mask_meta: Mask_meta,
                 cx: float, cy: float, w: float, h: float,
                 ratio: float, rot: float, inv: bool, feather: float, round_corner: float):
        self.mask_meta = mask_meta
        self.global_id = uuid.uuid4().hex

        self.center_x, self.center_y = cx, cy
        self.width, self.height = w, h
        self.aspect_ratio = ratio

        self.rotation = rot
        self.invert = inv
        self.feather = feather
        self.round_corner = round_corner

    def export_json(self) -> Dict[str, Any]:
        return {
            "config": {
                "aspectRatio": self.aspect_ratio,
                "centerX": self.center_x,
                "centerY": self.center_y,
                "feather": self.feather,
                "height": self.height,
                "invert": self.invert,
                "rotation": self.rotation,
                "roundCorner": self.round_corner,
                "width": self.width
            },
            "category": "video",
            "category_id": "",
            "category_name": "",
            "id": self.global_id,
            "name": self.mask_meta.name,
            "platform": "all",
            "position_info": "",
            "resource_type": self.mask_meta.resource_type,
            "resource_id": self.mask_meta.resource_id,
            "type": "mask"
            # Do not export the path field
        }

class Video_effect:
    """Video effect material"""

    name: str
    """Effect name"""
    global_id: str
    """Effect global id, auto-generated"""
    effect_id: str
    """Effect id, provided by CapCut"""
    resource_id: str
    """Resource id, provided by CapCut"""

    effect_type: Literal["video_effect", "face_effect"]
    apply_target_type: Literal[0, 2]
    """Apply target type, 0: clip, 2: global"""

    adjust_params: List[Effect_param_instance]

    def __init__(self, effect_meta: Union[Video_scene_effect_type, Video_character_effect_type],
                 params: Optional[List[Optional[float]]] = None, *,
                 apply_target_type: Literal[0, 2] = 0):
        """Construct a video effect object from the given effect metadata and parameter list; params range is 0-100"""

        self.name = effect_meta.value.name
        self.global_id = uuid.uuid4().hex
        self.effect_id = effect_meta.value.effect_id
        self.resource_id = effect_meta.value.resource_id
        self.adjust_params = []

        if IS_CAPCUT_ENV:
            if isinstance(effect_meta, CapCut_Video_scene_effect_type):
                self.effect_type = "video_effect"
            elif isinstance(effect_meta, CapCut_Video_character_effect_type):
                self.effect_type = "face_effect"
            else:
                raise TypeError("Invalid effect meta type %s" % type(effect_meta))
        else:
            if isinstance(effect_meta, Video_scene_effect_type):
                self.effect_type = "video_effect"
            elif isinstance(effect_meta, Video_character_effect_type):
                self.effect_type = "face_effect"
            else:
                raise TypeError("Invalid effect meta type %s" % type(effect_meta))

        self.apply_target_type = apply_target_type

        self.adjust_params = effect_meta.value.parse_params(params)

    def export_json(self) -> Dict[str, Any]:
        return {
            "adjust_params": [param.export_json() for param in self.adjust_params],
            "apply_target_type": self.apply_target_type,
            "apply_time_range": None,
            "category_id": "",  # Always set empty
            "category_name": "",  # Always set empty
            "common_keyframes": [],
            "disable_effect_faces": [],
            "effect_id": self.effect_id,
            "formula_id": "",
            "id": self.global_id,
            "name": self.name,
            "platform": "all",
            "render_index": 11000,
            "resource_id": self.resource_id,
            "source_platform": 0,
            "time_range": None,
            "track_render_index": 0,
            "type": self.effect_type,
            "value": 1.0,
            "version": ""
            # Do not export the fields path, request_id, and algorithm_artifact_path
        }

class Filter:
    """Filter material"""

    global_id: str
    """Filter global id, auto-generated"""

    effect_meta: Effect_meta
    """Filter metadata"""
    intensity: float
    """Filter intensity (the only parameter)"""

    apply_target_type: Literal[0, 2]
    """Apply target type, 0: clip, 2: global"""

    def __init__(self, meta: Effect_meta, intensity: float, *,
                 apply_target_type: Literal[0, 2] = 0):
        """Construct a filter material object from the given filter metadata and intensity"""

        self.global_id = uuid.uuid4().hex
        self.effect_meta = meta
        self.intensity = intensity
        self.apply_target_type = apply_target_type

    def export_json(self) -> Dict[str, Any]:
        return {
            "adjust_params": [],
            "algorithm_artifact_path": "",
            "apply_target_type": self.apply_target_type,
            "bloom_params": None,
            "category_id": "",  # Always set empty
            "category_name": "",  # Always set empty
            "color_match_info": {
                "source_feature_path": "",
                "target_feature_path": "",
                "target_image_path": ""
            },
            "effect_id": self.effect_meta.effect_id,
            "enable_skin_tone_correction": False,
            "exclusion_group": [],
            "face_adjust_params": [],
            "formula_id": "",
            "id": self.global_id,
            "intensity_key": "",
            "multi_language_current": "",
            "name": self.effect_meta.name,
            "panel_id": "",
            "platform": "all",
            "resource_id": self.effect_meta.resource_id,
            "source_platform": 1,
            "sub_type": "none",
            "time_range": None,
            "type": "filter",
            "value": self.intensity,
            "version": ""
            # Do not export path and request_id
        }

class Transition:
    """Transition object"""

    name: str
    """Transition name"""
    global_id: str
    """Transition global id, auto-generated"""
    effect_id: str
    """Transition effect id, provided by CapCut"""
    resource_id: str
    """Resource id, provided by CapCut"""

    duration: int
    """Transition duration, in microseconds"""
    is_overlap: bool
    """Whether it overlaps with the previous clip (?)"""

    def __init__(self, effect_meta: Union[Transition_type, CapCut_Transition_type], duration: Optional[int] = None):
        """Construct a transition object from the given transition metadata and duration"""
        self.name = effect_meta.value.name
        self.global_id = uuid.uuid4().hex
        self.effect_id = effect_meta.value.effect_id
        self.resource_id = effect_meta.value.resource_id

        self.duration = duration if duration is not None else effect_meta.value.default_duration
        self.is_overlap = effect_meta.value.is_overlap

    def export_json(self) -> Dict[str, Any]:
        return {
            "category_id": "",  # Always set empty
            "category_name": "",  # Always set empty
            "duration": self.duration,
            "effect_id": self.effect_id,
            "id": self.global_id,
            "is_overlap": self.is_overlap,
            "name": self.name,
            "platform": "all",
            "resource_id": self.resource_id,
            "type": "transition"
            # Do not export path and request_id fields
        }

class BackgroundFilling:
    """Background filling object"""

    global_id: str
    """Background filling global id, auto-generated"""
    fill_type: Literal["canvas_blur", "canvas_color"]
    """Background filling type"""
    blur: float
    """Blur amount, 0-1"""
    color: str
    """Background color, format '#RRGGBBAA'"""

    def __init__(self, fill_type: Literal["canvas_blur", "canvas_color"], blur: float, color: str):
        self.global_id = uuid.uuid4().hex
        self.fill_type = fill_type
        self.blur = blur
        self.color = color

    def export_json(self) -> Dict[str, Any]:
        return {
            "id": self.global_id,
            "type": self.fill_type,
            "blur": self.blur,
            "color": self.color,
            "source_platform": 0,
        }

class Video_segment(Visual_segment):
    """A video/image segment placed on a track"""

    material_instance: Video_material
    """Material instance"""
    material_size: Tuple[int, int]
    """Material size"""

    effects: List[Video_effect]
    """Effects list

    Automatically added to the materials list when placed on a track
    """
    filters: List[Filter]
    """Filters list

    Automatically added to the materials list when placed on a track
    """
    mask: Optional[Mask]
    """Mask instance, may be None

    Automatically added to the materials list when placed on a track
    """
    transition: Optional[Transition]
    """Transition instance, may be None

    Automatically added to the materials list when placed on a track
    """
    background_filling: Optional[BackgroundFilling]
    """Background filling instance, may be None

    Automatically added to the materials list when placed on a track
    """

    visible: Optional[bool]
    """Whether visible
    Defaults to True
    """

    # TODO: Allow the material parameter to accept a path for convenient construction
    def __init__(self, material: Video_material, target_timerange: Timerange, *,
                 source_timerange: Optional[Timerange] = None, speed: Optional[float] = None, volume: float = 1.0,
                 clip_settings: Optional[Clip_settings] = None):
        """Construct a track segment using the given video/image material, specifying timing and image adjustment settings

        Args:
            material (`Video_material`): Material instance
            target_timerange (`Timerange`): Target time range of the segment on the track
            source_timerange (`Timerange`, optional): Time range of the clipped portion of the material. By default, starting from the beginning, clip a portion whose length equals `target_timerange`, determined by `speed`.
            speed (`float`, optional): Playback speed, default 1.0. When specified together with `source_timerange`, overrides the duration in `target_timerange`.
            volume (`float`, optional): Volume, default 1.0
            clip_settings (`Clip_settings`, optional): Image adjustment settings, no transformation by default

        Raises:
            `ValueError`: The specified or computed `source_timerange` exceeds the material duration
        """
        # if source_timerange is not None and speed is not None:
        #     target_timerange = Timerange(target_timerange.start, round(source_timerange.duration / speed))
        # elif source_timerange is not None and speed is None:
        #     speed = source_timerange.duration / target_timerange.duration
        # else:  # source_timerange is None
        #     speed = speed if speed is not None else 1.0
        #     source_timerange = Timerange(0, round(target_timerange.duration * speed))

        # if source_timerange.end > material.duration:
        #     source_timerange = Timerange(source_timerange.start, material.duration - source_timerange.start)
        #     # Recalculate the target time range
        #     target_timerange = Timerange(target_timerange.start, round(source_timerange.duration / speed))

        super().__init__(material.material_id, source_timerange, target_timerange, speed, volume, clip_settings=clip_settings)

        self.material_instance = deepcopy(material)
        self.material_size = (material.width, material.height)
        self.effects = []
        self.filters = []
        self.transition = None
        self.mask = None
        self.background_filling = None

    def add_animation(self, animation_type: Union[Intro_type, Outro_type, Group_animation_type, CapCut_Intro_type, CapCut_Outro_type, CapCut_Group_animation_type],
                      duration: Optional[Union[int, str]] = None) -> "Video_segment":
        """Add the given intro/outro/group animation to this segment's animation list

        Args:
            animation_type (`Intro_type`, `Outro_type`, or `Group_animation_type`): Animation type
            duration (`int` or `str`, optional): Animation duration in microseconds. If a string is provided, it is parsed by `tim()`.
                If unspecified, uses the default defined by the animation type. In principle, applies only to intro and outro animations.
        """
        if duration is not None:
            duration = tim(duration)
        if (isinstance(animation_type, Intro_type) or isinstance(animation_type, CapCut_Intro_type)):
            start = 0
            duration = duration or animation_type.value.duration
        elif isinstance(animation_type, Outro_type) or isinstance(animation_type, CapCut_Outro_type):
            duration = duration or animation_type.value.duration
            start = self.target_timerange.duration - duration
        elif isinstance(animation_type, Group_animation_type) or isinstance(animation_type, CapCut_Group_animation_type):
            start = 0
            duration = duration or self.target_timerange.duration
        else:
            raise TypeError("Invalid animation type %s" % type(animation_type))

        if self.animations_instance is None:
            self.animations_instance = Segment_animations()
            self.extra_material_refs.append(self.animations_instance.animation_id)

        self.animations_instance.add_animation(Video_animation(animation_type, start, duration))

        return self

    def add_effect(self, effect_type: Union[Video_scene_effect_type, Video_character_effect_type],
                   params: Optional[List[Optional[float]]] = None) -> "Video_segment":
        """Add an effect that applies to the entire video segment

        Args:
            effect_type (`Video_scene_effect_type` or `Video_character_effect_type`): Effect type
            params (`List[Optional[float]]`, optional): Effect parameter list. Items not provided or set to None use default values.
                Parameter range (0-100) matches CapCut. For a given effect type, which parameters exist and their order are defined by the enum member's annotations.

        Raises:
            `ValueError`: Provided parameter count exceeds the number of parameters for the effect type, or parameter values are out of range.
        """
        if params is not None and len(params) > len(effect_type.value.params):
            raise ValueError("Too many parameters passed for audio effect %s" % effect_type.value.name)

        effect_inst = Video_effect(effect_type, params)
        self.effects.append(effect_inst)
        self.extra_material_refs.append(effect_inst.global_id)

        return self

    def add_filter(self, filter_type: Filter_type, intensity: float = 100.0) -> "Video_segment":
        """Add a filter to the video segment

        Args:
            filter_type (`Filter_type`): Filter type
            intensity (`float`, optional): Filter intensity (0-100). Effective only when the selected filter supports intensity adjustment. Defaults to 100.
        """
        filter_inst = Filter(filter_type.value, intensity / 100.0)  # Convert to the 0~1 range
        self.filters.append(filter_inst)
        self.extra_material_refs.append(filter_inst.global_id)

        return self

    def add_mask(self, draft: "Script_file", mask_type: Union[Mask_type, CapCut_Mask_type], *, center_x: float = 0.0, center_y: float = 0.0, size: float = 0.5,
                 rotation: float = 0.0, feather: float = 0.0, invert: bool = False,
                 rect_width: Optional[float] = None, round_corner: Optional[float] = None) -> "Video_segment":
        """Add a mask to the video segment

        Args:
            mask_type (`Mask_type`): Mask type
            center_x (`float`, optional): X coordinate of the mask center (in material pixels). Defaults to the material center
            center_y (`float`, optional): Y coordinate of the mask center (in material pixels). Defaults to the material center
            size (`float`, optional): The "primary size" of the mask (visible part height for mirror/circle diameter/heart height, etc.), expressed as a proportion of material height. Defaults to 0.5
            rotation (`float`, optional): Clockwise rotation angle of the mask. Defaults to no rotation
            feather (`float`, optional): Feather parameter of the mask, range 0-100. Defaults to no feathering
            invert (`bool`, optional): Whether to invert the mask. Defaults to False
            rect_width (`float`, optional): Width of the rectangular mask. Allowed only when the mask type is rectangular, expressed as a proportion of material width. Defaults to the same as `size`
            round_corner (`float`, optional): Corner radius parameter for rectangular masks. Allowed only when the mask type is rectangular, range 0-100. Defaults to 0

        Raises:
            `ValueError`: Attempted to add multiple masks or incorrectly set `rect_width` and `round_corner`
        """

        if self.mask is not None:
            raise ValueError("This segment already has a mask and cannot add another")
        if (rect_width is not None or round_corner is not None) and (mask_type != Mask_type.矩形 and mask_type != CapCut_Mask_type.Rectangle):
            raise ValueError("`rect_width` and `round_corner` are only allowed when the mask type is rectangular")
        if rect_width is None and (mask_type == Mask_type.矩形 or mask_type == CapCut_Mask_type.Rectangle):
            rect_width = size
        if round_corner is None:
            round_corner = 0

        # Get the draft width and height, instead of using the material's
        draft_width = draft.width
        draft_height = draft.height
        
        width = rect_width or size * draft_height * mask_type.value.default_aspect_ratio / draft_width
        self.mask = Mask(mask_type.value, center_x / (draft_width / 2), center_y / (draft_height / 2),
                         w=width, h=size, ratio=mask_type.value.default_aspect_ratio,
                         rot=rotation, inv=invert, feather=feather/100, round_corner=round_corner/100)
        self.extra_material_refs.append(self.mask.global_id)
        return self

    def add_transition(self, transition_type: Union[Transition_type, CapCut_Transition_type], *, duration: Optional[Union[int, str]] = None) -> "Video_segment":
        """Add a transition to the video segment. Note: the transition should be added to the previous segment

        Args:
            transition_type (`Transition_type` or `CapCut_Transition_type`): Transition type
            duration (`int` or `str`, optional): Transition duration in microseconds. If a string is provided, it is parsed by `tim()`. If unspecified, uses the default defined by the transition type.

        Raises:
            `ValueError`: Attempted to add multiple transitions.
        """
        if self.transition is not None:
            raise ValueError("This segment already has a transition and cannot add another")
        if isinstance(duration, str): duration = tim(duration)

        self.transition = Transition(transition_type, duration)
        self.extra_material_refs.append(self.transition.global_id)
        return self

    def add_background_filling(self, fill_type: Literal["blur", "color"], blur: float = 0.0625, color: str = "#00000000") -> "Video_segment":
        """Add background filling to the video segment

        Note: Background filling only takes effect for segments on the bottom video track

        Args:
            fill_type (`blur` or `color`): Filling type. `blur` means blur, `color` means color.
            blur (`float`, optional): Blur amount, 0.0-1.0. Effective only when `fill_type` is `blur`. The four blur levels in CapCut are 0.0625, 0.375, 0.75, and 1.0. Defaults to 0.0625.
            color (`str`, optional): Fill color, format '#RRGGBBAA'. Effective only when `fill_type` is `color`.

        Raises:
            `ValueError`: The segment already has a background filling effect or `fill_type` is invalid.
        """
        if self.background_filling is not None:
            raise ValueError("This segment already has a background filling effect")

        if fill_type == "blur":
            self.background_filling = BackgroundFilling("canvas_blur", blur, color)
        elif fill_type == "color":
            self.background_filling = BackgroundFilling("canvas_color", blur, color)
        else:
            raise ValueError(f"Invalid background filling type {fill_type}")

        self.extra_material_refs.append(self.background_filling.global_id)
        return self

    def export_json(self) -> Dict[str, Any]:
        json_dict = super().export_json()
        json_dict.update({
            "hdr_settings": {"intensity": 1.0, "mode": 1, "nits": 1000},
        })
        return json_dict

class Sticker_segment(Visual_segment):
    """A sticker segment placed on a track"""

    resource_id: str
    """Sticker resource id"""

    def __init__(self, resource_id: str, target_timerange: Timerange, *, clip_settings: Optional[Clip_settings] = None):
        """Construct a sticker segment from the sticker resource_id and specify its timing and image adjustment settings

        After creating the segment, you can add it to the track via `Script_file.add_segment`

        Args:
            resource_id (`str`): Sticker resource_id, obtainable from the template via `Script_file.inspect_material`
            target_timerange (`Timerange`): Target time range of the segment on the track
            clip_settings (`Clip_settings`, optional): Image adjustment settings, no transformation by default
        """
        super().__init__(uuid.uuid4().hex, None, target_timerange, 1.0, 1.0, clip_settings=clip_settings)
        self.resource_id = resource_id

    def export_material(self) -> Dict[str, Any]:
        """Create a minimal sticker material object, avoiding a separate sticker material class"""
        return {
            "id": self.material_id,
            "resource_id": self.resource_id,
            "sticker_id": self.resource_id,
            "source_platform": 1,
            "type": "sticker",
        }
