#!/usr/bin/env python3
"""Test script to verify improved SegmentOverlap error message"""

import CapCutAPI as cc
import traceback

def test_overlap_error():
    """Test the improved overlap error message"""
    print("Testing improved SegmentOverlap error message...")

    try:
        # Create a draft
        script, draft_id = cc.create_draft(width=1080, height=1920)
        print(f"Created draft: {draft_id}")

        # Add first video segment
        cc.add_video(
            video_url="https://example.com/video1.mp4",
            start=0,
            end=5,
            draft_id=draft_id
        )
        print("Added first video segment [0-5s]")

        # Try to add overlapping video segment - this should trigger the improved error
        cc.add_video(
            video_url="https://example.com/video2.mp4",
            start=3,  # Overlaps with first segment (0-5)
            end=8,
            draft_id=draft_id
        )
        print("ERROR: Should have raised SegmentOverlap exception!")

    except Exception as e:
        if "overlaps with existing segment" in str(e):
            print("✅ Caught improved SegmentOverlap error:")
            print(f"   {e}")
            return True
        else:
            print(f"❌ Caught different error: {e}")
            traceback.print_exc()
            return False

    return False

if __name__ == "__main__":
    success = test_overlap_error()
    print(f"\nTest {'PASSED' if success else 'FAILED'}")
