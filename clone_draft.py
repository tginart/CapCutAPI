import os
import shutil
import time
import uuid
from typing import Optional, Tuple

import pyJianYingDraft as draft

from draft_cache import update_cache
from settings import IS_CAPCUT_ENV
from settings.local import DRAFT_CACHE_DIR


def _default_drafts_root() -> str:
    """Return the default CapCut/JianYing drafts root for the current OS.

    macOS/Linux (POSIX):
      - CapCut:     ~/Movies/CapCut/User Data/Projects/com.lveditor.draft
      - JianYing:   ~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft
    Windows:
      - CapCut:     %USERPROFILE%/Documents/CapCut/User Data/Projects/com.lveditor.draft
      - JianYing:   %USERPROFILE%/Documents/JianyingPro/User Data/Projects/com.lveditor.draft
    """
    if os.name == "nt":
        base = os.path.join(os.path.expanduser("~"), "Documents")
        app_dir = "CapCut" if IS_CAPCUT_ENV else "JianyingPro"
        return os.path.join(base, app_dir, "User Data", "Projects", "com.lveditor.draft")
    else:
        app_dir = "CapCut" if IS_CAPCUT_ENV else "JianyingPro"
        return os.path.expanduser(os.path.join("~", "Movies", app_dir, "User Data", "Projects", "com.lveditor.draft"))


def clone_draft(source_draft_name: str, *, source_root: Optional[str] = None) -> Tuple['draft.Script_file', str]:
    """Clone an existing CapCut/JianYing draft folder without modifying the original.

    Copies the folder `<source_root>/<source_draft_name>` into the draft cache directory
    under a newly generated `draft_id`, loads the `draft_info.json` in template mode,
    updates the in-memory cache, and returns the `(script, draft_id)`.

    Args:
        source_draft_name: Folder name of the draft inside the real CapCut/JianYing drafts directory.
        source_root: Optional absolute path to the drafts root. If omitted, a sensible OS-specific
            default is used based on `IS_CAPCUT_ENV`.

    Returns:
        (script, draft_id)

    Raises:
        FileNotFoundError: When the source root or draft folder does not exist.
    """
    drafts_root = os.path.expanduser(source_root) if source_root else _default_drafts_root()
    if not os.path.isdir(drafts_root):
        raise FileNotFoundError(f"Drafts root not found: {drafts_root}")

    source_path = os.path.join(drafts_root, source_draft_name)
    if not os.path.isdir(source_path):
        raise FileNotFoundError(f"Source draft folder not found: {source_path}")

    # Destination inside the draft cache directory
    os.makedirs(DRAFT_CACHE_DIR, exist_ok=True)
    draft_id = f"dfd_cat_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    dest_path = os.path.join(DRAFT_CACHE_DIR, draft_id)

    shutil.copytree(source_path, dest_path)

    # Load the copied draft in template mode and cache it
    script = draft.Script_file.load_template(os.path.join(dest_path, "draft_info.json"))
    update_cache(draft_id, script)

    return script, draft_id
