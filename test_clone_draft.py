import os
import sys
import CapCutAPI as cc

# Minimal smoke test for clone_draft using a user-provided draft name
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_clone_draft.py <source_draft_name>")
        print(
            "<source_draft_name> is the folder name that exists under your CapCut/JianYing projects directory."
        )
        sys.exit(2)

    source_draft_name = sys.argv[1]

    # Clone from the real CapCut/JianYing drafts directory (default inside clone_draft)
    script, draft_id = cc.clone_draft(source_draft_name)

    # Basic sanity checks that the clone exists in this repository and is well-formed
    repo_root = os.path.dirname(os.path.abspath(__file__))
    cloned_path = os.path.join(repo_root, draft_id)
    assert os.path.isdir(cloned_path), "Cloned draft directory not found"
    assert os.path.isfile(os.path.join(cloned_path, "draft_info.json")), "Cloned draft missing draft_info.json"

    print(draft_id)
