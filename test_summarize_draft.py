import CapCutAPI as cc

# Minimal smoke test for summarize_draft
if __name__ == "__main__":
    script, draft_id = cc.create_draft(width=1080, height=1920)
    # Add a simple text to make the timeline non-empty
    cc.add_text(text="Hello world", start=0, end=2, draft_id=draft_id, font_size=8.0, font_color="#FFFFFF", width=1080, height=1920)
    print(cc.summarize_draft(draft_id))
