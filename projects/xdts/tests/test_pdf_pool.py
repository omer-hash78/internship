from __future__ import annotations

import sys
import shutil
import unittest
import uuid
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools import generate_pdf_pool


class PdfPoolGeneratorTests(unittest.TestCase):
    def test_wrap_labeled_text_preserves_label_and_wraps_follow_on_lines(self) -> None:
        value = (
            "Initial issue formalizing post-flight engine-bay temperature capture "
            "and cooldown comparison after armed loiter recovery."
        )
        wrapped = generate_pdf_pool.wrap_labeled_text(
            "Revision Note:",
            value,
            52,
        )
        self.assertGreater(len(wrapped), 1)
        self.assertTrue(wrapped[0].startswith("Revision Note: "))
        self.assertFalse(wrapped[1].startswith("Revision Note: "))
        self.assertEqual(
            " ".join([wrapped[0].removeprefix("Revision Note: ")] + wrapped[1:]),
            value,
        )

    def test_rendered_preflight_document_uses_controlled_header(self) -> None:
        spec = generate_pdf_pool.collect_document_specs()[
            "AV_FL_NAV_CL_1001_Preflight_Checklist_R000_2026_04_10.pdf"
        ]
        test_root = PROJECT_ROOT / ".test-work" / "pdf-pool-tests"
        test_root.mkdir(parents=True, exist_ok=True)
        temp_dir = test_root / uuid.uuid4().hex
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            output_path = temp_dir / spec.filename
            generate_pdf_pool.render_document(spec, output_path)
            content = output_path.read_bytes().decode("latin-1", "ignore")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        self.assertIn("FLIGHT RELEASE CHECKLIST", content)
        self.assertIn("XDTS CONTROLLED TECHNICAL DATA", content)
        self.assertIn("Flight Release Control Table", content)
        self.assertNotIn("Language Profile", content)
        self.assertNotIn("XDTS SAMPLE AVIATION DOCUMENT", content)

    def test_rendered_long_document_code_wraps_in_header(self) -> None:
        spec = generate_pdf_pool.collect_document_specs()[
            "SA_EN_TMP_RP_1007_Engine_Temperature_Log_R000_2026_04_15.pdf"
        ]
        test_root = PROJECT_ROOT / ".test-work" / "pdf-pool-tests"
        test_root.mkdir(parents=True, exist_ok=True)
        temp_dir = test_root / uuid.uuid4().hex
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            output_path = temp_dir / spec.filename
            generate_pdf_pool.render_document(spec, output_path)
            content = output_path.read_bytes().decode("latin-1", "ignore")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        doc_code_match = re.search(
            r"1 0 0 1 58\.00 ([0-9]+\.[0-9]+) Tm \(Document Code: SA_EN_TMP_RP_1007_Engine_Temperature_Log\)",
            content,
        )
        revision_match = re.search(
            r"1 0 0 1 58\.00 ([0-9]+\.[0-9]+) Tm \(Revision: R000\)",
            content,
        )
        self.assertIsNotNone(doc_code_match)
        self.assertIsNotNone(revision_match)
        self.assertGreater(float(doc_code_match.group(1)), float(revision_match.group(1)))

    def test_rendered_turkish_document_uses_unicode_font_path(self) -> None:
        spec = generate_pdf_pool.collect_document_specs()[
            "QA_EL_PWR_PL_1004_Avionics_Parts_List_R000_2026_04_08.pdf"
        ]
        test_root = PROJECT_ROOT / ".test-work" / "pdf-pool-tests"
        test_root.mkdir(parents=True, exist_ok=True)
        temp_dir = test_root / uuid.uuid4().hex
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            output_path = temp_dir / spec.filename
            generate_pdf_pool.render_document(spec, output_path)
            content = output_path.read_bytes().decode("latin-1", "ignore")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        self.assertIn("/FontFile2", content)
        self.assertIn("/ToUnicode", content)

    def test_resolve_filenames_restricts_generation_to_requested_file(self) -> None:
        manifest = [
            "AV_FL_NAV_CL_1001_Preflight_Checklist_R000_2026_04_10.pdf",
            "SA_FL_INS_RP_1003_Safety_Inspection_Report_R000_2026_04_11.pdf",
        ]
        resolved = generate_pdf_pool.resolve_filenames(
            manifest,
            "AV_FL_NAV_CL_1001_Preflight_Checklist_R000_2026_04_10.pdf",
        )
        self.assertEqual(
            resolved,
            ["AV_FL_NAV_CL_1001_Preflight_Checklist_R000_2026_04_10.pdf"],
        )

    def test_resolve_filenames_rejects_unknown_filename(self) -> None:
        with self.assertRaises(SystemExit):
            generate_pdf_pool.resolve_filenames(["known.pdf"], "unknown.pdf")


if __name__ == "__main__":
    unittest.main()
