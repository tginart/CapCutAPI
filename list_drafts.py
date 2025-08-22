import os
from typing import List, Optional, TypedDict

from draft_cache import DRAFT_CACHE
from clone_draft import _default_drafts_root


class DraftEntry(TypedDict):
    """A single draft listing entry.

    Attributes:
        draft_id: The folder name or cache key identifying the draft.
        type: Either "cached draft" (in-memory) or "project draft" (real CapCut/JianYing dir).
    """

    draft_id: str
    type: str


def _list_cached_drafts() -> List[DraftEntry]:
    """Return all draft ids currently present in the in-memory cache."""
    results: List[DraftEntry] = []
    for draft_id in list(DRAFT_CACHE.keys()):
        results.append({"draft_id": draft_id, "type": "cached draft"})
    return results


def _list_project_drafts(source_root: Optional[str]) -> List[DraftEntry]:
    """Return all draft folder names under the CapCut/JianYing projects directory.

    A draft is recognized as any directory containing a `draft_info.json` file.
    """
    drafts_root = os.path.expanduser(source_root) if source_root else _default_drafts_root()
    if not os.path.isdir(drafts_root):
        return []

    entries: List[DraftEntry] = []
    try:
        for name in os.listdir(drafts_root):
            full_path = os.path.join(drafts_root, name)
            if not os.path.isdir(full_path):
                continue
            if not os.path.isfile(os.path.join(full_path, "draft_info.json")):
                continue
            entries.append({"draft_id": name, "type": "project draft"})
    except OSError:
        # If the directory cannot be read, return what we have (likely empty)
        return []

    return entries


def list_drafts(*, source_root: Optional[str] = None) -> List[DraftEntry]:
    """List drafts from both the in-memory cache and the real project directory.

    Args:
        source_root: Optional absolute path to the CapCut/JianYing drafts root. If omitted,
            a sensible OS-specific default is used (based on environment settings).

    Returns:
        A list of dicts, each with keys:
          - "draft_id": The draft identifier (folder name or cache key)
          - "type": "cached draft" or "project draft"

        Duplicates may appear if a draft exists in both places.
    """
    results: List[DraftEntry] = []
    results.extend(_list_cached_drafts())
    results.extend(_list_project_drafts(source_root))
    return results
