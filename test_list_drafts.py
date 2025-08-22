import CapCutAPI as cc

if __name__ == "__main__":
    drafts = cc.list_drafts()
    for d in drafts:
        print(f"{d['draft_id']}\t{d['type']}")
