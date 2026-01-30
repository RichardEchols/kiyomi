"""Tests for cleanup module."""

import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_cleanup_old_memory_files():
    """Test that only dated memory files older than threshold are removed."""
    from cleanup import cleanup_old_memory_files, MEMORY_RETENTION_DAYS

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create files with different ages
        old_file = tmppath / "2025-11-01.md"
        old_file.write_text("old memory")

        recent_file = tmppath / (datetime.now().strftime("%Y-%m-%d") + ".md")
        recent_file.write_text("today memory")

        # Non-dated file should be ignored
        other_file = tmppath / "MEMORY.md"
        other_file.write_text("long-term memory")

        # Patch MEMORY_DIR
        with patch("cleanup.MEMORY_DIR", tmppath):
            # Make old file actually old
            import os
            old_time = (datetime.now() - timedelta(days=MEMORY_RETENTION_DAYS + 5)).timestamp()
            os.utime(old_file, (old_time, old_time))

            # Dry run should not delete
            removed = cleanup_old_memory_files(dry_run=True)
            assert len(removed) == 1
            assert old_file.exists()  # Still there

            # Real run should delete
            removed = cleanup_old_memory_files(dry_run=False)
            assert len(removed) == 1
            assert not old_file.exists()
            assert other_file.exists()  # Long-term memory untouched


def test_truncate_cost_log():
    """Test cost log truncation keeps recent entries."""
    from cleanup import truncate_cost_log, COST_LOG_RETENTION_DAYS

    with tempfile.TemporaryDirectory() as tmpdir:
        cost_file = Path(tmpdir) / "cost_log.json"

        # Create entries
        old_date = (datetime.now() - timedelta(days=COST_LOG_RETENTION_DAYS + 10)).isoformat()
        recent_date = datetime.now().isoformat()

        data = [
            {"timestamp": old_date, "cost": 0.50},
            {"timestamp": old_date, "cost": 0.25},
            {"timestamp": recent_date, "cost": 1.00},
        ]
        cost_file.write_text(json.dumps(data))

        with patch("cleanup.BASE_DIR", Path(tmpdir)):
            removed = truncate_cost_log(dry_run=False)
            assert removed == 2

            # Verify remaining data
            remaining = json.loads(cost_file.read_text())
            assert len(remaining) == 1
            assert remaining[0]["cost"] == 1.00


def test_format_cleanup_report():
    """Test report formatting."""
    from cleanup import format_cleanup_report

    results = {
        "timestamp": "2026-01-29T03:00:00",
        "dry_run": False,
        "memory_files_removed": ["2025-11-01.md", "2025-11-02.md"],
        "swarm_logs_removed": [],
        "temp_files_removed": ["screenshot_123.png"],
        "cost_entries_trimmed": 5,
        "empty_dirs_removed": [],
        "total_items_cleaned": 8,
    }

    report = format_cleanup_report(results)
    assert "Memory files" in report
    assert "2 removed" in report
    assert "Temp files" in report
    assert "1 removed" in report
    assert "5 trimmed" in report


def test_cleanup_nothing_to_do():
    """Test cleanup with empty/nonexistent directories."""
    from cleanup import run_full_cleanup

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        with patch("cleanup.MEMORY_DIR", tmppath / "nonexistent_memory"), \
             patch("cleanup.SWARM_LOGS_DIR", tmppath / "nonexistent_swarm"), \
             patch("cleanup.TEMP_DIR", tmppath / "nonexistent_temp"), \
             patch("cleanup.BASE_DIR", tmppath), \
             patch("cleanup.LOGS_DIR", tmppath / "nonexistent_logs"):
            results = run_full_cleanup(dry_run=False)
            assert results["total_items_cleaned"] == 0


if __name__ == "__main__":
    test_cleanup_old_memory_files()
    print("PASS: test_cleanup_old_memory_files")

    test_truncate_cost_log()
    print("PASS: test_truncate_cost_log")

    test_format_cleanup_report()
    print("PASS: test_format_cleanup_report")

    test_cleanup_nothing_to_do()
    print("PASS: test_cleanup_nothing_to_do")

    print("\nAll cleanup tests passed!")
