import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import weekly_job as job

DATE = "2026-10-05"
OLD = "2026-09-14"
RECORDS = [{"r": "ID", "cat": "gaming", "sh": i, "id": str(i)} for i in range(5)]

def insights(target=DATE):
    return {"date": target, "all": {"gaming": "fixture", "all": "fixture"},
            "ID": {"gaming": "fixture", "all": "fixture"}, "summary": "fixture"}

def archive(root, target=DATE, analysis=True, records=None):
    path = root / target
    path.mkdir(parents=True, exist_ok=True)
    (path / "combined.json").write_text(json.dumps(RECORDS if records is None else records), encoding="utf-8")
    (path / "covers").mkdir(exist_ok=True)
    (path / "covers" / "cover.jpg").write_bytes(b"cover-fixture")
    if analysis:
        (path / "insights.json").write_text(json.dumps(insights(target)), encoding="utf-8")
    return path

def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}

class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root / "data"
        archive(self.data)
        (self.data / "dates.json").write_text(json.dumps([DATE]), encoding="utf-8")
        self.patch = patch.object(job, "DATA_DIR", self.data)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def test_missing_files_block_publication(self):
        for name in ("combined.json", "insights.json"):
            path = self.data / DATE / name
            saved = path.read_bytes()
            path.unlink()
            with self.assertRaisesRegex(ValueError, DATE):
                job.validate_publication()
            path.write_bytes(saved)

    def test_incomplete_empty_malformed_and_wrong_date_are_rejected(self):
        path = self.data / DATE / "insights.json"
        samples = ["not json", "null", "[]"]
        for value in ("", "   ", None, 1):
            bad = insights()
            bad["ID"]["gaming"] = value
            samples.append(json.dumps(bad))
        bad = insights(OLD)
        samples.append(json.dumps(bad))
        bad = insights()
        bad.pop("summary")
        samples.append(json.dumps(bad))
        for text in samples:
            path.write_text(text, encoding="utf-8")
            with self.subTest(text=text), self.assertRaises(ValueError):
                job.validate_publication()

    def test_threshold_and_regions_follow_archive(self):
        small = RECORDS[:4] + [{"r": "global", "cat": "global_trending"}]
        value = {"date": DATE, "all": {"all": "fixture"}, "ID": {"all": "fixture"},
                 "global": {"all": "fixture"}, "summary": "fixture"}
        job.validate_insights(small, value, DATE)
        value.pop("global")
        with self.assertRaisesRegex(ValueError, "global/all"):
            job.validate_insights(small, value, DATE)

    def test_failed_generation_keeps_existing_report_and_history(self):
        before = snapshot(self.data)
        with patch.object(job, "_llm_call", side_effect=["fixture", RuntimeError("model failed")]):
            with self.assertRaisesRegex(RuntimeError, "model failed"):
                job.generate_insights(RECORDS, DATE)
        self.assertEqual(before, snapshot(self.data))

    def test_empty_model_result_is_not_published(self):
        before = snapshot(self.data)
        with patch.object(job, "_llm_call", return_value=""):
            with self.assertRaises(ValueError):
                job.generate_insights(RECORDS, DATE)
        self.assertEqual(before, snapshot(self.data))

    def test_atomic_replace_failure_preserves_report_and_removes_temp(self):
        before = snapshot(self.data)
        with patch.object(job, "_llm_call", return_value="fixture"), patch.object(job.os, "replace", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                job.generate_insights(RECORDS, DATE)
        self.assertEqual(before, snapshot(self.data))

    def test_backfill_is_idempotent_and_preserves_all_other_files(self):
        archive(self.data, OLD)
        (self.data / "dates.json").write_text(json.dumps([DATE, OLD]), encoding="utf-8")
        (self.data / DATE / "insights.json").unlink()
        before = snapshot(self.data)
        with patch.object(job, "_llm_call", return_value="fixture") as llm, \
             patch.object(job, "run_scrape") as scrape, patch.object(job, "cleanup_old_data") as prune, \
             patch.object(job, "notify_dingtalk") as notify, patch.object(job, "deploy_pages") as deploy:
            job.backfill_insights([DATE, DATE, OLD])
            self.assertEqual(llm.call_count, 5)
            after = snapshot(self.data)
            job.backfill_insights()
            self.assertEqual(llm.call_count, 5)
            self.assertEqual(after, snapshot(self.data))
            for mock in (scrape, prune, notify, deploy):
                mock.assert_not_called()
        self.assertEqual(before, {k: v for k, v in after.items() if k != f"{DATE}/insights.json"})

    def test_backfill_continues_after_one_week_fails_and_returns_failure(self):
        archive(self.data, OLD, analysis=False)
        (self.data / "dates.json").write_text(json.dumps([DATE, OLD]), encoding="utf-8")
        (self.data / DATE / "insights.json").unlink()
        with patch.object(job, "_llm_call", side_effect=[RuntimeError("offline")] + ["fixture"] * 5):
            with self.assertRaisesRegex(RuntimeError, DATE):
                job.backfill_insights()
        self.assertFalse((self.data / DATE / "insights.json").exists())
        self.assertTrue((self.data / OLD / "insights.json").exists())

    def test_missing_archive_and_unlisted_date_do_not_generate(self):
        (self.data / DATE / "combined.json").unlink()
        with patch.object(job, "generate_insights") as generate:
            with self.assertRaises(RuntimeError):
                job.backfill_insights([DATE])
            with self.assertRaises(ValueError):
                job.backfill_insights(["../../unexpected"])
            generate.assert_not_called()

    def test_backfill_deploy_retains_more_than_five_published_weeks(self):
        published = self.root / "published"
        old_dates = ["2026-09-28", "2026-09-21", OLD, "2026-09-07", "2026-08-31", "2026-08-24"]
        for target in old_dates:
            archive(published, target)
        (published / "dates.json").write_text(json.dumps(old_dates), encoding="utf-8")
        before = snapshot(published)
        local_before = snapshot(self.data)
        job.stage_publication(published, retain_history=True)
        for path, content in before.items():
            if path != "dates.json":
                self.assertEqual(content, (published / path).read_bytes())
        self.assertEqual(len(job._read_dates(published)), 7)
        self.assertEqual(local_before, snapshot(self.data))
        job.validate_publication(published)

    def test_regular_retention_only_prunes_staging_after_validation(self):
        published = self.root / "published"
        dates = ["2026-09-28", "2026-09-21", OLD, "2026-09-07", "2026-08-31"]
        for target in dates:
            archive(published, target)
        (published / "dates.json").write_text(json.dumps(dates), encoding="utf-8")
        before = snapshot(self.data)
        job.stage_publication(published)
        self.assertEqual(len(job._read_dates(published)), job.MAX_WEEKS)
        self.assertFalse((published / "2026-08-31").exists())
        self.assertEqual(before, snapshot(self.data))

    def test_invalid_published_history_blocks_pruning(self):
        published = self.root / "published"
        archive(published, OLD, analysis=False)
        (published / "dates.json").write_text(json.dumps([OLD]), encoding="utf-8")
        with patch.object(job, "cleanup_old_data") as prune:
            with self.assertRaisesRegex(ValueError, OLD):
                job.stage_publication(published)
            prune.assert_not_called()

    def test_deploy_validation_failure_never_pushes(self):
        stage = self.root / "_site"
        archive(stage / "data", OLD, analysis=False)
        (stage / "data" / "dates.json").write_text(json.dumps([OLD]), encoding="utf-8")
        def run(cmd, **kwargs):
            if cmd[:3] == ["git", "config", "remote.origin.url"]:
                return subprocess.CompletedProcess(cmd, 0, stdout="repo\n")
            if cmd[:2] == ["git", "clone"]:
                return subprocess.CompletedProcess(cmd, 0)
            self.fail(f"Unexpected git operation: {cmd}")
        with patch.object(job, "SITE_DIR", stage), patch.object(job.shutil, "rmtree"), \
             patch.object(job.subprocess, "run", side_effect=run), patch.object(job, "_git_push") as push:
            with self.assertRaises(ValueError):
                job.deploy_pages()
            push.assert_not_called()

    def test_clone_failure_refuses_to_replace_remote(self):
        stage = self.root / "_site"
        with patch.object(job, "SITE_DIR", stage), \
             patch.object(job.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, stdout="", stderr="offline")), \
             patch.object(job, "_git_push") as push:
            with self.assertRaisesRegex(RuntimeError, "published history"):
                job.deploy_pages()
            push.assert_not_called()

    def test_cli_archive_commands_do_not_require_tikhub_token(self):
        with patch.object(job, "API_TOKEN", ""), patch.object(sys, "argv", ["weekly_job.py", "validate"]):
            job.main()
        with patch.object(job, "API_TOKEN", ""), patch.object(sys, "argv", ["weekly_job.py", "backfill"]):
            job.main()

    def test_monday_generation_failure_stops_deployment_and_notification(self):
        with patch.object(job, "run_scrape"), patch.object(job, "get_monday_date", return_value=job.date.fromisoformat(DATE)), \
             patch.dict(sys.modules, {"translate_data": type("FakeTranslation", (), {"translate_file": staticmethod(lambda _: None)})}), \
             patch.object(job, "generate_insights", side_effect=RuntimeError("offline")), \
             patch.object(job, "deploy_pages") as deploy, patch.object(job, "sync_main") as sync, \
             patch.object(job, "notify_dingtalk") as notify:
            with self.assertRaises(RuntimeError):
                job.run_monday()
            for mock in (deploy, sync, notify):
                mock.assert_not_called()

if __name__ == "__main__":
    unittest.main()
