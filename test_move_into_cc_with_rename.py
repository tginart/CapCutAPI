import sys
import time

import CapCutAPI as cc


def pick_cached_draft_id() -> str:
    entries = cc.list_drafts()
    cached = [e for e in entries if e.get("type") == "cached draft"]
    if not cached:
        raise RuntimeError("No cached drafts found. Create/save a draft first.")
    return cached[0]["draft_id"]


def main() -> int:
    try:
        source_id = pick_cached_draft_id()
        new_name = f"test_move_into_cc_{int(time.time())}"

        print(f"Source cached draft: {source_id}")
        print(f"New draft name:      {new_name}")
        print(f"CapCut projects dir: {cc.CAPCUT_PROJECT_DIR}")

        _, new_id = cc.copy_draft(source_id, new_draft_id=new_name)
        print(f"Copied draft to new id: {new_id}")

        dst = cc.move_into_capcut(new_id, overwrite=True)
        print("Moved into CapCut at:", dst)
        print("Open CapCut and confirm the project appears with the new name.")
        return 0
    except Exception as exc:
        print("Error:", str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())


