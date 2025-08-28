import shutil
import subprocess
import json
import re
import os
import hashlib
import functools
import time
from settings.local import DRAFT_DOMAIN, PREVIEW_ROUTER, IS_CAPCUT_ENV, DRAFT_CACHE_DIR, set_draft_cache_dir
# save_draft_impl is imported lazily inside move_into_capcut to avoid circular imports

def hex_to_rgb(hex_color: str) -> tuple:
    """Convert hexadecimal color code to RGB tuple (range 0.0-1.0)"""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join([c*2 for c in hex_color])  # Handle shorthand form (e.g. #fff)
    try:
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return (r, g, b)
    except ValueError:
        raise ValueError(f"Invalid hexadecimal color code: {hex_color}")


def is_windows_path(path):
    """Detect if the path is Windows style"""
    # Check if it starts with a drive letter (e.g. C:\) or contains Windows style separators
    return re.match(r'^[a-zA-Z]:\\|\\\\', path) is not None


def zip_draft(draft_id):
    # Compress folder under configured cache dir
    zip_dir = os.path.join(DRAFT_CACHE_DIR, "tmp/zip")
    os.makedirs(zip_dir, exist_ok=True)
    zip_path = os.path.join(zip_dir, f"{draft_id}.zip")
    shutil.make_archive(os.path.join(zip_dir, draft_id), 'zip', os.path.join(DRAFT_CACHE_DIR, draft_id))
    return zip_path

def url_to_hash(url, length=16):
    """
    Convert URL to a fixed-length hash string (without extension)
    
    Parameters:
    - url: Original URL string
    - length: Length of the hash string (maximum 64, default 16)
    
    Returns:
    - Hash string (e.g.: 3a7f9e7d9a1b4e2d)
    """
    # Ensure URL is bytes type
    url_bytes = url.encode('utf-8')
    
    # Use SHA-256 to generate hash (secure and highly unique)
    hash_object = hashlib.sha256(url_bytes)
    
    # Truncate to specified length of hexadecimal string
    return hash_object.hexdigest()[:length]


def timing_decorator(func_name):
    """Decorator: Used to monitor function execution time"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            print(f"[{func_name}] Starting execution...")
            try:
                result = func(*args, **kwargs)
                end_time = time.time()
                duration = end_time - start_time
                print(f"[{func_name}] Execution completed, time taken: {duration:.3f} seconds")
                return result
            except Exception as e:
                end_time = time.time()
                duration = end_time - start_time
                print(f"[{func_name}] Execution failed, time taken: {duration:.3f} seconds, error: {e}")
                raise
        return wrapper
    return decorator

def generate_draft_url(draft_id):
    return f"{DRAFT_DOMAIN}{PREVIEW_ROUTER}?draft_id={draft_id}&is_capcut={1 if IS_CAPCUT_ENV else 0}"


def move_into_capcut(draft_id: str, overwrite: bool = True) -> str:
    """Publish a draft into CapCut's drafts directory using save_draft logic.

    This ensures material paths are written correctly by delegating to
    save_draft_impl with the CapCut projects directory as the target.

    Arguments:
        draft_id: The draft id to move
        overwrite: If True, allow replacing an existing destination folder

    Returns:
        str: The destination path in CapCut's drafts directory

    Raises:
        FileNotFoundError: If the draft does not exist in cache
        FileExistsError: If destination exists and overwrite is False
        RuntimeError: If saving fails
    """
    from CapCutAPI import CAPCUT_PROJECT_DIR
    from save_draft_impl import save_draft_impl

    # Validate source exists in cache dir
    src_path = os.path.join(DRAFT_CACHE_DIR, draft_id)
    if not os.path.isdir(src_path):
        raise FileNotFoundError(f"Source draft folder not found: {src_path}")

    # Destination handling
    os.makedirs(CAPCUT_PROJECT_DIR, exist_ok=True)
    dst_path = os.path.join(CAPCUT_PROJECT_DIR, draft_id)
    if os.path.exists(dst_path) and not overwrite:
        raise FileExistsError(f"Destination already exists: {dst_path}")

    # Use official save pathing to emit correct replace_path values and files
    result = save_draft_impl(draft_id, draft_folder=CAPCUT_PROJECT_DIR)
    if not isinstance(result, dict) or not result.get("success"):
        raise RuntimeError(f"Failed to move draft into CapCut: {result}")

    # Final sanity check
    if not os.path.isdir(dst_path):
        raise RuntimeError(f"Draft was not created at expected location: {dst_path}")

    return dst_path