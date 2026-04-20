import shutil
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

from archive_wechat_file import archive_files, archive_month


@contextmanager
def local_temp_dir():
    temp_root = Path.cwd() / ".test_tmp" / uuid.uuid4().hex
    temp_root.mkdir(parents=True)
    try:
        yield temp_root
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


class ArchiveWechatFileTests(unittest.TestCase):
    def test_duplicate_content_with_different_name_is_skipped(self):
        with local_temp_dir() as base:
            source_dir = base / "wechat" / "File"
            target_dir = base / "archive"
            source_dir.mkdir(parents=True)

            duplicate_source = source_dir / "different-name.txt"
            duplicate_source.write_text("same content", encoding="utf-8")

            month = archive_month(duplicate_source)
            target_month = target_dir / month
            target_month.mkdir(parents=True)
            (target_month / "already-archived.txt").write_text(
                "same content", encoding="utf-8"
            )

            summary = archive_files(
                base / "wechat", target_dir, dry_run=False, stable_seconds=0
            )

            self.assertEqual(summary["skipped_duplicate"], 1)
            self.assertFalse((target_month / "different-name.txt").exists())

    def test_same_name_different_content_is_copied_with_unique_name(self):
        with local_temp_dir() as base:
            source_dir = base / "wechat" / "File"
            target_dir = base / "archive"
            source_dir.mkdir(parents=True)

            source_file = source_dir / "report.final.txt"
            source_file.write_text("new content", encoding="utf-8")

            month = archive_month(source_file)
            target_month = target_dir / month
            target_month.mkdir(parents=True)
            (target_month / "report.final.txt").write_text(
                "old content", encoding="utf-8"
            )

            summary = archive_files(
                base / "wechat", target_dir, dry_run=False, stable_seconds=0
            )

            self.assertEqual(summary["renamed"], 1)
            archived_files = sorted(path.name for path in target_month.iterdir())
            self.assertEqual(len(archived_files), 2)
            self.assertIn("report.final.txt", archived_files)
            self.assertTrue(
                any(name.startswith("report.final_") for name in archived_files)
            )

    def test_dry_run_does_not_create_target_files(self):
        with local_temp_dir() as base:
            source_dir = base / "wechat" / "File"
            target_dir = base / "archive"
            source_dir.mkdir(parents=True)
            (source_dir / "message.txt").write_text("hello", encoding="utf-8")

            summary = archive_files(
                base / "wechat", target_dir, dry_run=True, stable_seconds=0
            )

            self.assertEqual(summary["copied"], 1)
            self.assertFalse(target_dir.exists())


if __name__ == "__main__":
    unittest.main()
