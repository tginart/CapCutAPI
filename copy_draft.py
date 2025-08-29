import os
import shutil
import time
import uuid
from typing import Optional, Tuple

import pyJianYingDraft as draft

from draft_cache import update_cache
from settings.local import DRAFT_CACHE_DIR


def copy_draft(source_draft_id: str, *, new_draft_id: Optional[str] = None) -> Tuple['draft.Script_file', str]:
    """Copy an existing draft within the cache to create a new draft.

    Creates a copy of the draft folder `<DRAFT_CACHE_DIR>/<source_draft_id>` under
    a new `draft_id`, loads the `draft_info.json` in template mode, updates the
    in-memory cache, and returns the `(script, new_draft_id)`.

    Args:
        source_draft_id: The draft id of the existing draft to copy.
        new_draft_id: Optional custom draft id for the copy. If omitted, a unique
            id will be auto-generated.

    Returns:
        (script, new_draft_id)

    Raises:
        FileNotFoundError: When the source draft folder does not exist in the cache.
    """
    # Ensure cache directory exists
    os.makedirs(DRAFT_CACHE_DIR, exist_ok=True)

    # Validate source draft exists
    source_path = os.path.join(DRAFT_CACHE_DIR, source_draft_id)
    if not os.path.isdir(source_path):
        raise FileNotFoundError(f"Source draft folder not found: {source_path}")

    # Generate new draft_id if not provided
    if new_draft_id is None:
        new_draft_id = f"dfd_cat_{int(time.time())}_{uuid.uuid4().hex[:8]}"

    # Destination path
    dest_path = os.path.join(DRAFT_CACHE_DIR, new_draft_id)

    # Check if destination already exists
    if os.path.exists(dest_path):
        raise FileExistsError(f"Destination draft folder already exists: {dest_path}")

    # Copy the entire draft folder
    shutil.copytree(source_path, dest_path)

    # Load the copied draft in template mode and cache it
    script = draft.Script_file.load_template(os.path.join(dest_path, "draft_info.json"))
    update_cache(new_draft_id, script)

    return script, new_draft_id
