import os
import tempfile
import textwrap
import json
import CapCutAPI as cc
from settings import set_draft_cache_dir, DRAFT_CACHE_DIR


def build_yaml_content() -> str:
    """Return a minimal but comprehensive YAML that exercises:
    - top-level draft config
    - assets resolution ($assets.*)
    - defaults merging
    - single-key step mapping and explicit `op` style
    - multiple add_text steps (no external downloads)
    """
    return textwrap.dedent(
        """
        draft:
          width: 1080
          height: 1920

        assets:
          greeting: "Hello from YAML assets!"

        defaults:
          track_name: text_main
          font_size: 10.0

        steps:
          - add_text:
              text: $assets.greeting
              start: 0
              end: 2
              transform_y: -0.3

          - add_text:
              text: "Second line overrides font_size"
              start: 2
              end: 4
              font_size: 12.0

          - op: add_text
            text: "Third via explicit op style"
            start: 4
            end: 6
        """
    ).strip() + "\n"


def main() -> None:
    # Ensure we operate from the project root (directory of this file)
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)

    # Configure a local cachespace directory under the repo (can override via env)
    default_cache = os.path.join(project_root, "draft_cachespace_dir")
    set_draft_cache_dir(default_cache)
    os.makedirs(default_cache, exist_ok=True)

    # Create a temp YAML config; draft will be saved locally under project_root
    with tempfile.TemporaryDirectory() as tmp_dir:
        yaml_path = os.path.join(tmp_dir, "test_config.yaml")
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(build_yaml_content())

        print("Parsing YAML:", yaml_path)
        result = cc.parse_yaml_config(yaml_path)

        # Basic assertions to ensure parse routine executed steps and returned identifiers
        if not isinstance(result, dict):
            raise AssertionError(f"Expected dict result, got: {type(result).__name__}")
        if not result.get("draft_id"):
            raise AssertionError("parse_yaml_config did not return a draft_id")

        draft_id = result["draft_id"]
        draft_url = result.get("draft_url")
        print("Draft ID:", draft_id)
        if draft_url:
            print("Draft URL:", draft_url)

        # Save the draft locally (under <DRAFT_CACHE_DIR>/<draft_id>)
        cc.save_draft(draft_id)

        saved_path = os.path.join(default_cache, draft_id)
        print("Saved local draft folder:", saved_path)
        if not os.path.isdir(saved_path):
            raise FileNotFoundError(f"Expected saved draft at {saved_path}")

        # Show a shallow listing of the top-level saved draft folder
        try:
            top_level = sorted(os.listdir(saved_path))
        except Exception as e:
            top_level = [f"<error listing contents: {e}>"]
        print("Top-level contents:", json.dumps(top_level, indent=2))

        # Optional: show a brief summary
        try:
            summary = cc.summarize_draft(draft_id)
            print("\nSummary:\n" + summary)
        except Exception:
            pass

        print("SUCCESS: YAML parse and local save completed.")


if __name__ == "__main__":
    main()
