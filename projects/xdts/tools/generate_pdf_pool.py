from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


PAGE_WIDTH = 595
PAGE_HEIGHT = 842
LEFT_MARGIN = 48
RIGHT_MARGIN = 48
TOP_MARGIN = 54
BOTTOM_MARGIN = 54


def escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def chunk_text(text: str, max_chars: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


class PDFPage:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def add(self, command: str) -> None:
        self.commands.append(command)

    def render(self) -> str:
        return "\n".join(self.commands) + "\n"


class PDFCanvas:
    def __init__(self) -> None:
        self.pages: list[PDFPage] = [PDFPage()]
        self.current_page = self.pages[0]
        self.cursor_y = PAGE_HEIGHT - TOP_MARGIN

    def new_page(self) -> None:
        self.current_page = PDFPage()
        self.pages.append(self.current_page)
        self.cursor_y = PAGE_HEIGHT - TOP_MARGIN

    def ensure_space(self, height: float) -> None:
        if self.cursor_y - height < BOTTOM_MARGIN:
            self.new_page()

    def text_line(self, x: float, y: float, text: str, *, font: str = "F1", size: int = 10) -> None:
        escaped = escape_pdf_text(text)
        self.current_page.add(f"BT /{font} {size} Tf 1 0 0 1 {x:.2f} {y:.2f} Tm ({escaped}) Tj ET")

    def paragraph(
        self,
        text: str,
        *,
        font: str = "F1",
        size: int = 10,
        leading: int = 14,
        x: float = LEFT_MARGIN,
        width: float | None = None,
        gap_after: int = 10,
    ) -> None:
        content_width = width if width is not None else PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN
        max_chars = max(20, int(content_width / (size * 0.55)))
        lines = chunk_text(text, max_chars)
        block_height = max(leading, len(lines) * leading)
        self.ensure_space(block_height + gap_after)
        y = self.cursor_y
        for line in lines:
            self.text_line(x, y, line, font=font, size=size)
            y -= leading
        self.cursor_y = y - gap_after

    def heading(self, text: str, *, size: int = 12, gap_after: int = 8) -> None:
        self.ensure_space(size + gap_after + 4)
        self.text_line(LEFT_MARGIN, self.cursor_y, text, font="F2", size=size)
        self.cursor_y -= size + gap_after

    def rule(self, *, gap_before: int = 4, gap_after: int = 10) -> None:
        self.ensure_space(gap_before + gap_after + 2)
        y = self.cursor_y - gap_before
        self.current_page.add(f"{LEFT_MARGIN:.2f} {y:.2f} m {PAGE_WIDTH - RIGHT_MARGIN:.2f} {y:.2f} l S")
        self.cursor_y = y - gap_after

    def header_block(
        self,
        *,
        doc_code: str,
        title: str,
        revision: str,
        date_text: str,
        language: str,
        english_title: str | None,
        revision_note: str,
    ) -> None:
        self.ensure_space(140)
        self.current_page.add("0.15 0.15 0.15 RG")
        self.current_page.add(f"{LEFT_MARGIN:.2f} {self.cursor_y - 6:.2f} {PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN:.2f} 98 re S")
        self.current_page.add("0 0 0 RG")
        self.text_line(LEFT_MARGIN + 10, self.cursor_y + 14, "XDTS SAMPLE AVIATION DOCUMENT", font="F2", size=9)
        self.text_line(LEFT_MARGIN + 10, self.cursor_y - 6, title, font="F2", size=18)
        self.text_line(LEFT_MARGIN + 10, self.cursor_y - 26, f"Document Code: {doc_code}", font="F1", size=10)
        self.text_line(LEFT_MARGIN + 10, self.cursor_y - 40, f"Revision: {revision}", font="F1", size=10)
        self.text_line(LEFT_MARGIN + 160, self.cursor_y - 40, f"Effective Date: {date_text}", font="F1", size=10)
        profile = "English-dominant" if language == "en" else "Turkish-dominant"
        self.text_line(LEFT_MARGIN + 10, self.cursor_y - 54, f"Language Profile: {profile}", font="F1", size=10)
        if english_title:
            self.text_line(LEFT_MARGIN + 10, self.cursor_y - 68, f"Reference Title: {english_title}", font="F1", size=10)
        self.text_line(LEFT_MARGIN + 10, self.cursor_y - 82, f"Revision Note: {revision_note}", font="F1", size=10)
        self.cursor_y -= 120
        self.rule(gap_before=0, gap_after=8)

    def draw_table(self, headers: list[str], rows: list[list[str]], *, title: str) -> None:
        row_height = 24
        col_count = len(headers)
        table_width = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN
        col_width = table_width / col_count
        table_height = row_height * (len(rows) + 1)
        self.ensure_space(table_height + 42)
        self.heading(title, size=12, gap_after=4)
        top = self.cursor_y
        self.current_page.add(f"{LEFT_MARGIN:.2f} {top - table_height:.2f} {table_width:.2f} {table_height:.2f} re S")
        for index in range(1, len(rows) + 1):
            y = top - (index * row_height)
            self.current_page.add(f"{LEFT_MARGIN:.2f} {y:.2f} m {LEFT_MARGIN + table_width:.2f} {y:.2f} l S")
        for index in range(1, col_count):
            x = LEFT_MARGIN + (index * col_width)
            self.current_page.add(f"{x:.2f} {top:.2f} m {x:.2f} {top - table_height:.2f} l S")

        y = top - 16
        for col_index, header in enumerate(headers):
            self.text_line(LEFT_MARGIN + 6 + (col_index * col_width), y, header, font="F2", size=9)

        for row_index, row in enumerate(rows):
            cell_y = top - ((row_index + 1) * row_height) - 16
            for col_index, value in enumerate(row):
                wrapped = chunk_text(value, max(8, int((col_width - 10) / 5.2)))[:2]
                for wrapped_index, line in enumerate(wrapped):
                    self.text_line(LEFT_MARGIN + 6 + (col_index * col_width), cell_y - (wrapped_index * 9), line, font="F1", size=8)
        self.cursor_y = top - table_height - 16

    def draw_labeled_box(self, x: float, y: float, width: float, height: float, label: str) -> None:
        self.current_page.add(f"{x:.2f} {y:.2f} {width:.2f} {height:.2f} re S")
        self.text_line(x + 6, y + (height / 2) - 3, label, font="F1", size=9)

    def draw_arrow(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self.current_page.add(f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")
        self.current_page.add(f"{x2:.2f} {y2:.2f} m {x2 - 6:.2f} {y2 + 3:.2f} l S")
        self.current_page.add(f"{x2:.2f} {y2:.2f} m {x2 - 6:.2f} {y2 - 3:.2f} l S")

    def draw_diagram(self, *, title: str, kind: str, caption: str) -> None:
        diagram_height = 200
        self.ensure_space(diagram_height + 40)
        self.heading(title, size=12, gap_after=4)
        base_y = self.cursor_y - 20

        if kind == "uav_preflight":
            self.current_page.add(f"{LEFT_MARGIN + 30:.2f} {base_y:.2f} m {LEFT_MARGIN + 160:.2f} {base_y:.2f} l S")
            self.current_page.add(f"{LEFT_MARGIN + 160:.2f} {base_y:.2f} m {LEFT_MARGIN + 200:.2f} {base_y + 10:.2f} l S")
            self.current_page.add(f"{LEFT_MARGIN + 160:.2f} {base_y:.2f} m {LEFT_MARGIN + 200:.2f} {base_y - 10:.2f} l S")
            self.current_page.add(f"{LEFT_MARGIN + 90:.2f} {base_y + 2:.2f} m {LEFT_MARGIN + 90:.2f} {base_y + 52:.2f} l S")
            self.current_page.add(f"{LEFT_MARGIN + 60:.2f} {base_y + 26:.2f} m {LEFT_MARGIN + 120:.2f} {base_y + 26:.2f} l S")
            self.current_page.add(f"{LEFT_MARGIN + 54:.2f} {base_y - 16:.2f} m {LEFT_MARGIN + 74:.2f} {base_y - 16:.2f} l S")
            self.current_page.add(f"{LEFT_MARGIN + 106:.2f} {base_y - 16:.2f} m {LEFT_MARGIN + 126:.2f} {base_y - 16:.2f} l S")
            self.text_line(LEFT_MARGIN + 208, base_y + 4, "Nose / EO-IR", size=9)
            self.text_line(LEFT_MARGIN + 96, base_y + 58, "SATCOM fairing", size=9)
            self.text_line(LEFT_MARGIN + 34, base_y - 26, "Weapon station L", size=9)
            self.text_line(LEFT_MARGIN + 108, base_y - 26, "Weapon station R", size=9)
        elif kind == "engine_flow":
            self.draw_labeled_box(LEFT_MARGIN + 10, base_y - 20, 86, 28, "Wing Tank")
            self.draw_labeled_box(LEFT_MARGIN + 128, base_y - 20, 86, 28, "Filter Pack")
            self.draw_labeled_box(LEFT_MARGIN + 246, base_y - 20, 92, 28, "Fuel Metering")
            self.draw_labeled_box(LEFT_MARGIN + 370, base_y - 20, 92, 28, "Engine Core")
            self.draw_arrow(LEFT_MARGIN + 96, base_y - 6, LEFT_MARGIN + 128, base_y - 6)
            self.draw_arrow(LEFT_MARGIN + 214, base_y - 6, LEFT_MARGIN + 246, base_y - 6)
            self.draw_arrow(LEFT_MARGIN + 338, base_y - 6, LEFT_MARGIN + 370, base_y - 6)
            self.text_line(LEFT_MARGIN + 20, base_y - 56, "Drain sample", size=9)
            self.text_line(LEFT_MARGIN + 148, base_y - 56, "Delta-P check", size=9)
            self.text_line(LEFT_MARGIN + 268, base_y - 56, "Prime and purge", size=9)
            self.text_line(LEFT_MARGIN + 394, base_y - 56, "Idle stabilization", size=9)
        elif kind == "safety_arc":
            self.current_page.add(f"{LEFT_MARGIN + 180:.2f} {base_y - 12:.2f} 78 78 re S")
            self.text_line(LEFT_MARGIN + 200, base_y + 26, "UCAV", font="F2", size=10)
            self.current_page.add(f"{LEFT_MARGIN + 60:.2f} {base_y - 80:.2f} m {LEFT_MARGIN + 300:.2f} {base_y - 80:.2f} l S")
            self.text_line(LEFT_MARGIN + 64, base_y - 96, "Safe line", size=9)
            self.current_page.add(f"{LEFT_MARGIN + 220:.2f} {base_y + 80:.2f} m {LEFT_MARGIN + 320:.2f} {base_y + 120:.2f} l S")
            self.text_line(LEFT_MARGIN + 326, base_y + 118, "Weapon clear arc", size=9)
            self.current_page.add(f"{LEFT_MARGIN + 80:.2f} {base_y + 20:.2f} m {LEFT_MARGIN + 20:.2f} {base_y + 90:.2f} l S")
            self.text_line(LEFT_MARGIN - 6, base_y + 94, "Ground crew lane", size=9)
        elif kind == "power_block":
            self.draw_labeled_box(LEFT_MARGIN + 20, base_y - 10, 90, 30, "28V Bus")
            self.draw_labeled_box(LEFT_MARGIN + 160, base_y + 30, 94, 30, "Mission Computer")
            self.draw_labeled_box(LEFT_MARGIN + 160, base_y - 20, 94, 30, "EO-IR Payload")
            self.draw_labeled_box(LEFT_MARGIN + 160, base_y - 70, 94, 30, "Datalink Radio")
            self.draw_labeled_box(LEFT_MARGIN + 304, base_y - 20, 110, 30, "Relay / Breaker Pack")
            self.draw_arrow(LEFT_MARGIN + 110, base_y + 5, LEFT_MARGIN + 160, base_y + 45)
            self.draw_arrow(LEFT_MARGIN + 110, base_y + 5, LEFT_MARGIN + 160, base_y - 5)
            self.draw_arrow(LEFT_MARGIN + 110, base_y + 5, LEFT_MARGIN + 160, base_y - 55)
            self.draw_arrow(LEFT_MARGIN + 254, base_y - 5, LEFT_MARGIN + 304, base_y - 5)
        elif kind == "hydraulic_loop":
            self.draw_labeled_box(LEFT_MARGIN + 20, base_y - 10, 86, 28, "Reservoir")
            self.draw_labeled_box(LEFT_MARGIN + 146, base_y - 10, 86, 28, "Pump")
            self.draw_labeled_box(LEFT_MARGIN + 272, base_y - 10, 86, 28, "Actuator Manifold")
            self.draw_labeled_box(LEFT_MARGIN + 398, base_y - 10, 86, 28, "Flap / Gear Act.")
            self.draw_arrow(LEFT_MARGIN + 106, base_y + 4, LEFT_MARGIN + 146, base_y + 4)
            self.draw_arrow(LEFT_MARGIN + 232, base_y + 4, LEFT_MARGIN + 272, base_y + 4)
            self.draw_arrow(LEFT_MARGIN + 358, base_y + 4, LEFT_MARGIN + 398, base_y + 4)
            self.current_page.add(f"{LEFT_MARGIN + 398:.2f} {base_y - 44:.2f} m {LEFT_MARGIN + 20:.2f} {base_y - 44:.2f} l S")
            self.current_page.add(f"{LEFT_MARGIN + 20:.2f} {base_y - 44:.2f} m {LEFT_MARGIN + 20:.2f} {base_y - 10:.2f} l S")
            self.text_line(LEFT_MARGIN + 210, base_y - 58, "Return line to reservoir", size=9)
        elif kind == "landing_gear":
            self.current_page.add(f"{LEFT_MARGIN + 70:.2f} {base_y + 70:.2f} m {LEFT_MARGIN + 230:.2f} {base_y + 70:.2f} l S")
            self.current_page.add(f"{LEFT_MARGIN + 150:.2f} {base_y + 70:.2f} m {LEFT_MARGIN + 150:.2f} {base_y + 10:.2f} l S")
            self.current_page.add(f"{LEFT_MARGIN + 150:.2f} {base_y + 10:.2f} m {LEFT_MARGIN + 120:.2f} {base_y - 40:.2f} l S")
            self.current_page.add(f"{LEFT_MARGIN + 150:.2f} {base_y + 10:.2f} m {LEFT_MARGIN + 180:.2f} {base_y - 40:.2f} l S")
            self.current_page.add(f"{LEFT_MARGIN + 120:.2f} {base_y - 40:.2f} 16 16 re S")
            self.current_page.add(f"{LEFT_MARGIN + 180:.2f} {base_y - 40:.2f} 16 16 re S")
            self.text_line(LEFT_MARGIN + 244, base_y + 68, "Main beam", size=9)
            self.text_line(LEFT_MARGIN + 188, base_y + 16, "Strut", size=9)
            self.text_line(LEFT_MARGIN + 198, base_y - 42, "Wheel", size=9)
        elif kind == "temperature_map":
            self.current_page.add(f"{LEFT_MARGIN + 120:.2f} {base_y - 10:.2f} 170 80 re S")
            self.text_line(LEFT_MARGIN + 176, base_y + 26, "Engine Bay", font="F2", size=10)
            for label, dx, dy in [("T1", 18, 46), ("T2", 86, 52), ("T3", 136, 38), ("T4", 30, 14), ("T5", 120, 12)]:
                self.current_page.add(f"{LEFT_MARGIN + 120 + dx:.2f} {base_y + dy - 10:.2f} 10 10 re S")
                self.text_line(LEFT_MARGIN + 120 + dx + 14, base_y + dy - 4, label, size=9)
            self.text_line(LEFT_MARGIN + 120, base_y - 34, "Sensors monitor exhaust spread after armed loiter recovery.", size=9)
        elif kind == "comms_chain":
            self.draw_labeled_box(LEFT_MARGIN + 16, base_y - 10, 100, 30, "Pilot Console")
            self.draw_labeled_box(LEFT_MARGIN + 156, base_y - 10, 100, 30, "Mission Console")
            self.draw_labeled_box(LEFT_MARGIN + 296, base_y - 10, 100, 30, "Relay / SATCOM")
            self.draw_labeled_box(LEFT_MARGIN + 436, base_y - 10, 90, 30, "UCAV Link")
            self.draw_arrow(LEFT_MARGIN + 116, base_y + 5, LEFT_MARGIN + 156, base_y + 5)
            self.draw_arrow(LEFT_MARGIN + 256, base_y + 5, LEFT_MARGIN + 296, base_y + 5)
            self.draw_arrow(LEFT_MARGIN + 396, base_y + 5, LEFT_MARGIN + 436, base_y + 5)
            self.text_line(LEFT_MARGIN + 40, base_y - 44, "Voice test", size=9)
            self.text_line(LEFT_MARGIN + 176, base_y - 44, "Target handover", size=9)
            self.text_line(LEFT_MARGIN + 314, base_y - 44, "Latency check", size=9)
            self.text_line(LEFT_MARGIN + 452, base_y - 44, "Ack return", size=9)

        self.text_line(LEFT_MARGIN, base_y - 98, f"Figure 1. {caption}", font="F1", size=9)
        self.cursor_y = base_y - 118

    def footer(self) -> None:
        for index, page in enumerate(self.pages, start=1):
            page.add(f"BT /F1 8 Tf 1 0 0 1 {LEFT_MARGIN:.2f} 24.00 Tm (Page {index} of {len(self.pages)}) Tj ET")


def build_pdf(page_contents: list[str]) -> bytes:
    objects: list[bytes] = []
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique >>")

    stream_ids: list[int] = []
    for content in page_contents:
        stream_data = content.encode("latin-1", "replace")
        stream = f"<< /Length {len(stream_data)} >>\nstream\n".encode("ascii") + stream_data + b"endstream"
        objects.append(stream)
        stream_ids.append(len(objects))

    page_ids: list[int] = []
    pages_id = 3 + len(page_contents) + len(page_contents) + 1
    for stream_id in stream_ids:
        page_obj = (
            f"<< /Type /Page /Parent {pages_id} 0 R "
            f"/MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 1 0 R /F2 2 0 R /F3 3 0 R >> >> "
            f"/Contents {stream_id} 0 R >>"
        ).encode("ascii")
        objects.append(page_obj)
        page_ids.append(len(objects))

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects.append(f"<< /Type /Pages /Count {len(page_ids)} /Kids [{kids}] >>".encode("ascii"))
    catalog_id = len(objects) + 1
    objects.append(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("ascii"))

    buffer = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(buffer))
        buffer.extend(f"{index} 0 obj\n".encode("ascii"))
        buffer.extend(obj)
        buffer.extend(b"\nendobj\n")

    xref_start = len(buffer)
    buffer.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    buffer.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        buffer.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    trailer = f"trailer << /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref_start}\n%%EOF\n"
    buffer.extend(trailer.encode("ascii"))
    return bytes(buffer)


@dataclass(frozen=True)
class DocumentSpec:
    filename: str
    language: str
    visible_title: str
    english_title: str | None
    revision_note: str
    summary: str
    paragraph_one: str
    paragraph_two: str
    table_title: str
    table_headers: list[str]
    table_rows: list[list[str]]
    diagram_title: str
    diagram_kind: str
    diagram_caption: str


def render_document(spec: DocumentSpec, output_path: Path) -> None:
    doc_code = spec.filename.replace(".pdf", "").rsplit("_R", 1)[0]
    revision = spec.filename.split("_")[-4]
    date_text = spec.filename.replace(".pdf", "").split("_")[-3:]
    date_display = "-".join(date_text)

    canvas = PDFCanvas()
    canvas.header_block(
        doc_code=doc_code,
        title=spec.visible_title,
        revision=revision,
        date_text=date_display,
        language=spec.language,
        english_title=spec.english_title,
        revision_note=spec.revision_note,
    )
    canvas.heading("Summary", size=12, gap_after=6)
    canvas.paragraph(spec.summary, font="F1", size=10, leading=14, gap_after=8)
    canvas.heading("Operational Context", size=12, gap_after=6)
    canvas.paragraph(spec.paragraph_one, font="F1", size=10, leading=14, gap_after=8)
    canvas.paragraph(spec.paragraph_two, font="F1", size=10, leading=14, gap_after=10)
    canvas.draw_table(spec.table_headers, spec.table_rows, title=spec.table_title)
    canvas.draw_diagram(title=spec.diagram_title, kind=spec.diagram_kind, caption=spec.diagram_caption)
    canvas.footer()

    output_path.write_bytes(build_pdf([page.render() for page in canvas.pages]))


def english_documents() -> dict[str, DocumentSpec]:
    return {
        "AV_FL_NAV_CL_1001_Preflight_Checklist_R000_2026_04_10.pdf": DocumentSpec(
            filename="AV_FL_NAV_CL_1001_Preflight_Checklist_R000_2026_04_10.pdf",
            language="en",
            visible_title="Preflight Checklist",
            english_title=None,
            revision_note="Baseline release for armed UAV taxi, datalink, and weapon-safe inspection.",
            summary="This checklist governs the preflight release of a medium-altitude armed unmanned aircraft before sunrise launch from a dispersed operating strip. The intent is to confirm flight safety, payload restraint status, and link readiness using a repeatable line sequence.",
            paragraph_one="Ground crew must complete the walk-around with aircraft power off, intake blanks removed, and both external hardpoints safed. Any moisture, abrasion, or missing witness marks around the EO-IR turret, SATCOM fairing, or wing root panels shall be logged before engine start authority is requested.",
            paragraph_two="After battery-on, the launch supervisor verifies inertial alignment, encrypted datalink registration, and control-surface response. The aircraft remains in a weapon-safe state until the mission console receives positive stores inhibit telemetry and a matching mission load sheet from armament control.",
            table_title="Line Inspection Table",
            table_headers=["Step", "Inspection Point", "Standard", "Action"],
            table_rows=[
                ["1", "Nose / EO-IR dome", "No cracks, no salt film", "Clean and log"],
                ["2", "Wing stations", "Pins installed, covers secure", "Verify safe state"],
                ["3", "Main tires", "Pressure band visible", "Record serviceable"],
                ["4", "Datalink antenna", "No looseness or dents", "Sign release"],
            ],
            diagram_title="Inspection Diagram",
            diagram_kind="uav_preflight",
            diagram_caption="Primary preflight inspection points on the armed UAV outer mold line.",
        ),
        "AV_FL_NAV_CL_1001_Preflight_Checklist_R001_2026_04_14.pdf": DocumentSpec(
            filename="AV_FL_NAV_CL_1001_Preflight_Checklist_R001_2026_04_14.pdf",
            language="en",
            visible_title="Preflight Checklist",
            english_title=None,
            revision_note="Added EO-IR contamination check and thermal cover release step after desert trial findings.",
            summary="This revision updates the preflight release flow for armed UAV launch after dusty taxi trials. The sequence now emphasizes payload optics cleanliness and cover removal confirmation before the aircraft is handed to the pilot console.",
            paragraph_one="Ground crew must complete the walk-around with aircraft power off, intake blanks removed, and both external hardpoints safed. Any dust bloom, abrasion, or missing witness marks around the EO-IR turret, SATCOM fairing, or wing root panels shall be logged before engine start authority is requested.",
            paragraph_two="After battery-on, the launch supervisor verifies inertial alignment, encrypted datalink registration, and control-surface response. The aircraft remains in a weapon-safe state until the mission console receives positive stores inhibit telemetry, confirms turret lens clarity, and verifies removal of all thermal transport covers.",
            table_title="Line Inspection Table",
            table_headers=["Step", "Inspection Point", "Standard", "Action"],
            table_rows=[
                ["1", "Nose / EO-IR dome", "No cracks, no dust haze", "Clean and photograph"],
                ["2", "Wing stations", "Pins installed, covers secure", "Verify safe state"],
                ["3", "Thermal transport covers", "All removed and tagged", "Cross-check inventory"],
                ["4", "Datalink antenna", "No looseness or dents", "Sign release"],
            ],
            diagram_title="Inspection Diagram",
            diagram_kind="uav_preflight",
            diagram_caption="Updated preflight inspection points with optics and cover-control emphasis.",
        ),
        "AV_FL_NAV_CL_1001_Preflight_Checklist_R002_2026_04_17.pdf": DocumentSpec(
            filename="AV_FL_NAV_CL_1001_Preflight_Checklist_R002_2026_04_17.pdf",
            language="en",
            visible_title="Preflight Checklist",
            english_title=None,
            revision_note="Added SATCOM witness-mark verification and stores consent line for network-enabled sortie release.",
            summary="This revision aligns the preflight checklist with the current armed UAV release standard for long-range network relay sorties. The line now includes an explicit witness-mark review on the SATCOM fairing and a stores consent confirmation before taxi release.",
            paragraph_one="Ground crew must complete the walk-around with aircraft power off, intake blanks removed, and both external hardpoints safed. Any dust bloom, abrasion, or broken torque witness marks around the EO-IR turret, SATCOM fairing, or wing root panels shall be logged before engine start authority is requested.",
            paragraph_two="After battery-on, the launch supervisor verifies inertial alignment, encrypted datalink registration, control-surface response, and stores inhibit telemetry. Taxi authority is withheld until the mission console records a valid network relay health status and the armament officer signs the release consent line for the uploaded mission package.",
            table_title="Line Inspection Table",
            table_headers=["Step", "Inspection Point", "Standard", "Action"],
            table_rows=[
                ["1", "Nose / EO-IR dome", "No cracks, no dust haze", "Clean and photograph"],
                ["2", "SATCOM fairing", "Witness marks aligned", "Log torque seal status"],
                ["3", "Stores consent", "Signed by armament officer", "Attach sortie packet"],
                ["4", "Datalink antenna", "No looseness or dents", "Sign release"],
            ],
            diagram_title="Inspection Diagram",
            diagram_kind="uav_preflight",
            diagram_caption="Final preflight release checkpoints for a network-enabled armed UAV sortie.",
        ),
        "SA_FL_INS_RP_1003_Safety_Inspection_Report_R000_2026_04_11.pdf": DocumentSpec(
            filename="SA_FL_INS_RP_1003_Safety_Inspection_Report_R000_2026_04_11.pdf",
            language="en",
            visible_title="Safety Inspection Report",
            english_title=None,
            revision_note="Initial issue documenting apron safety findings after armed UAV turnaround rehearsal.",
            summary="This report records a controlled safety inspection carried out during an armed UAV turnaround rehearsal. The objective was to verify personnel spacing, propeller exclusion boundaries, and weapon-safe handling discipline during refuel and re-task operations.",
            paragraph_one="The inspection team observed compliant use of wheel chocks, fire bottles, and communication headsets across the launch element. The main concern involved inconsistent marking of the ground crew lane behind the left wing, which created avoidable congestion during simulated stores loading.",
            paragraph_two="A secondary finding noted that the visual safe line was partially obscured by temporary tool cases when the aircraft was repositioned. The report recommends repainting the lane edge and installing two foldable warning boards to keep the arc clear during night preparations.",
            table_title="Observed Safety Findings",
            table_headers=["Item", "Condition", "Risk", "Disposition"],
            table_rows=[
                ["A1", "Crew lane partially narrow", "Medium", "Repaint boundary"],
                ["A2", "Fire bottle placement correct", "Low", "Accept"],
                ["A3", "Safe line obscured by cases", "Medium", "Add warning boards"],
                ["A4", "Weapon-safe tag visible", "Low", "Accept"],
            ],
            diagram_title="Safety Layout Sketch",
            diagram_kind="safety_arc",
            diagram_caption="Ground crew lane, safe line, and weapon clear arc around the armed UAV stand.",
        ),
        "MT_HY_ACT_CL_1005_Hydraulic_System_Checklist_R000_2026_04_12.pdf": DocumentSpec(
            filename="MT_HY_ACT_CL_1005_Hydraulic_System_Checklist_R000_2026_04_12.pdf",
            language="en",
            visible_title="Hydraulic System Checklist",
            english_title=None,
            revision_note="Initial checklist for hydraulic readiness after flap actuator replacement.",
            summary="This checklist defines the maintenance release flow for the hydraulic loop that powers the flap, brake, and landing gear actuators on an armed unmanned aircraft. It is intended for post-repair pressurization and leak verification before a functional taxi test.",
            paragraph_one="Technicians shall inspect the reservoir cap seal, service the fluid to the marked cold level, and confirm that no metallic residue is present in the return screen. A clean lint-free wipe is required at every hose coupling before pressure is applied to prevent introducing debris into the actuator manifold.",
            paragraph_two="Once the electric pump is enabled, the crew verifies stable pressure rise, actuator response timing, and return-line temperature. Any fluctuation beyond the approved pressure band requires system depressurization and a repeat visual check of the flap actuator fittings and landing gear uplock line.",
            table_title="Hydraulic Release Checklist",
            table_headers=["Step", "Check", "Expected", "Record"],
            table_rows=[
                ["1", "Reservoir level", "Cold mark reached", "Service / OK"],
                ["2", "Pump pressure", "Nominal rise", "Log reading"],
                ["3", "Actuator fittings", "Dry and torqued", "Visual OK"],
                ["4", "Return temperature", "Stable trend", "Log reading"],
            ],
            diagram_title="Hydraulic Loop Diagram",
            diagram_kind="hydraulic_loop",
            diagram_caption="Simplified hydraulic flow from reservoir to actuator manifold and return line.",
        ),
        "SA_EN_TMP_RP_1007_Engine_Temperature_Log_R000_2026_04_15.pdf": DocumentSpec(
            filename="SA_EN_TMP_RP_1007_Engine_Temperature_Log_R000_2026_04_15.pdf",
            language="en",
            visible_title="Engine Temperature Log",
            english_title=None,
            revision_note="Initial logging template for recovery inspection after armed loiter mission.",
            summary="This report captures the post-flight temperature condition of the engine bay on an armed UAV after extended loiter and descent. It is designed to highlight unusual spread patterns that may indicate cooling duct blockage or fuel scheduling drift.",
            paragraph_one="After propeller stop, the maintenance observer records the five engine-bay sensor values within two minutes to preserve a meaningful heat map. The aircraft must remain pointed into wind with cowl doors closed until the first capture is complete, preventing false cooling gradients caused by cross-draft exposure.",
            paragraph_two="A second reading is taken after ten minutes to compare cooldown behavior. If the delta between left and right upper sensors remains elevated, the team inspects exhaust shielding, nozzle seal condition, and any soot residue near the firewall-mounted harness brackets.",
            table_title="Temperature Capture Log",
            table_headers=["Sensor", "2 min", "10 min", "Status"],
            table_rows=[
                ["T1", "188 C", "132 C", "Normal"],
                ["T2", "194 C", "138 C", "Normal"],
                ["T3", "201 C", "149 C", "Watch"],
                ["T4", "176 C", "124 C", "Normal"],
            ],
            diagram_title="Sensor Location Map",
            diagram_kind="temperature_map",
            diagram_caption="Relative placement of engine-bay temperature sensors used for post-flight comparison.",
        ),
    }


def turkish_documents() -> dict[str, DocumentSpec]:
    return {
        "MT_EN_FUE_PR_1002_Engine_Maintenance_Procedure_R000_2026_04_09.pdf": DocumentSpec(
            filename="MT_EN_FUE_PR_1002_Engine_Maintenance_Procedure_R000_2026_04_09.pdf",
            language="tr",
            visible_title="Motor Bakim Proseduru",
            english_title="Engine Maintenance Procedure",
            revision_note="Ilk yayin. Silahli IHA motor yakit hattinda temel servis ve purge adimlari tanimlandi.",
            summary="Bu prosedur, silahli insansiz hava araci motoru icin filtre degisimi, yakit hattinin purge edilmesi ve ilk calistirma oncesi emniyet dogrulamasini tarif eder. Metin, ucus hattinda hizli fakat izlenebilir bir bakim sirasi saglamak icin hazirlanmistir.",
            paragraph_one="Bakim ekibi once kanat ici tanktan filtre paketine kadar olan hatti gozle kontrol eder, yakit numunesi alir ve su veya partikule rastlanirsa islemi durdurur. Butun baglanti noktalarinda tork boyasi gorunur olmali, motora yakin esnek hortumlarda surtunme izi bulunmamali ve damlama olmamalidir.",
            paragraph_two="Filtre degisimi tamamlandiktan sonra prime pompasiyla hat doldurulur ve purge islemi uygulanir. Ilk calistirma, sadece yer emniyet subayi ve gorev konsolu veri baglantisi hazir oldugunda yapilir; rolanti stabil hale gelmeden devir artisi denenmez.",
            table_title="Bakim Adimlari",
            table_headers=["Adim", "Bolum", "Kriter", "Kayit"],
            table_rows=[
                ["1", "Tank numunesi", "Su yok, tortu yok", "Numune onay"],
                ["2", "Filtre paketi", "Yeni eleman takili", "Seri no yaz"],
                ["3", "Purge suresi", "60 sn", "Sureyi kaydet"],
                ["4", "Rolanti", "Stabil", "Motor aciklamasi"],
            ],
            diagram_title="Yakit Akis Semasi",
            diagram_kind="engine_flow",
            diagram_caption="Silahli IHA motor yakit akisi: tank, filtre, metering ve motor cekirdegi.",
        ),
        "MT_EN_FUE_PR_1002_Engine_Maintenance_Procedure_R001_2026_04_13.pdf": DocumentSpec(
            filename="MT_EN_FUE_PR_1002_Engine_Maintenance_Procedure_R001_2026_04_13.pdf",
            language="tr",
            visible_title="Motor Bakim Proseduru",
            english_title="Engine Maintenance Procedure",
            revision_note="Cevresel toz testinden sonra filtre fark basinc kontrolu ve uzatilmis purge adimi eklendi.",
            summary="Bu revizyon, silahli insansiz hava araci motoru icin filtre degisimi, fark basinc kontrolu ve yakit hattinin purge edilmesini gunceller. Ozellikle tozlu meydan operasyonlarinda filtre yuklenmesini daha iyi izlemek icin yeni kontrol maddeleri eklenmistir.",
            paragraph_one="Bakim ekibi once kanat ici tanktan filtre paketine kadar olan hatti gozle kontrol eder, yakit numunesi alir ve su veya partikule rastlanirsa islemi durdurur. Filtre girisi ile cikisi arasindaki fark basinc okunur; limit disina cikan bir deger, prime isleminden once filtre paketinin yeniden degistirilmesini gerektirir.",
            paragraph_two="Filtre degisimi tamamlandiktan sonra prime pompasiyla hat doldurulur ve purge islemi uygulanir. Ilk calistirma, sadece yer emniyet subayi ve gorev konsolu veri baglantisi hazir oldugunda yapilir; rolanti stabil hale gelmeden devir artisi denenmez ve purge suresi artik standart olarak 75 saniyedir.",
            table_title="Bakim Adimlari",
            table_headers=["Adim", "Bolum", "Kriter", "Kayit"],
            table_rows=[
                ["1", "Tank numunesi", "Su yok, tortu yok", "Numune onay"],
                ["2", "Filtre fark basinc", "Limit ici", "Degeri yaz"],
                ["3", "Purge suresi", "75 sn", "Sureyi kaydet"],
                ["4", "Rolanti", "Stabil", "Motor aciklamasi"],
            ],
            diagram_title="Yakit Akis Semasi",
            diagram_kind="engine_flow",
            diagram_caption="Revize motor yakit akisi: filtre fark basinc ve purge kontrol noktalarini gosterir.",
        ),
        "MT_EN_FUE_PR_1002_Engine_Maintenance_Procedure_R002_2026_04_16.pdf": DocumentSpec(
            filename="MT_EN_FUE_PR_1002_Engine_Maintenance_Procedure_R002_2026_04_16.pdf",
            language="tr",
            visible_title="Motor Bakim Proseduru",
            english_title="Engine Maintenance Procedure",
            revision_note="Ag destekli gorevler icin purge standardi ve yakit hatti baglanti tork dogrulamasi guncellendi.",
            summary="Bu revizyon, silahli insansiz hava araci motor prosedurunu sahadaki yeni gorev temposuna gore kesinlestirir. Yakit hatti baglanti tork dogrulamasi, fark basinc kontrolu ve daha uzun purge suresi artik zorunlu adim olarak tanimlanmistir.",
            paragraph_one="Bakim ekibi once kanat ici tanktan filtre paketine kadar olan hatti gozle kontrol eder, yakit numunesi alir ve su veya partikule rastlanirsa islemi durdurur. Filtre girisi ile cikisi arasindaki fark basinc okunur, yakit hatti kelepce ve baglanti noktalarinda tork boyasi tek tek dogrulanir ve eksik iz varsa yeniden tork uygulanir.",
            paragraph_two="Filtre degisimi tamamlandiktan sonra prime pompasiyla hat doldurulur ve purge islemi uygulanir. Ilk calistirma, sadece yer emniyet subayi ve gorev konsolu veri baglantisi hazir oldugunda yapilir; purge suresi artik 90 saniyedir ve motor rolantide stabilize olduktan sonra veri baginda hata yoksa sonraki gorev paketine gecilir.",
            table_title="Bakim Adimlari",
            table_headers=["Adim", "Bolum", "Kriter", "Kayit"],
            table_rows=[
                ["1", "Tank numunesi", "Su yok, tortu yok", "Numune onay"],
                ["2", "Baglanti torku", "Isaret tam", "Tork onay"],
                ["3", "Purge suresi", "90 sn", "Sureyi kaydet"],
                ["4", "Rolanti ve link", "Stabil / hata yok", "Motor aciklamasi"],
            ],
            diagram_title="Yakit Akis Semasi",
            diagram_kind="engine_flow",
            diagram_caption="Son revizyon yakit akisi: tork kontrolu, filtre fark basinc ve uzun purge adimi.",
        ),
        "QA_EL_PWR_PL_1004_Avionics_Parts_List_R000_2026_04_08.pdf": DocumentSpec(
            filename="QA_EL_PWR_PL_1004_Avionics_Parts_List_R000_2026_04_08.pdf",
            language="tr",
            visible_title="Aviyonik Parca Listesi",
            english_title="Avionics Parts List",
            revision_note="Ilk yayin. Silahli IHA gorev bilgisayari ve guc dagitim alt gruplari listelendi.",
            summary="Bu belge, silahli insansiz hava aracinda kullanilan temel aviyonik guc dagitim bilesenlerini izlenebilir bir parca listesi olarak sunar. Liste, depo kabul, hat bakimi ve seri numara kontrolu icin ortak referans olarak kullanilir.",
            paragraph_one="Parca listesi, 28V ana bus, gorev bilgisayari, EO-IR gorev yuk baglanti modulu ve veri bagi radyo guc modullerini kapsar. Her kalem, kalite kontrol etiket durumu, yazilim konfigrasyonu ve son kabul inceleme tarihi ile birlikte tutulmalidir.",
            paragraph_two="Kalite muhendisi, saha stokundan cekilen her kalemin seri numarasini gorev oncesi paket ile karsilastirir. Uyumsuz bir seri no veya acik kalmis sigorta karti gorulurse parca kullanimdan cekilir ve uygunsuzluk kaydi acilir.",
            table_title="Parca Envanteri",
            table_headers=["Kalem", "Aciklama", "Miktar", "Durum"],
            table_rows=[
                ["P-11", "Gorev bilgisayari karti", "2", "Kabul edildi"],
                ["P-24", "28V bus role modulu", "3", "Kabul edildi"],
                ["P-32", "EO-IR guc arayuzu", "1", "Izleniyor"],
                ["P-47", "Veri bagi sigorta paketi", "4", "Kabul edildi"],
            ],
            diagram_title="Guc Dagitim Blogu",
            diagram_kind="power_block",
            diagram_caption="Silahli IHA aviyonik guc dagitim bloklari ve breaker paket akisi.",
        ),
        "AV_LG_LND_DG_1006_Landing_Gear_Diagram_Guide_R000_2026_04_07.pdf": DocumentSpec(
            filename="AV_LG_LND_DG_1006_Landing_Gear_Diagram_Guide_R000_2026_04_07.pdf",
            language="tr",
            visible_title="Inis Takimi Semasi Kilavuzu",
            english_title="Landing Gear Diagram Guide",
            revision_note="Ilk yayin. Silahli IHA ana inis takimi geometri noktalarini aciklar.",
            summary="Bu kilavuz, silahli insansiz hava aracinin ana inis takimi duzenini ve kontrol edilmesi gereken geometri noktalarini tanimlar. Amac, hat bakim ekibinin aci, strut uzamasi ve teker hizasini ayni sema uzerinden yorumlayabilmesidir.",
            paragraph_one="Semadaki ana beam, strut ve wheel referanslari; acik durumdaki inis takiminda gorulmesi gereken temel hatlari temsil eder. Acilis sonrasi asiri aci farki, sigorta pimi bozulmasi veya teker hizasizligi varsa ucus once manuel inceleme gerekir.",
            paragraph_two="Kilavuz, ozellikle sert pistli acil geri donuslerden sonra gorsel karsilastirma icin kullanilir. Ekip, semayi fiziksel ucak uzerindeki referanslarla eslestirir ve gerekli ise uplock ve side-brace bolgelerinde ikincil kontrol talep eder.",
            table_title="Geometri Kontrol Noktalari",
            table_headers=["Nokta", "Kontrol", "Beklenen", "Not"],
            table_rows=[
                ["G1", "Main beam duzlemi", "Dogru", "Gorsel onay"],
                ["G2", "Strut uzamasi", "Standart aralik", "Olc ve yaz"],
                ["G3", "Teker hizasi", "Simetrik", "Gorsel onay"],
                ["G4", "Side brace", "Bosluk yok", "Bakim notu"],
            ],
            diagram_title="Inis Takimi Semasi",
            diagram_kind="landing_gear",
            diagram_caption="Ana beam, strut ve teker referanslari ile inis takimi geometri semasi.",
        ),
        "QA_FL_COM_PR_1008_Cockpit_Communication_Test_Procedure_R000_2026_04_18.pdf": DocumentSpec(
            filename="QA_FL_COM_PR_1008_Cockpit_Communication_Test_Procedure_R000_2026_04_18.pdf",
            language="tr",
            visible_title="Kokpit Haberlesme Test Proseduru",
            english_title="Cockpit Communication Test Procedure",
            revision_note="Ilk yayin. Yer kontrol ve silahli IHA veri bag zinciri test sirasi tanimlandi.",
            summary="Bu prosedur, silahli insansiz hava araci yer kontrol istasyonunda pilot konsolu, gorev konsolu ve hava araci arasindaki haberlesme zincirini test etmek icin hazirlanmistir. Ses, veri ve onay geri donusu ayni sirada dogrulanir.",
            paragraph_one="Test ekibi once pilot konsolundan ses kontrolunu, ardindan gorev konsolundan hedef devir mesajini yollar. Relay veya SATCOM katmaninda gecikme gorulurse paket zaman damgalari kaydedilir ve sistem tekrar baslatilmaz; once hatanin yeri izole edilir.",
            paragraph_two="Arac tarafindan gelen kabul mesaji ile beraber stores inhibit ve gorev veri seti durum bayraklari da okunur. Herhangi bir eksik cevapta prosedur, operatoru sesli tekrar yapmaya degil fiziksel baglanti ve sifreleme durumunu kontrol etmeye yonlendirir.",
            table_title="Haberlesme Test Akisi",
            table_headers=["Adim", "Kaynak", "Beklenen Sonuc", "Kayit"],
            table_rows=[
                ["1", "Pilot konsolu", "Ses acik", "Onay ver"],
                ["2", "Gorev konsolu", "Hedef mesaji gecti", "Zaman yaz"],
                ["3", "Relay / SATCOM", "Gecikme limit ici", "Olc ve yaz"],
                ["4", "IHA geri donusu", "Ack alindi", "Durumu isaretle"],
            ],
            diagram_title="Haberlesme Zinciri",
            diagram_kind="comms_chain",
            diagram_caption="Pilot konsolu, gorev konsolu, relay ve UCAV veri bag zinciri.",
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the XDTS PDF pool sample files.")
    parser.add_argument(
        "--pool-dir",
        default=str(Path(__file__).resolve().parents[1] / "pdf_pool"),
        help="Path to the pdf_pool directory.",
    )
    parser.add_argument(
        "--meta-dir",
        default=str(Path(__file__).resolve().parents[1] / "pdf_pool_meta"),
        help="Path to the pdf_pool metadata directory.",
    )
    args = parser.parse_args()

    pool_dir = Path(args.pool_dir)
    meta_dir = Path(args.meta_dir)
    pool_dir.mkdir(parents=True, exist_ok=True)

    specs = {}
    specs.update(english_documents())
    specs.update(turkish_documents())

    with (meta_dir / "index.csv").open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        filenames = [row["filename"] for row in reader]

    if set(filenames) != set(specs):
        missing_specs = sorted(set(filenames) - set(specs))
        extra_specs = sorted(set(specs) - set(filenames))
        raise SystemExit(
            "Spec mismatch with index.csv. "
            f"Missing specs: {missing_specs}. Extra specs: {extra_specs}."
        )

    for filename in filenames:
        render_document(specs[filename], pool_dir / filename)
        print(f"Generated {filename}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
