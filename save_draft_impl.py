import os
import re
import pyJianYingDraft as draft
import shutil
from util import zip_draft, is_windows_path
from oss import upload_to_oss
from typing import Dict, Literal, Optional, List, Union
from draft_cache import DRAFT_CACHE
from save_task_cache import DRAFT_TASKS, get_task_status, update_tasks_cache, update_task_field, increment_task_field, update_task_fields, create_task
from downloader import download_audio, download_file, download_image, download_video
from concurrent.futures import ThreadPoolExecutor, as_completed
import imageio.v2 as imageio
import subprocess
import json
from get_duration_impl import get_video_duration
import uuid
import threading
from collections import OrderedDict
import time
import requests # Import requests for making HTTP calls
import logging
# Import configuration
from settings import IS_CAPCUT_ENV, IS_UPLOAD_DRAFT

# --- Get your Logger instance ---
# The name here must match the logger name you configured in app.py
logger = logging.getLogger('flask_video_generator') 

# Define task status enumeration type
TaskStatus = Literal["initialized", "processing", "completed", "failed", "not_found"]

def build_asset_path(draft_folder: str, draft_id: str, asset_type: str, material_name: str) -> str:
    """
    Build asset file path
    :param draft_folder: Draft folder path
    :param draft_id: Draft ID
    :param asset_type: Asset type (audio, image, video)
    :param material_name: Material name
    :return: Built path
    """
    if is_windows_path(draft_folder):
        if os.name == 'nt': # 'nt' for Windows
            draft_real_path = os.path.join(draft_folder, draft_id, "assets", asset_type, material_name)
        else:
            windows_drive, windows_path = re.match(r'([a-zA-Z]:)(.*)', draft_folder).groups()
            parts = [p for p in windows_path.split('\\') if p]
            draft_real_path = os.path.join(windows_drive, *parts, draft_id, "assets", asset_type, material_name)
            draft_real_path = draft_real_path.replace('/', '\\')
    else:
        draft_real_path = os.path.join(draft_folder, draft_id, "assets", asset_type, material_name)
    return draft_real_path

def save_draft_background(draft_id, draft_folder, task_id):
    """Background save draft to OSS"""
    try:
        # Get draft information from global cache
        if draft_id not in DRAFT_CACHE:
            task_status = {
                "status": "failed",
                "message": f"Draft {draft_id} does not exist in cache",
                "progress": 0,
                "completed_files": 0,
                "total_files": 0,
                "draft_url": ""
            }
            update_tasks_cache(task_id, task_status)  # Use new cache management function
            logger.error(f"Draft {draft_id} does not exist in cache, task {task_id} failed.")
            return
            
        script = DRAFT_CACHE[draft_id]
        logger.info(f"Successfully retrieved draft {draft_id} from cache.")
        
        # Update task status to processing
        task_status = {
            "status": "processing",
            "message": "Preparing draft files",
            "progress": 0,
            "completed_files": 0,
            "total_files": 0,
            "draft_url": ""
        }
        update_tasks_cache(task_id, task_status)  # Use new cache management function
        logger.info(f"Task {task_id} status updated to 'processing': Preparing draft files.")
        
        # Delete possibly existing draft_id folder
        if os.path.exists(draft_id):
            logger.warning(f"Deleting existing draft folder (current working directory): {draft_id}")
            shutil.rmtree(draft_id)

        logger.info(f"Starting to save draft: {draft_id}")
        # Save draft
        current_dir = os.path.dirname(os.path.abspath(__file__))
        draft_folder_for_duplicate = draft.Draft_folder(current_dir)
        # Choose different template directory based on configuration
        template_dir = "template" if IS_CAPCUT_ENV else "template_jianying"
        draft_folder_for_duplicate.duplicate_as_template(template_dir, draft_id)
        
        # Update task status
        update_task_field(task_id, "message", "Updating media file metadata")
        update_task_field(task_id, "progress", 5)
        logger.info(f"Task {task_id} progress 5%: Updating media file metadata.")
        
        update_media_metadata(script, task_id)
        
        download_tasks = []
        
        audios = script.materials.audios
        if audios:
            for audio in audios:
                remote_url = audio.remote_url
                material_name = audio.material_name
                # Use helper function to build path
                if draft_folder:
                    audio.replace_path = build_asset_path(draft_folder, draft_id, "audio", material_name)
                if not remote_url:
                    logger.warning(f"Audio file {material_name} has no remote_url, skipping download.")
                    continue
                
                # Add audio download task
                download_tasks.append({
                    'type': 'audio',
                    'func': download_file,
                    'args': (remote_url, os.path.join(current_dir, f"{draft_id}/assets/audio/{material_name}")),
                    'material': audio
                })
        
        # Collect video and image download tasks
        videos = script.materials.videos
        if videos:
            for video in videos:
                remote_url = video.remote_url
                material_name = video.material_name
                
                if video.material_type == 'photo':
                    # Use helper function to build path
                    if draft_folder:
                        video.replace_path = build_asset_path(draft_folder, draft_id, "image", material_name)
                    if not remote_url:
                        logger.warning(f"Image file {material_name} has no remote_url, skipping download.")
                        continue
                    
                    # Add image download task
                    download_tasks.append({
                        'type': 'image',
                        'func': download_file,
                        'args': (remote_url, os.path.join(current_dir, f"{draft_id}/assets/image/{material_name}")),
                        'material': video
                    })
                
                elif video.material_type == 'video':
                    # Use helper function to build path
                    if draft_folder:
                        video.replace_path = build_asset_path(draft_folder, draft_id, "video", material_name)
                    if not remote_url:
                        logger.warning(f"Video file {material_name} has no remote_url, skipping download.")
                        continue
                    
                    # Add video download task
                    download_tasks.append({
                        'type': 'video',
                        'func': download_file,
                        'args': (remote_url, os.path.join(current_dir, f"{draft_id}/assets/video/{material_name}")),
                        'material': video
                    })

        update_task_field(task_id, "message", f"Collected {len(download_tasks)} download tasks in total")
        update_task_field(task_id, "progress", 10)
        logger.info(f"Task {task_id} progress 10%: Collected {len(download_tasks)} download tasks in total.")

        # Execute all download tasks concurrently
        downloaded_paths = []
        completed_files = 0
        if download_tasks:
            logger.info(f"Starting concurrent download of {len(download_tasks)} files...")
            
            # Use thread pool for concurrent downloads, maximum concurrency of 16
            with ThreadPoolExecutor(max_workers=16) as executor:
                # Submit all download tasks
                future_to_task = {
                    executor.submit(task['func'], *task['args']): task 
                    for task in download_tasks
                }
                
                # Wait for all tasks to complete
                for future in as_completed(future_to_task):
                    task = future_to_task[future]
                    try:
                        local_path = future.result()
                        downloaded_paths.append(local_path)
                        
                        # Update task status - only update completed files count
                        completed_files += 1
                        update_task_field(task_id, "completed_files", completed_files)
                        task_status = get_task_status(task_id)
                        completed = task_status["completed_files"]
                        total = len(download_tasks)
                        update_task_field(task_id, "total_files", total)
                        # Download part accounts for 60% of the total progress
                        download_progress = 10 + int((completed / total) * 60)
                        update_task_field(task_id, "progress", download_progress)
                        update_task_field(task_id, "message", f"Downloaded {completed}/{total} files")
                        
                        logger.info(f"Task {task_id}: Successfully downloaded {task['type']} file, progress {download_progress}.")
                    except Exception as e:
                        logger.error(f"Task {task_id}: Download {task['type']} file failed: {str(e)}", exc_info=True)
                        # Continue processing other files, don't interrupt the entire process
            
            logger.info(f"Task {task_id}: Concurrent download completed, downloaded {len(downloaded_paths)} files in total.")
        
        # Update task status - Start saving draft information
        update_task_field(task_id, "progress", 70)
        update_task_field(task_id, "message", "Saving draft information")
        logger.info(f"Task {task_id} progress 70%: Saving draft information.")
        
        script.dump(os.path.join(current_dir, f"{draft_id}/draft_info.json"))
        logger.info(f"Draft information has been saved to {os.path.join(current_dir, draft_id)}/draft_info.json.")

        draft_url = ""
        # Only upload draft information when IS_UPLOAD_DRAFT is True
        if IS_UPLOAD_DRAFT:
            # Update task status - Start compressing draft
            update_task_field(task_id, "progress", 80)
            update_task_field(task_id, "message", "Compressing draft files")
            logger.info(f"Task {task_id} progress 80%: Compressing draft files.")
            
            # Compress the entire draft directory
            zip_path = zip_draft(draft_id)
            logger.info(f"Draft directory {os.path.join(current_dir, draft_id)} has been compressed to {zip_path}.")
            
            # Update task status - Start uploading to OSS
            update_task_field(task_id, "progress", 90)
            update_task_field(task_id, "message", "Uploading to cloud storage")
            logger.info(f"Task {task_id} progress 90%: Uploading to cloud storage.")
            
            # Upload to OSS
            draft_url = upload_to_oss(zip_path)
            logger.info(f"Draft archive has been uploaded to OSS, URL: {draft_url}")
            update_task_field(task_id, "draft_url", draft_url)

            # Clean up temporary files
            if os.path.exists(os.path.join(current_dir, draft_id)):
                shutil.rmtree(os.path.join(current_dir, draft_id))
                logger.info(f"Cleaned up temporary draft folder: {os.path.join(current_dir, draft_id)}")

    
        # Update task status - Completed
        update_task_field(task_id, "status", "completed")
        update_task_field(task_id, "progress", 100)
        update_task_field(task_id, "message", "Draft creation completed")
        logger.info(f"Task {task_id} completed, draft URL: {draft_url}")
        return draft_url

    except Exception as e:
        # Update task status - Failed
        update_task_fields(task_id, 
                          status="failed",
                          message=f"Failed to save draft: {str(e)}")
        logger.error(f"Saving draft {draft_id} task {task_id} failed: {str(e)}", exc_info=True)
        return ""

def query_task_status(task_id: str):
    return get_task_status(task_id)

def save_draft_impl(draft_id: str, draft_folder: str = None) -> Dict[str, str]:
    """Start a background task to save the draft"""
    logger.info(f"Received save draft request: draft_id={draft_id}, draft_folder={draft_folder}")
    try:
        # Generate a unique task ID
        task_id = draft_id
        create_task(task_id)
        logger.info(f"Task {task_id} has been created.")
        
        # Changed to synchronous execution
        return {
            "success": True,
            "draft_url": save_draft_background(draft_id, draft_folder, task_id)
            }

        # # Start a background thread to execute the task
        # thread = threading.Thread(
        #     target=save_draft_background,
        #     args=(draft_id, draft_folder, task_id)
        # )
        # thread.start()
        
    except Exception as e:
        logger.error(f"Failed to start save draft task {draft_id}: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }

def update_media_metadata(script, task_id=None):
    """
    Update metadata for all media files in the script (duration, width/height, etc.)
    
    :param script: Draft script object
    :param task_id: Optional task ID for updating task status
    :return: None
    """
    # Process audio file metadata
    audios = script.materials.audios
    if not audios:
        logger.info("No audio files found in the draft.")
    else:
        for audio in audios:
            remote_url = audio.remote_url
            material_name = audio.material_name
            if not remote_url:
                logger.warning(f"Warning: Audio file {material_name} has no remote_url, skipped.")
                continue
            
            try:
                video_command = [
                    'ffprobe',
                    '-v', 'error',
                    '-select_streams', 'v:0',
                    '-show_entries', 'stream=codec_type',
                    '-of', 'json',
                    remote_url
                ]
                video_result = subprocess.check_output(video_command, stderr=subprocess.STDOUT)
                video_result_str = video_result.decode('utf-8')
                # Find JSON start position (first '{')
                video_json_start = video_result_str.find('{')
                if video_json_start != -1:
                    video_json_str = video_result_str[video_json_start:]
                    video_info = json.loads(video_json_str)
                    if 'streams' in video_info and len(video_info['streams']) > 0:
                        logger.warning(f"Warning: Audio file {material_name} contains video tracks, skipped its metadata update.")
                        continue
            except Exception as e:
                logger.error(f"Error occurred while checking if audio {material_name} contains video streams: {str(e)}", exc_info=True)

            # Get audio duration and set it
            try:
                duration_result = get_video_duration(remote_url)
                if duration_result["success"]:
                    if task_id:
                        update_task_field(task_id, "message", f"Processing audio metadata: {material_name}")
                    # Convert seconds to microseconds
                    audio.duration = int(duration_result["output"] * 1000000)
                    logger.info(f"Successfully obtained audio {material_name} duration: {duration_result['output']:.2f} seconds ({audio.duration} microseconds).")
                    
                    # Update timerange for all segments using this audio material
                    for track_name, track in script.tracks.items():
                        if track.track_type == draft.Track_type.audio:
                            for segment in track.segments:
                                if isinstance(segment, draft.Audio_segment) and segment.material_id == audio.material_id:
                                    # Get current settings
                                    current_target = segment.target_timerange
                                    current_source = segment.source_timerange
                                    speed = segment.speed.speed
                                    
                                    # If the end time of source_timerange exceeds the new audio duration, adjust it
                                    if current_source.end > audio.duration or current_source.end <= 0:
                                        # Adjust source_timerange to fit the new audio duration
                                        new_source_duration = audio.duration - current_source.start
                                        if new_source_duration <= 0:
                                            logger.warning(f"Warning: Audio segment {segment.segment_id} start time {current_source.start} exceeds audio duration {audio.duration}, will skip this segment.")
                                            continue
                                            
                                        # Update source_timerange
                                        segment.source_timerange = draft.Timerange(current_source.start, new_source_duration)
                                        
                                        # Update target_timerange based on new source_timerange and speed
                                        new_target_duration = int(new_source_duration / speed)
                                        segment.target_timerange = draft.Timerange(current_target.start, new_target_duration)
                                        
                                        logger.info(f"Adjusted audio segment {segment.segment_id} timerange to fit the new audio duration.")
                else:
                    logger.warning(f"Warning: Unable to get audio {material_name} duration: {duration_result['error']}.")
            except Exception as e:
                logger.error(f"Error occurred while getting audio {material_name} duration: {str(e)}", exc_info=True)
    
    # Process video and image file metadata
    videos = script.materials.videos
    if not videos:
        logger.info("No video or image files found in the draft.")
    else:
        for video in videos:
            remote_url = video.remote_url
            material_name = video.material_name
            if not remote_url:
                logger.warning(f"Warning: Media file {material_name} has no remote_url, skipped.")
                continue
                
            if video.material_type == 'photo':
                # Use imageio to get image width/height and set it
                try:
                    if task_id:
                        update_task_field(task_id, "message", f"Processing image metadata: {material_name}")
                    img = imageio.imread(remote_url)
                    video.height, video.width = img.shape[:2]
                    logger.info(f"Successfully set image {material_name} dimensions: {video.width}x{video.height}.")
                except Exception as e:
                    logger.error(f"Failed to set image {material_name} dimensions: {str(e)}, using default values 1920x1080.", exc_info=True)
                    video.width = 1920
                    video.height = 1080
            
            elif video.material_type == 'video':
                # Get video duration and width/height information
                try:
                    if task_id:
                        update_task_field(task_id, "message", f"Processing video metadata: {material_name}")
                    # Use ffprobe to get video information
                    command = [
                        'ffprobe',
                        '-v', 'error',
                        '-select_streams', 'v:0',  # Select the first video stream
                        '-show_entries', 'stream=width,height,duration',
                        '-show_entries', 'format=duration',
                        '-of', 'json',
                        remote_url
                    ]
                    result = subprocess.check_output(command, stderr=subprocess.STDOUT)
                    result_str = result.decode('utf-8')
                    # Find JSON start position (first '{')
                    json_start = result_str.find('{')
                    if json_start != -1:
                        json_str = result_str[json_start:]
                        info = json.loads(json_str)
                        
                        if 'streams' in info and len(info['streams']) > 0:
                            stream = info['streams'][0]
                            # Set width and height
                            video.width = int(stream.get('width', 0))
                            video.height = int(stream.get('height', 0))
                            logger.info(f"Successfully set video {material_name} dimensions: {video.width}x{video.height}.")
                            
                            # Set duration
                            # Prefer stream duration, if not available use format duration
                            duration = stream.get('duration') or info['format'].get('duration', '0')
                            video.duration = int(float(duration) * 1000000)  # Convert to microseconds
                            logger.info(f"Successfully obtained video {material_name} duration: {float(duration):.2f} seconds ({video.duration} microseconds).")
                            
                            # Update timerange for all segments using this video material
                            for track_name, track in script.tracks.items():
                                if track.track_type == draft.Track_type.video:
                                    for segment in track.segments:
                                        if isinstance(segment, draft.Video_segment) and segment.material_id == video.material_id:
                                            # Get current settings
                                            current_target = segment.target_timerange
                                            current_source = segment.source_timerange
                                            speed = segment.speed.speed

                                            # If the end time of source_timerange exceeds the new video duration, adjust it
                                            if current_source.end > video.duration or current_source.end <= 0:
                                                # Adjust source_timerange to fit the new video duration
                                                new_source_duration = video.duration - current_source.start
                                                if new_source_duration <= 0:
                                                    logger.warning(f"Warning: Video segment {segment.segment_id} start time {current_source.start} exceeds video duration {video.duration}, will skip this segment.")
                                                    continue
                                                    
                                                # Update source_timerange
                                                segment.source_timerange = draft.Timerange(current_source.start, new_source_duration)
                                                
                                                # Update target_timerange based on new source_timerange and speed
                                                new_target_duration = int(new_source_duration / speed)
                                                segment.target_timerange = draft.Timerange(current_target.start, new_target_duration)
                                                
                                                logger.info(f"Adjusted video segment {segment.segment_id} timerange to fit the new video duration.")
                        else:
                            logger.warning(f"Warning: Unable to get video {material_name} stream information.")
                            # Set default values
                            video.width = 1920
                            video.height = 1080
                    else:
                        logger.warning(f"Warning: Could not find JSON data in ffprobe output.")
                        # Set default values
                        video.width = 1920
                        video.height = 1080
                except Exception as e:
                    logger.error(f"Error occurred while getting video {material_name} information: {str(e)}, using default values 1920x1080.", exc_info=True)
                    # Set default values
                    video.width = 1920
                    video.height = 1080
                    
                    # Try to get duration separately
                    try:
                        duration_result = get_video_duration(remote_url)
                        if duration_result["success"]:
                            # Convert seconds to microseconds
                            video.duration = int(duration_result["output"] * 1000000)
                            logger.info(f"Successfully obtained video {material_name} duration: {duration_result['output']:.2f} seconds ({video.duration} microseconds).")
                        else:
                            logger.warning(f"Warning: Unable to get video {material_name} duration: {duration_result['error']}.")
                    except Exception as e2:
                        logger.error(f"Error occurred while getting video {material_name} duration: {str(e2)}.", exc_info=True)

    # After updating all segments' timerange, check if there are time range conflicts in each track, and delete the later segment in case of conflict
    logger.info("Checking track segment time range conflicts...")
    for track_name, track in script.tracks.items():
        # Use a set to record segment indices that need to be deleted
        to_remove = set()
        
        # Check for conflicts between all segments
        for i in range(len(track.segments)):
            # Skip if current segment is already marked for deletion
            if i in to_remove:
                continue
                
            for j in range(len(track.segments)):
                # Skip self-comparison and segments already marked for deletion
                if i == j or j in to_remove:
                    continue
                    
                # Check if there is a conflict
                if track.segments[i].overlaps(track.segments[j]):
                    # Always keep the segment with the smaller index (added first)
                    later_index = max(i, j)
                    logger.warning(f"Time range conflict between segments {track.segments[min(i, j)].segment_id} and {track.segments[later_index].segment_id} in track {track_name}, deleting the later segment")
                    to_remove.add(later_index)
        
        # Delete marked segments from back to front to avoid index change issues
        for index in sorted(to_remove, reverse=True):
            track.segments.pop(index)

    # After updating all segments' timerange, recalculate the total duration of the script
    max_duration = 0
    for track_name, track in script.tracks.items():
        for segment in track.segments:
            max_duration = max(max_duration, segment.end)
    script.duration = max_duration
    logger.info(f"Updated script total duration to: {script.duration} microseconds.")
    
    # Process all pending keyframes in tracks
    logger.info("Processing pending keyframes...")
    for track_name, track in script.tracks.items():
        if hasattr(track, 'pending_keyframes') and track.pending_keyframes:
            logger.info(f"Processing {len(track.pending_keyframes)} pending keyframes in track {track_name}...")
            track.process_pending_keyframes()
            logger.info(f"Pending keyframes in track {track_name} have been processed.")

def query_script_impl(draft_id: str, force_update: bool = True):
    """
    Query draft script object, with option to force refresh media metadata
    
    :param draft_id: Draft ID
    :param force_update: Whether to force refresh media metadata, default is True
    :return: Script object
    """
    # Get draft information from global cache
    if draft_id not in DRAFT_CACHE:
        logger.warning(f"Draft {draft_id} does not exist in cache.")
        return None
        
    script = DRAFT_CACHE[draft_id]
    logger.info(f"Retrieved draft {draft_id} from cache.")
    
    # If force_update is True, force refresh media metadata
    if force_update:
        logger.info(f"Force refreshing media metadata for draft {draft_id}.")
        update_media_metadata(script)
    
    # Return script object
    return script


def summarize_draft(
    draft_id: str,
    *,
    include_materials: bool = True,
    max_text_len: int = 120,
    force_update: bool = False,
) -> str:
    """Return a human-readable, API-level summary of the current draft state.

    The summary reflects the abstractions used by the Python API (tracks, segments,
    materials), while hiding low-level CapCut raw JSON details. Media are referenced
    by ids and human-friendly names, preferring remote URLs where appropriate.

    Args:
        draft_id: Target draft id in cache.
        include_materials: Whether to include a materials appendix.
        max_text_len: Truncate long text contents to this many characters.
        force_update: If True, refresh media metadata before summarizing.

    Returns:
        A multiline string summary.
    """
    # Fetch script from cache
    script = query_script_impl(draft_id, force_update=force_update)
    if script is None:
        return f"Draft '{draft_id}' not found in cache."

    # Helpers
    def us_to_s_str(us_value: Optional[int]) -> str:
        try:
            if us_value is None:
                return "0.000s"
            return f"{(us_value / 1_000_000.0):.3f}s"
        except Exception:
            return str(us_value)

    def fmt_timerange(tr: Optional['draft.Timerange']) -> str:
        if tr is None:
            return "n/a"
        return f"{us_to_s_str(tr.start)} – {us_to_s_str(tr.end)} (dur {us_to_s_str(tr.duration)})"

    def fmt_clip_settings(clip: Optional['draft.Clip_settings']) -> Optional[str]:
        if clip is None:
            return None
        # Only show when non-default to avoid noise
        non_default_bits: List[str] = []
        if abs(clip.alpha - 1.0) > 1e-6:
            non_default_bits.append(f"alpha={clip.alpha:.2f}")
        if clip.flip_horizontal:
            non_default_bits.append("flipH")
        if clip.flip_vertical:
            non_default_bits.append("flipV")
        if abs(clip.rotation) > 1e-6:
            non_default_bits.append(f"rot={clip.rotation:.1f}deg")
        if abs(clip.scale_x - 1.0) > 1e-6 or abs(clip.scale_y - 1.0) > 1e-6:
            non_default_bits.append(f"scale={clip.scale_x:.2f}x,{clip.scale_y:.2f}y")
        if abs(clip.transform_x) > 1e-6 or abs(clip.transform_y) > 1e-6:
            non_default_bits.append(f"pos=({clip.transform_x:.2f},{clip.transform_y:.2f})")
        return ", ".join(non_default_bits) if non_default_bits else None

    def indent(lines: List[str], level: int = 1) -> List[str]:
        prefix = "    " * level
        return [prefix + l for l in lines]

    lines: List[str] = []
    # Header
    lines.append(f"Draft {draft_id}")
    lines.append(f"- Canvas: {script.width}x{script.height} @ {script.fps}fps")
    lines.append(f"- Duration: {us_to_s_str(script.duration)}")

    # Tracks overview (sorted by render order, as exported)
    track_list: List['draft.Base_track'] = list(script.tracks.values())
    track_list.extend(getattr(script, 'imported_tracks', []))
    track_list.sort(key=lambda t: t.render_index)

    lines.append("Tracks:")
    if not track_list:
        lines.extend(indent(["(none)"]))
    else:
        for track in track_list:
            t_type = track.track_type.name
            t_name = track.name
            t_info = f"[{t_type}] '{t_name}' (render_index={track.render_index}, mute={'yes' if getattr(track, 'mute', False) else 'no'})"
            lines.extend(indent([t_info]))

            segs: List['draft.Base_segment'] = getattr(track, 'segments', [])
            if not segs:
                lines.extend(indent(["segments: (none)"], 2))
                continue

            for idx, seg in enumerate(segs):
                seg_header: str = f"#{idx+1}: "
                # Video/Image segment
                if isinstance(seg, draft.Video_segment):
                    material = seg.material_instance
                    m_kind = material.material_type
                    m_name = getattr(material, 'material_name', '')
                    ref = material.remote_url or material.path or ''
                    seg_header += f"VideoSegment {m_kind} id={material.material_id} name='{m_name}'"
                    lines.extend(indent([seg_header], 2))

                    details: List[str] = [
                        f"target={fmt_timerange(seg.target_timerange)}",
                        f"source={fmt_timerange(seg.source_timerange)}",
                        f"speed={getattr(seg.speed, 'speed', 1.0):.3f}, volume={seg.volume:.2f}",
                    ]
                    if material.width and material.height:
                        details.append(f"media_size={material.width}x{material.height}")
                    if ref:
                        details.append(f"ref={ref}")
                    clip_desc = fmt_clip_settings(seg.clip_settings)
                    if clip_desc:
                        details.append(f"clip[{clip_desc}]")
                    if seg.animations_instance is not None:
                        details.append("animations=present")
                    if seg.effects:
                        details.append("effects=" + ", ".join(e.name for e in seg.effects))
                    if seg.filters:
                        details.append("filters=" + ", ".join(f.effect_meta.name for f in seg.filters))
                    if seg.mask is not None:
                        details.append(f"mask={seg.mask.mask_meta.name}")
                    if seg.transition is not None:
                        details.append(f"transition={seg.transition.name}")
                    if seg.background_filling is not None:
                        details.append(f"background={seg.background_filling.fill_type}")
                    # Keyframes summary
                    if seg.common_keyframes:
                        kf_summ = ", ".join(
                            f"{kf_list.keyframe_property.name}:{len(kf_list.keyframes)}" for kf_list in seg.common_keyframes
                        )
                        details.append(f"keyframes=({kf_summ})")
                    lines.extend(indent(details, 3))

                # Audio segment
                elif isinstance(seg, draft.Audio_segment):
                    material = seg.material_instance
                    m_name = getattr(material, 'material_name', '')
                    ref = material.remote_url or material.path or ''
                    seg_header += f"AudioSegment id={material.material_id} name='{m_name}'"
                    lines.extend(indent([seg_header], 2))

                    details = [
                        f"target={fmt_timerange(seg.target_timerange)}",
                        f"source={fmt_timerange(seg.source_timerange)}",
                        f"speed={getattr(seg.speed, 'speed', 1.0):.3f}, volume={seg.volume:.2f}",
                        f"media_dur={us_to_s_str(material.duration)}",
                    ]
                    if ref:
                        details.append(f"ref={ref}")
                    if seg.fade is not None:
                        details.append(
                            f"fade=in {us_to_s_str(seg.fade.in_duration)}, out {us_to_s_str(seg.fade.out_duration)}"
                        )
                    if seg.effects:
                        details.append("effects=" + ", ".join(e.name for e in seg.effects))
                    # Keyframes summary
                    if seg.common_keyframes:
                        kf_summ = ", ".join(
                            f"{kf_list.keyframe_property.name}:{len(kf_list.keyframes)}" for kf_list in seg.common_keyframes
                        )
                        details.append(f"keyframes=({kf_summ})")
                    lines.extend(indent(details, 3))

                # Text segment
                elif isinstance(seg, draft.Text_segment):
                    text = seg.text.replace("\n", " ")
                    if len(text) > max_text_len:
                        text = text[:max_text_len - 1] + "…"
                    seg_header += f"TextSegment id={seg.material_id} text=\"{text}\""
                    lines.extend(indent([seg_header], 2))

                    details = [
                        f"target={fmt_timerange(seg.target_timerange)}",
                        f"font={(seg.font.name if getattr(seg, 'font', None) else 'system')} size={seg.style.size}",
                        f"align={seg.style.align} vertical={seg.style.vertical}",
                    ]
                    clip_desc = fmt_clip_settings(seg.clip_settings)
                    if clip_desc:
                        details.append(f"clip[{clip_desc}]")
                    if seg.bubble is not None:
                        details.append("bubble=present")
                    if seg.effect is not None:
                        details.append("text_effect=present")
                    if seg.background is not None:
                        details.append("background=present")
                    if seg.border is not None:
                        details.append("border=present")
                    if seg.shadow is not None and seg.shadow.has_shadow:
                        details.append("shadow=present")
                    if seg.common_keyframes:
                        kf_summ = ", ".join(
                            f"{kf_list.keyframe_property.name}:{len(kf_list.keyframes)}" for kf_list in seg.common_keyframes
                        )
                        details.append(f"keyframes=({kf_summ})")
                    lines.extend(indent(details, 3))

                # Imported text segment (from templates or cloned drafts)
                elif getattr(track, 'track_type', None) == draft.Track_type.text and hasattr(seg, 'material_id'):
                    # Try to resolve text content from imported or local materials by material_id
                    text_value = ""
                    try:
                        def _extract_text_from_mat(mat_obj):
                            content_field = mat_obj.get('content')
                            if isinstance(content_field, str):
                                try:
                                    parsed = json.loads(content_field)
                                    return parsed.get('text') if isinstance(parsed, dict) else None
                                except Exception:
                                    return content_field  # sometimes plain text
                            if isinstance(content_field, dict):
                                return content_field.get('text')
                            return None

                        # Search imported materials first
                        imported_txts = getattr(script, 'imported_materials', {}).get('texts', [])
                        for mat in imported_txts:
                            if mat.get('id') == getattr(seg, 'material_id', None):
                                tv = _extract_text_from_mat(mat)
                                if tv:
                                    text_value = tv
                                    break
                        # Fallback to local materials.texts
                        if not text_value:
                            local_txts = getattr(script.materials, 'texts', [])
                            for mat in local_txts:
                                if mat.get('id') == getattr(seg, 'material_id', None):
                                    tv = _extract_text_from_mat(mat)
                                    if tv:
                                        text_value = tv
                                        break
                    except Exception:
                        pass

                    if text_value:
                        text_flat = str(text_value).replace("\n", " ")
                        if len(text_flat) > max_text_len:
                            text_flat = text_flat[:max_text_len - 1] + "…"
                        seg_header += f"TextSegment id={getattr(seg, 'material_id', '')} text=\"{text_flat}\""
                    else:
                        seg_header += f"ImportedSegment material_id={getattr(seg, 'material_id', '')}"
                    lines.extend(indent([seg_header], 2))
                    tr = getattr(seg, 'target_timerange', None)
                    lines.extend(indent([f"target={fmt_timerange(tr)}"], 3))

                # Filter track segment
                elif isinstance(seg, draft.Filter_segment):
                    seg_header += f"Filter '{seg.material.effect_meta.name}'"
                    lines.extend(indent([seg_header], 2))
                    details = [f"target={fmt_timerange(seg.target_timerange)}", f"intensity={seg.material.intensity:.2f}"]
                    lines.extend(indent(details, 3))

                # Effect track segment
                elif isinstance(seg, draft.Effect_segment):
                    seg_header += f"Effect '{seg.effect_inst.name}'"
                    lines.extend(indent([seg_header], 2))
                    details = [f"target={fmt_timerange(seg.target_timerange)}", f"apply={'global' if seg.effect_inst.apply_target_type == 2 else 'clip'}"]
                    lines.extend(indent(details, 3))

                else:
                    # Imported or unknown segment: show minimal info
                    tr = getattr(seg, 'target_timerange', None)
                    seg_header += f"ImportedSegment material_id={getattr(seg, 'material_id', '')}"
                    lines.extend(indent([seg_header], 2))
                    lines.extend(indent([f"target={fmt_timerange(tr)}"], 3))

    # Materials appendix
    if include_materials:
        lines.append("Materials:")
        mats = getattr(script, 'materials', None)
        if mats is None:
            lines.extend(indent(["(none)"]))
        else:
            # Videos/Images
            vids = getattr(mats, 'videos', [])
            if vids:
                lines.extend(indent(["Videos/Images:"]))
                for v in vids:
                    ref = v.remote_url or v.path or ''
                    lines.extend(indent([
                        f"id={v.material_id} name='{v.material_name}' type={v.material_type} size={v.width}x{v.height} dur={us_to_s_str(v.duration)}",
                        f"ref={ref}" if ref else ""
                    ], 2))
            # Audios
            auds = getattr(mats, 'audios', [])
            if auds:
                lines.extend(indent(["Audios:"]))
                for a in auds:
                    ref = a.remote_url or a.path or ''
                    lines.extend(indent([
                        f"id={a.material_id} name='{a.material_name}' dur={us_to_s_str(a.duration)}",
                        f"ref={ref}" if ref else ""
                    ], 2))
            # Texts summary (count only; contents are shown per segment)
            txts = getattr(mats, 'texts', [])
            if txts:
                lines.extend(indent([f"Texts: {len(txts)} entries (see segments)"]))
            # Effects/filters counts
            if getattr(mats, 'video_effects', []):
                lines.extend(indent([f"Video effects: {len(mats.video_effects)}"]))
            if getattr(mats, 'filters', []):
                lines.extend(indent([f"Filters: {len(mats.filters)}"]))

    # Remove empty trailing lines
    lines = [l for l in lines if l.strip() != ""]
    return "\n".join(lines)

def download_script(draft_id: str, draft_folder: str = None, script_data: Dict = None) -> Dict[str, str]:
    """Downloads the draft script and its associated media assets.

    This function fetches the script object from a remote API,
    then iterates through its materials (audios, videos, images)
    to download them to the specified draft folder. It also updates
    task status and progress throughout the process.

    :param draft_id: The ID of the draft to download.
    :param draft_folder: The base folder where the draft's assets will be stored.
                         If None, assets will be stored directly under a folder named
                         after the draft_id in the current working directory.
    :return: A dictionary indicating success and, if successful, the URL where the draft
             would eventually be saved (though this function primarily focuses on download).
             If failed, it returns an error message.
    """

    logger.info(f"Starting to download draft: {draft_id} to folder: {draft_folder}")
    # Copy template to target directory
    template_path = os.path.join("./", 'template') if IS_CAPCUT_ENV else os.path.join("./", 'template_jianying')
    new_draft_path = os.path.join(draft_folder, draft_id)
    if os.path.exists(new_draft_path):
        logger.warning(f"Deleting existing draft target folder: {new_draft_path}")
        shutil.rmtree(new_draft_path)

    # Copy draft folder
    shutil.copytree(template_path, new_draft_path)
    
    try:
        # 1. Fetch the script from the remote endpoint
        if script_data is None:
            query_url = "https://cut-jianying-vdvswivepm.cn-hongkong.fcapp.run/query_script"
            headers = {"Content-Type": "application/json"}
            payload = {"draft_id": draft_id}

            logger.info(f"Attempting to get script for draft ID: {draft_id} from {query_url}.")
            response = requests.post(query_url, headers=headers, json=payload)
            response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
            
            script_data = json.loads(response.json().get('output'))
            logger.info(f"Successfully retrieved script data for draft {draft_id}.")
        else:
            logger.info(f"Using provided script_data, skipping remote retrieval.")

        # Collect download tasks
        download_tasks = []
        
        # Collect audio download tasks
        audios = script_data.get('materials',{}).get('audios',[])
        if audios:
            for audio in audios:
                remote_url = audio['remote_url']
                material_name = audio['name']
                # Use helper function to build path
                if draft_folder:
                    audio['path']=build_asset_path(draft_folder, draft_id, "audio", material_name)
                    logger.debug(f"Local path for audio {material_name}: {audio['path']}")
                if not remote_url:
                    logger.warning(f"Audio file {material_name} has no remote_url, skipping download.")
                    continue
                
                # Add audio download task
                download_tasks.append({
                    'type': 'audio',
                    'func': download_file,
                    'args': (remote_url, audio['path']),
                    'material': audio
                })
        
        # Collect video and image download tasks
        videos = script_data['materials']['videos']
        if videos:
            for video in videos:
                remote_url = video['remote_url']
                material_name = video['material_name']
                
                if video['type'] == 'photo':
                    # Use helper function to build path
                    if draft_folder:
                        video['path'] = build_asset_path(draft_folder, draft_id, "image", material_name)
                    if not remote_url:
                        logger.warning(f"Image file {material_name} has no remote_url, skipping download.")
                        continue
                    
                    # Add image download task
                    download_tasks.append({
                        'type': 'image',
                        'func': download_file,
                        'args': (remote_url, video['path']),
                        'material': video
                    })
                
                elif video['type'] == 'video':
                    # Use helper function to build path
                    if draft_folder:
                        video['path'] = build_asset_path(draft_folder, draft_id, "video", material_name)
                    if not remote_url:
                        logger.warning(f"Video file {material_name} has no remote_url, skipping download.")
                        continue
                    
                    # Add video download task
                    download_tasks.append({
                        'type': 'video',
                        'func': download_file,
                        'args': (remote_url, video['path']),
                        'material': video
                    })

        # Execute all download tasks concurrently
        downloaded_paths = []
        completed_files = 0
        if download_tasks:
            logger.info(f"Starting concurrent download of {len(download_tasks)} files...")
            
            # Use thread pool for concurrent downloads, maximum concurrency of 16
            with ThreadPoolExecutor(max_workers=16) as executor:
                # Submit all download tasks
                future_to_task = {
                    executor.submit(task['func'], *task['args']): task 
                    for task in download_tasks
                }
                
                # Wait for all tasks to complete
                for future in as_completed(future_to_task):
                    task = future_to_task[future]
                    try:
                        local_path = future.result()
                        downloaded_paths.append(local_path)
                        
                        # Update task status - only update completed files count
                        completed_files += 1
                        logger.info(f"Downloaded {completed_files}/{len(download_tasks)} files.")
                    except Exception as e:
                        logger.error(f"Failed to download {task['type']} file {task['args'][0]}: {str(e)}", exc_info=True)
                        logger.error("Download failed.")
                        # Continue processing other files, don't interrupt the entire process
            
            logger.info(f"Concurrent download completed, downloaded {len(downloaded_paths)} files in total.")
        
        """Write draft file content to file"""
        with open(f"{draft_folder}/{draft_id}/draft_info.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(script_data))
        logger.info(f"Draft has been saved.")

        # No draft_url for download, but return success
        return {"success": True, "message": f"Draft {draft_id} and its assets downloaded successfully"}

    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to fetch script from API: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error during download: {e}", exc_info=True)
        return {"success": False, "error": f"An unexpected error occurred: {str(e)}"}

if __name__ == "__main__":
    print('hello')
    download_script("dfd_cat_1751012163_a7e8c315",'/Users/sunguannan/Movies/JianyingPro/User Data/Projects/com.lveditor.draft')