import CapCutAPI as cc

CC_DRAFT_FOLDER = "~/Movies/CapCut/User Data/Projects/com.lveditor.draft"

import os, shutil, CapCutAPI as cc

# 1) Create (or reuse) a draft, then add edits...
script, draft_id = cc.create_draft(width=1080, height=1920)
cc.add_text(text="Hello", start=0, end=3, draft_id=draft_id, font_size=8.0, font_color="#FFFFFF", width=1080, height=1920)

# Print summary
print(cc.summarize_draft(draft_id))

# 2) Save: writes to repo_dir/<draft_id>; draft_folder only sets replace paths
capcut_drafts = os.path.expanduser(CC_DRAFT_FOLDER)
cc.save_draft(draft_id, draft_folder=capcut_drafts)

# 3) Copy the saved folder into CapCut’s drafts directory
repo_dir = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(repo_dir, draft_id)
dst = os.path.join(capcut_drafts, draft_id)
print("Saved at:", src)
if os.path.exists(dst): shutil.rmtree(dst)
shutil.copytree(src, dst)
print("Copied to:", dst)