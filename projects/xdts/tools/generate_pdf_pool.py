from __future__ import annotations

import argparse
import csv
import zlib
from dataclasses import dataclass
from pathlib import Path

from fpdf import FPDF
from PIL import Image, ImageDraw


PAGE_WIDTH = 595
PAGE_HEIGHT = 842
LEFT_MARGIN = 48
RIGHT_MARGIN = 48
TOP_MARGIN = 54
BOTTOM_MARGIN = 54
WINDOWS_FONT_DIR = Path(__import__("os").environ.get("WINDIR", "C:/WINDOWS")) / "Fonts"
UNICODE_REGULAR_FONT = WINDOWS_FONT_DIR / "arial.ttf"
UNICODE_BOLD_FONT = WINDOWS_FONT_DIR / "arialbd.ttf"


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


def wrap_identifier_value(label: str, value: str, max_chars: int) -> list[str]:
    label_prefix = f"{label} "
    available = max(8, max_chars - len(label_prefix))
    if len(label_prefix) + len(value) <= max_chars:
        return [f"{label_prefix}{value}"]

    parts = value.split("_")
    chunks: list[str] = []
    current = parts[0]
    for part in parts[1:]:
        candidate = f"{current}_{part}"
        if len(candidate) <= available:
            current = candidate
        else:
            chunks.append(f"{current}_")
            current = part
    chunks.append(current)
    return [f"{label_prefix}{chunks[0]}"] + chunks[1:]


def wrap_labeled_text(label: str, value: str, max_chars: int) -> list[str]:
    label_prefix = f"{label} "
    first_line_capacity = max(8, max_chars - len(label_prefix))
    value_lines = chunk_text(value, first_line_capacity)
    if not value_lines:
        return [label]
    wrapped = [f"{label_prefix}{value_lines[0]}"]
    if len(value_lines) > 1:
        wrapped.extend(chunk_text(" ".join(value_lines[1:]), max_chars))
    return wrapped


def localized_labels(language: str) -> dict[str, str]:
    if language == "tr":
        return {
            "summary": "Özet",
            "operational_context": "Operasyonel Bağlam",
            "document_code": "Doküman Kodu",
            "revision": "Revizyon",
            "effective_date": "Yürürlük Tarihi",
            "reference_title": "Referans Başlığı",
            "revision_note": "Revizyon Notu",
            "figure": "Şekil",
            "page": "Sayfa",
            "technical_data": "XDTS KONTROLLÜ TEKNİK VERİ",
        }
    return {
        "summary": "Summary",
        "operational_context": "Operational Context",
        "document_code": "Document Code",
        "revision": "Revision",
        "effective_date": "Effective Date",
        "reference_title": "Reference Title",
        "revision_note": "Revision Note",
        "figure": "Figure",
        "page": "Page",
        "technical_data": "XDTS CONTROLLED TECHNICAL DATA",
    }


def infer_document_class(filename: str, language: str = "en") -> str:
    doc_type_code = filename.split("_")[3]
    english_labels = {
        "CL": "FLIGHT RELEASE CHECKLIST",
        "PR": "MAINTENANCE PROCEDURE",
        "RP": "CONTROLLED INSPECTION REPORT",
        "PL": "CONFIGURATION PARTS LIST",
        "DG": "REFERENCE DIAGRAM GUIDE",
    }
    turkish_labels = {
        "CL": "SERBEST BIRAKMA KONTROL LİSTESİ",
        "PR": "KONTROLLÜ PROSEDÜR",
        "RP": "KONTROLLÜ MUAYENE RAPORU",
        "PL": "KONFİGÜRASYON PARÇA LİSTESİ",
        "DG": "REFERANS ŞEMA KILAVUZU",
    }
    mapping = turkish_labels if language == "tr" else english_labels
    default = "KONTROLLÜ TEKNİK VERİ" if language == "tr" else "CONTROLLED TECHNICAL DATA"
    return mapping.get(doc_type_code, default)


def localized_helper_text(kind: str, language: str) -> str:
    if language == "tr":
        return {
            "engine_flow": "Akış şeması tank, filtre, ölçüm birimi ve motor girişindeki temel servis noktalarını gösterir.",
            "power_block": "Blok şema, 28 V bus üzerinden görev bilgisayarı, EO-IR yükü ve veri bağı besleme yolunu gösterir.",
            "landing_gear": "Şema, ana kiriş, amortisör ve teker eksenini aynı düzende göstererek geometri karşılaştırmasını kolaylaştırır.",
            "comms_chain": "Blok şema, pilot, görev, röle ve İHA arasındaki mesaj-onay akışını aynı sırada gösterir.",
            "temperature_map": "Renk yoğunluğu, sensörler arasındaki sıcaklık dağılımını ve soğuma farklarını karşılaştırmak için kullanılır.",
            "hydraulic_loop": "Şema, rezervuar, pompa, manifold ve geri dönüş hattının kontrol noktalarını birlikte gösterir.",
            "safety_arc": "Şema, emniyet şeridi, ekip yaya hattı ve açık güvenlik alanını birlikte gösterir.",
            "uav_preflight": "Amber işaretler, kontrol tablosunda referans verilen serbest bırakma muayene bölgelerini gösterir.",
        }.get(kind, "")
    return {
        "uav_preflight": "Amber markers identify the release-inspection sectors referenced in the control table.",
        "engine_flow": "Akis semasi tank, filtre, metering ve motor girisinde yapilan temel servis noktalarini gosterir.",
        "safety_arc": "Sema emniyet seridi, ekip yaya hattini ve acik kalan clear-arc alanini birlikte gosterir.",
        "power_block": "Blok sema 28V bus uzerinden gorev bilgisayari, EO-IR yuk ve veri bagi besleme yolunu gosterir.",
        "hydraulic_loop": "Sema rezervuar, pompa, manifold ve geri donus hattinin kontrol noktalarini birlikte gosterir.",
        "landing_gear": "Sema ana beam, strut ve teker eksenini ayni duzende gorerek geometri karsilastirmasi yapmayi kolaylastirir.",
        "temperature_map": "Renk yogunlugu sensorler arasindaki sicaklik dagilimini ve soguma farklarini karsilastirmak icin kullanilir.",
        "comms_chain": "Blok sema pilot, gorev, relay ve UCAV arasindaki mesaj-onay akislarini ayni sirada gosterir.",
    }.get(kind, "")


class PDFPage:
    def __init__(self) -> None:
        self.commands: list[str] = []
        self.images: list[PDFImage] = []

    def add(self, command: str) -> None:
        self.commands.append(command)

    def render(self) -> str:
        return "\n".join(self.commands) + "\n"


@dataclass
class PDFImage:
    name: str
    width: int
    height: int
    data: bytes


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
        document_class: str,
        doc_code: str,
        title: str,
        revision: str,
        date_text: str,
        language: str,
        english_title: str | None,
        revision_note: str,
    ) -> None:
        labels = localized_labels(language)
        box_width = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN
        left_col_x = LEFT_MARGIN + 10
        left_col_width = box_width - 20
        doc_code_max_chars = max(24, int(left_col_width / (10 * 0.52)))
        doc_code_lines = wrap_identifier_value(f"{labels['document_code']}:", doc_code, doc_code_max_chars)[:3]
        doc_code_line_count = max(1, len(doc_code_lines))
        note_max_chars = max(30, int((box_width - 20) / (10 * 0.55)))
        note_lines = wrap_labeled_text(f"{labels['revision_note']}:", revision_note, note_max_chars)[:3]
        note_line_count = max(1, len(note_lines))
        header_height = 132 + ((note_line_count - 1) * 12) + (14 if english_title else 0) + ((doc_code_line_count - 1) * 14)
        self.ensure_space(header_height + 24)
        box_top = self.cursor_y + 18
        box_bottom = box_top - header_height
        top_band_y = box_top - 18
        self.current_page.add("0.92 g")
        self.current_page.add(f"{LEFT_MARGIN:.2f} {top_band_y:.2f} {box_width:.2f} 18.00 re f")
        self.current_page.add("0 g")
        self.current_page.add("0.15 0.15 0.15 RG")
        self.current_page.add(f"{LEFT_MARGIN:.2f} {box_bottom:.2f} {box_width:.2f} {box_top - box_bottom:.2f} re S")
        self.current_page.add("0 0 0 RG")
        self.text_line(LEFT_MARGIN + 10, box_top - 13, document_class, font="F2", size=8)
        self.text_line(LEFT_MARGIN + 316, box_top - 13, labels["technical_data"], font="F2", size=8)
        self.text_line(LEFT_MARGIN + 10, box_top - 42, title, font="F2", size=18)
        first_meta_y = box_top - 60
        for index, line in enumerate(doc_code_lines):
            self.text_line(left_col_x, first_meta_y - (index * 14), line, font="F1", size=10)
        revision_y = first_meta_y - (14 * doc_code_line_count)
        self.text_line(left_col_x, revision_y, f"{labels['revision']}: {revision}", font="F1", size=10)
        effective_date_y = revision_y - 14
        self.text_line(left_col_x, effective_date_y, f"{labels['effective_date']}: {date_text}", font="F1", size=10)
        detail_y = effective_date_y - 14
        if english_title:
            self.text_line(LEFT_MARGIN + 10, detail_y, f"{labels['reference_title']}: {english_title}", font="F1", size=10)
            detail_y -= 14
        note_start_y = detail_y
        for index, line in enumerate(note_lines):
            self.text_line(LEFT_MARGIN + 10, note_start_y - (index * 12), line, font="F1", size=10)
        self.cursor_y = box_bottom - 8
        self.rule(gap_before=0, gap_after=16)

    def draw_table(self, headers: list[str], rows: list[list[str]], *, title: str) -> None:
        col_count = len(headers)
        table_width = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN
        col_width = table_width / col_count
        header_line_step = 10
        body_line_step = 9
        cell_max_chars = max(8, int((col_width - 10) / 5.2))
        header_cells = [chunk_text(header, cell_max_chars)[:2] for header in headers]
        header_line_count = max(len(cell) for cell in header_cells)
        header_height = max(24, 15 + ((header_line_count - 1) * header_line_step) + 9)
        wrapped_rows = [[chunk_text(value, cell_max_chars)[:3] for value in row] for row in rows]
        row_heights = [
            max(24, 15 + ((max(len(cell) for cell in wrapped_row) - 1) * body_line_step) + 9)
            for wrapped_row in wrapped_rows
        ]
        table_height = header_height + sum(row_heights)
        self.ensure_space(table_height + 42)
        self.heading(title, size=12, gap_after=4)
        top = self.cursor_y
        self.current_page.add("0.94 g")
        self.current_page.add(f"{LEFT_MARGIN:.2f} {top - header_height:.2f} {table_width:.2f} {header_height:.2f} re f")
        self.current_page.add("0 g")
        self.current_page.add(f"{LEFT_MARGIN:.2f} {top - table_height:.2f} {table_width:.2f} {table_height:.2f} re S")
        cumulative_height = header_height
        for row_height in row_heights:
            y = top - cumulative_height
            self.current_page.add(f"{LEFT_MARGIN:.2f} {y:.2f} m {LEFT_MARGIN + table_width:.2f} {y:.2f} l S")
            cumulative_height += row_height
        for index in range(1, col_count):
            x = LEFT_MARGIN + (index * col_width)
            self.current_page.add(f"{x:.2f} {top:.2f} m {x:.2f} {top - table_height:.2f} l S")

        header_text_y = top - 15
        for col_index, header_lines in enumerate(header_cells):
            for line_index, line in enumerate(header_lines):
                self.text_line(
                    LEFT_MARGIN + 6 + (col_index * col_width),
                    header_text_y - (line_index * header_line_step),
                    line,
                    font="F2",
                    size=9,
                )

        row_top = top - header_height
        for wrapped_row, row_height in zip(wrapped_rows, row_heights):
            cell_y = row_top - 15
            for col_index, wrapped in enumerate(wrapped_row):
                for wrapped_index, line in enumerate(wrapped):
                    self.text_line(
                        LEFT_MARGIN + 6 + (col_index * col_width),
                        cell_y - (wrapped_index * body_line_step),
                        line,
                        font="F1",
                        size=8,
                    )
            row_top -= row_height
        self.cursor_y = top - table_height - 16

    def draw_labeled_box(self, x: float, y: float, width: float, height: float, label: str) -> None:
        self.current_page.add(f"{x:.2f} {y:.2f} {width:.2f} {height:.2f} re S")
        self.text_line(x + 6, y + (height / 2) - 3, label, font="F1", size=9)

    def draw_arrow(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self.current_page.add(f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")
        self.current_page.add(f"{x2:.2f} {y2:.2f} m {x2 - 6:.2f} {y2 + 3:.2f} l S")
        self.current_page.add(f"{x2:.2f} {y2:.2f} m {x2 - 6:.2f} {y2 - 3:.2f} l S")

    def draw_image(self, image: Image.Image, *, x: float, y: float, width: float, height: float) -> None:
        rgb_image = image.convert("RGB")
        image_name = f"Im{len(self.current_page.images) + 1}"
        self.current_page.images.append(
            PDFImage(
                name=image_name,
                width=rgb_image.width,
                height=rgb_image.height,
                data=rgb_image.tobytes(),
            )
        )
        self.current_page.add(f"q {width:.2f} 0 0 {height:.2f} {x:.2f} {y:.2f} cm /{image_name} Do Q")

    def draw_diagram(self, *, title: str, kind: str, caption: str) -> None:
        diagram_height = 200
        self.ensure_space(diagram_height + 40)
        self.heading(title, size=12, gap_after=4)
        base_y = self.cursor_y - 20
        figure_caption_y = base_y - 98
        cursor_end_y = base_y - 118

        if kind == "uav_preflight":
            figure_image = build_uav_preflight_reference_image()
            image_width = 420
            image_height = 118
            image_x = LEFT_MARGIN + ((PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN - image_width) / 2)
            image_y = base_y - 122
            self.draw_image(
                figure_image,
                x=image_x,
                y=image_y,
                width=image_width,
                height=image_height,
            )
            helper_line_y = image_y - 18
            self.text_line(
                LEFT_MARGIN,
                helper_line_y,
                "Amber markers identify the release-inspection sectors referenced in the control table.",
                size=9,
            )
            figure_caption_y = helper_line_y - 36
            cursor_end_y = figure_caption_y - 20
        elif kind == "engine_flow":
            figure_image = build_engine_flow_reference_image()
            image_width = 430
            image_height = 124
            image_x = LEFT_MARGIN + ((PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN - image_width) / 2)
            image_y = base_y - 126
            self.draw_image(
                figure_image,
                x=image_x,
                y=image_y,
                width=image_width,
                height=image_height,
            )
            helper_line_y = image_y - 18
            self.text_line(
                LEFT_MARGIN,
                helper_line_y,
                "Akis semasi tank, filtre, metering ve motor girisinde yapilan temel servis noktalarini gosterir.",
                size=9,
            )
            figure_caption_y = helper_line_y - 36
            cursor_end_y = figure_caption_y - 20
        elif kind == "safety_arc":
            figure_image = build_safety_layout_reference_image()
            image_width = 426
            image_height = 126
            image_x = LEFT_MARGIN + ((PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN - image_width) / 2)
            image_y = base_y - 126
            self.draw_image(
                figure_image,
                x=image_x,
                y=image_y,
                width=image_width,
                height=image_height,
            )
            helper_line_y = image_y - 18
            self.text_line(
                LEFT_MARGIN,
                helper_line_y,
                "Sema emniyet seridi, ekip yaya hattini ve acik kalan clear-arc alanini birlikte gosterir.",
                size=9,
            )
            figure_caption_y = helper_line_y - 36
            cursor_end_y = figure_caption_y - 20
        elif kind == "power_block":
            figure_image = build_power_block_reference_image()
            image_width = 430
            image_height = 124
            image_x = LEFT_MARGIN + ((PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN - image_width) / 2)
            image_y = base_y - 126
            self.draw_image(figure_image, x=image_x, y=image_y, width=image_width, height=image_height)
            helper_line_y = image_y - 18
            self.text_line(
                LEFT_MARGIN,
                helper_line_y,
                "Blok sema 28V bus uzerinden gorev bilgisayari, EO-IR yuk ve veri bagi besleme yolunu gosterir.",
                size=9,
            )
            figure_caption_y = helper_line_y - 36
            cursor_end_y = figure_caption_y - 20
        elif kind == "hydraulic_loop":
            figure_image = build_hydraulic_loop_reference_image()
            image_width = 430
            image_height = 124
            image_x = LEFT_MARGIN + ((PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN - image_width) / 2)
            image_y = base_y - 126
            self.draw_image(figure_image, x=image_x, y=image_y, width=image_width, height=image_height)
            helper_line_y = image_y - 18
            self.text_line(
                LEFT_MARGIN,
                helper_line_y,
                "Sema rezervuar, pompa, manifold ve geri donus hattinin kontrol noktalarini birlikte gosterir.",
                size=9,
            )
            figure_caption_y = helper_line_y - 36
            cursor_end_y = figure_caption_y - 20
        elif kind == "landing_gear":
            figure_image = build_landing_gear_reference_image()
            image_width = 420
            image_height = 124
            image_x = LEFT_MARGIN + ((PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN - image_width) / 2)
            image_y = base_y - 126
            self.draw_image(figure_image, x=image_x, y=image_y, width=image_width, height=image_height)
            helper_line_y = image_y - 18
            self.text_line(
                LEFT_MARGIN,
                helper_line_y,
                "Sema ana beam, strut ve teker eksenini ayni duzende gorerek geometri karsilastirmasi yapmayi kolaylastirir.",
                size=9,
            )
            figure_caption_y = helper_line_y - 36
            cursor_end_y = figure_caption_y - 20
        elif kind == "temperature_map":
            figure_image = build_temperature_map_reference_image()
            image_width = 420
            image_height = 122
            image_x = LEFT_MARGIN + ((PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN - image_width) / 2)
            image_y = base_y - 124
            self.draw_image(figure_image, x=image_x, y=image_y, width=image_width, height=image_height)
            helper_line_y = image_y - 18
            self.text_line(
                LEFT_MARGIN,
                helper_line_y,
                "Renk yogunlugu sensorler arasindaki sicaklik dagilimini ve soguma farklarini karsilastirmak icin kullanilir.",
                size=9,
            )
            figure_caption_y = helper_line_y - 36
            cursor_end_y = figure_caption_y - 20
        elif kind == "comms_chain":
            figure_image = build_comms_chain_reference_image()
            image_width = 430
            image_height = 120
            image_x = LEFT_MARGIN + ((PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN - image_width) / 2)
            image_y = base_y - 124
            self.draw_image(figure_image, x=image_x, y=image_y, width=image_width, height=image_height)
            helper_line_y = image_y - 18
            self.text_line(
                LEFT_MARGIN,
                helper_line_y,
                "Blok sema pilot, gorev, relay ve UCAV arasindaki mesaj-onay akislarini ayni sirada gosterir.",
                size=9,
            )
            figure_caption_y = helper_line_y - 36
            cursor_end_y = figure_caption_y - 20

        self.text_line(LEFT_MARGIN, figure_caption_y, f"Figure 1. {caption}", font="F1", size=9)
        self.cursor_y = cursor_end_y

    def footer(self, *, doc_code: str, revision: str) -> None:
        for index, page in enumerate(self.pages, start=1):
            page.add(f"BT /F1 8 Tf 1 0 0 1 {LEFT_MARGIN:.2f} 24.00 Tm ({doc_code} | {revision}) Tj ET")
            page.add(
                f"BT /F1 8 Tf 1 0 0 1 {PAGE_WIDTH - RIGHT_MARGIN - 66:.2f} 24.00 Tm "
                f"(Page {index} of {len(self.pages)}) Tj ET"
            )


class XDTSUnicodePDF(FPDF):
    def __init__(self, *, doc_code: str, revision: str, language: str) -> None:
        super().__init__(unit="pt", format=(PAGE_WIDTH, PAGE_HEIGHT))
        self.doc_code = doc_code
        self.revision = revision
        self.language = language
        self.labels = localized_labels(language)
        self.set_auto_page_break(False)
        self.set_compression(False)
        self.alias_nb_pages()
        self.add_font("XDTSUnicode", "", str(UNICODE_REGULAR_FONT))
        self.add_font("XDTSUnicode", "B", str(UNICODE_BOLD_FONT))

    def footer(self) -> None:
        self.set_font("XDTSUnicode", "", 8)
        footer_y = self.h - 24
        self.text(LEFT_MARGIN, footer_y, f"{self.doc_code} | {self.revision}")
        page_text = f"{self.labels['page']} {self.page_no()} / {{nb}}"
        self.text(self.w - RIGHT_MARGIN - self.get_string_width(page_text), footer_y, page_text)


class UnicodePDFCanvas:
    def __init__(self, *, doc_code: str, revision: str, language: str) -> None:
        self.language = language
        self.labels = localized_labels(language)
        self.pdf = XDTSUnicodePDF(doc_code=doc_code, revision=revision, language=language)
        self.pdf.add_page()
        self.cursor_y = PAGE_HEIGHT - TOP_MARGIN

    def new_page(self) -> None:
        self.pdf.add_page()
        self.cursor_y = PAGE_HEIGHT - TOP_MARGIN

    def ensure_space(self, height: float) -> None:
        if self.cursor_y - height < BOTTOM_MARGIN:
            self.new_page()

    def _set_font(self, font: str, size: int) -> None:
        style = "B" if font == "F2" else ""
        self.pdf.set_font("XDTSUnicode", style, size)

    @staticmethod
    def _top_y(y: float) -> float:
        return PAGE_HEIGHT - y

    def text_line(self, x: float, y: float, text: str, *, font: str = "F1", size: int = 10) -> None:
        self._set_font(font, size)
        self.pdf.text(x, self._top_y(y), text)

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
        self.pdf.line(LEFT_MARGIN, self._top_y(y), PAGE_WIDTH - RIGHT_MARGIN, self._top_y(y))
        self.cursor_y = y - gap_after

    def _rect(self, x: float, y: float, width: float, height: float, *, fill: bool = False) -> None:
        style = "F" if fill else "D"
        self.pdf.rect(x, self._top_y(y) - height, width, height, style=style)

    def header_block(
        self,
        *,
        document_class: str,
        doc_code: str,
        title: str,
        revision: str,
        date_text: str,
        english_title: str | None,
        revision_note: str,
    ) -> None:
        box_width = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN
        left_col_x = LEFT_MARGIN + 10
        left_col_width = box_width - 20
        doc_code_max_chars = max(24, int(left_col_width / (10 * 0.52)))
        doc_code_lines = wrap_identifier_value(f"{self.labels['document_code']}:", doc_code, doc_code_max_chars)[:3]
        doc_code_line_count = max(1, len(doc_code_lines))
        note_max_chars = max(30, int((box_width - 20) / (10 * 0.55)))
        note_lines = wrap_labeled_text(f"{self.labels['revision_note']}:", revision_note, note_max_chars)[:3]
        note_line_count = max(1, len(note_lines))
        header_height = 132 + ((note_line_count - 1) * 12) + (14 if english_title else 0) + ((doc_code_line_count - 1) * 14)
        self.ensure_space(header_height + 24)
        box_top = self.cursor_y + 18
        box_bottom = box_top - header_height
        top_band_y = box_top - 18
        self.pdf.set_fill_color(235, 235, 235)
        self._rect(LEFT_MARGIN, top_band_y, box_width, 18, fill=True)
        self.pdf.set_draw_color(38, 38, 38)
        self._rect(LEFT_MARGIN, box_bottom, box_width, box_top - box_bottom, fill=False)
        self.text_line(LEFT_MARGIN + 10, box_top - 13, document_class, font="F2", size=8)
        self._set_font("F2", 8)
        technical_data_x = PAGE_WIDTH - RIGHT_MARGIN - 10 - self.pdf.get_string_width(self.labels["technical_data"])
        self.text_line(technical_data_x, box_top - 13, self.labels["technical_data"], font="F2", size=8)
        self.text_line(LEFT_MARGIN + 10, box_top - 42, title, font="F2", size=18)
        first_meta_y = box_top - 60
        for index, line in enumerate(doc_code_lines):
            self.text_line(left_col_x, first_meta_y - (index * 14), line, font="F1", size=10)
        revision_y = first_meta_y - (14 * doc_code_line_count)
        self.text_line(left_col_x, revision_y, f"{self.labels['revision']}: {revision}", font="F1", size=10)
        effective_date_y = revision_y - 14
        self.text_line(left_col_x, effective_date_y, f"{self.labels['effective_date']}: {date_text}", font="F1", size=10)
        detail_y = effective_date_y - 14
        if english_title:
            self.text_line(left_col_x, detail_y, f"{self.labels['reference_title']}: {english_title}", font="F1", size=10)
            detail_y -= 14
        for index, line in enumerate(note_lines):
            self.text_line(left_col_x, detail_y - (index * 12), line, font="F1", size=10)
        self.cursor_y = box_bottom - 8
        self.rule(gap_before=0, gap_after=16)

    def draw_table(self, headers: list[str], rows: list[list[str]], *, title: str) -> None:
        col_count = len(headers)
        table_width = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN
        col_width = table_width / col_count
        header_line_step = 10
        body_line_step = 9
        cell_max_chars = max(8, int((col_width - 10) / 5.2))
        header_cells = [chunk_text(header, cell_max_chars)[:2] for header in headers]
        header_line_count = max(len(cell) for cell in header_cells)
        header_height = max(24, 15 + ((header_line_count - 1) * header_line_step) + 9)
        wrapped_rows = [[chunk_text(value, cell_max_chars)[:3] for value in row] for row in rows]
        row_heights = [
            max(24, 15 + ((max(len(cell) for cell in wrapped_row) - 1) * body_line_step) + 9)
            for wrapped_row in wrapped_rows
        ]
        table_height = header_height + sum(row_heights)
        self.ensure_space(table_height + 42)
        self.heading(title, size=12, gap_after=4)
        top = self.cursor_y
        self.pdf.set_fill_color(240, 240, 240)
        self._rect(LEFT_MARGIN, top - header_height, table_width, header_height, fill=True)
        self._rect(LEFT_MARGIN, top - table_height, table_width, table_height, fill=False)
        cumulative_height = header_height
        for row_height in row_heights:
            y = top - cumulative_height
            self.pdf.line(LEFT_MARGIN, self._top_y(y), LEFT_MARGIN + table_width, self._top_y(y))
            cumulative_height += row_height
        for index in range(1, col_count):
            x = LEFT_MARGIN + (index * col_width)
            self.pdf.line(x, self._top_y(top), x, self._top_y(top - table_height))

        header_text_y = top - 15
        for col_index, header_lines in enumerate(header_cells):
            for line_index, line in enumerate(header_lines):
                self.text_line(
                    LEFT_MARGIN + 6 + (col_index * col_width),
                    header_text_y - (line_index * header_line_step),
                    line,
                    font="F2",
                    size=9,
                )

        row_top = top - header_height
        for wrapped_row, row_height in zip(wrapped_rows, row_heights):
            cell_y = row_top - 15
            for col_index, wrapped in enumerate(wrapped_row):
                for wrapped_index, line in enumerate(wrapped):
                    self.text_line(
                        LEFT_MARGIN + 6 + (col_index * col_width),
                        cell_y - (wrapped_index * body_line_step),
                        line,
                        font="F1",
                        size=8,
                    )
            row_top -= row_height
        self.cursor_y = top - table_height - 16

    def draw_image(self, image: Image.Image, *, x: float, y: float, width: float, height: float) -> None:
        self.pdf.image(image, x=x, y=self._top_y(y) - height, w=width, h=height)

    def draw_diagram(self, *, title: str, kind: str, caption: str) -> None:
        diagram_height = 200
        self.ensure_space(diagram_height + 40)
        self.heading(title, size=12, gap_after=4)
        base_y = self.cursor_y - 20
        figure_caption_y = base_y - 98
        cursor_end_y = base_y - 118
        image_width = 430
        image_height = 124
        image_x = LEFT_MARGIN + ((PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN - image_width) / 2)
        image_y = base_y - 126

        if kind == "uav_preflight":
            figure_image = build_uav_preflight_reference_image()
            image_width = 420
            image_height = 118
            image_x = LEFT_MARGIN + ((PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN - image_width) / 2)
            image_y = base_y - 122
        elif kind == "engine_flow":
            figure_image = build_engine_flow_reference_image()
        elif kind == "safety_arc":
            figure_image = build_safety_layout_reference_image()
            image_width = 426
            image_height = 126
            image_x = LEFT_MARGIN + ((PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN - image_width) / 2)
        elif kind == "power_block":
            figure_image = build_power_block_reference_image()
        elif kind == "hydraulic_loop":
            figure_image = build_hydraulic_loop_reference_image()
        elif kind == "landing_gear":
            figure_image = build_landing_gear_reference_image()
            image_width = 420
        elif kind == "temperature_map":
            figure_image = build_temperature_map_reference_image()
            image_width = 420
            image_height = 122
            image_x = LEFT_MARGIN + ((PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN - image_width) / 2)
            image_y = base_y - 124
        else:
            figure_image = build_comms_chain_reference_image()
            image_height = 120
            image_y = base_y - 124

        self.draw_image(figure_image, x=image_x, y=image_y, width=image_width, height=image_height)
        helper_line_y = image_y - 18
        helper_text = localized_helper_text(kind, self.language)
        if helper_text:
            self.text_line(LEFT_MARGIN, helper_line_y, helper_text, size=9)
        figure_caption_y = helper_line_y - 36
        self.text_line(LEFT_MARGIN, figure_caption_y, f"{self.labels['figure']} 1. {caption}", font="F1", size=9)
        self.cursor_y = figure_caption_y - 20

    def output(self, output_path: Path) -> None:
        self.pdf.output(str(output_path))


def build_uav_preflight_reference_image() -> Image.Image:
    image = Image.new("RGB", (920, 265), "white")
    draw = ImageDraw.Draw(image)

    silhouette = [
        (65, 133),
        (120, 121),
        (204, 112),
        (422, 109),
        (470, 90),
        (558, 92),
        (602, 107),
        (782, 114),
        (846, 99),
        (872, 133),
        (846, 167),
        (782, 152),
        (602, 158),
        (558, 173),
        (470, 175),
        (422, 156),
        (204, 154),
        (120, 145),
    ]
    wing_upper = [(325, 122), (536, 34), (611, 34), (444, 128)]
    wing_lower = [(325, 144), (536, 232), (611, 232), (444, 138)]
    tail_upper = [(178, 122), (108, 64), (78, 68), (150, 126)]
    tail_lower = [(178, 144), (108, 202), (78, 198), (150, 140)]

    draw.polygon(silhouette, fill=(24, 24, 24))
    draw.polygon(wing_upper, fill=(24, 24, 24))
    draw.polygon(wing_lower, fill=(24, 24, 24))
    draw.polygon(tail_upper, fill=(24, 24, 24))
    draw.polygon(tail_lower, fill=(24, 24, 24))

    accent = (203, 124, 37)
    for box in [
        (788, 110, 842, 156),
        (233, 84, 285, 128),
        (432, 53, 485, 98),
        (431, 167, 485, 212),
        (166, 157, 220, 208),
    ]:
        draw.rounded_rectangle(box, radius=8, outline=accent, width=6)

    return image


def build_engine_flow_reference_image() -> Image.Image:
    image = Image.new("RGB", (940, 270), "white")
    draw = ImageDraw.Draw(image)

    accent = (203, 124, 37)
    outline = (28, 28, 28)
    fill = (245, 245, 245)

    blocks = [
        ((42, 102, 184, 168), "KANAT ICI TANK"),
        ((242, 102, 384, 168), "FILTRE PAKETI"),
        ((442, 102, 598, 168), "FUEL METERING"),
        ((662, 102, 844, 168), "MOTOR GIRISI"),
    ]
    for box, label in blocks:
        draw.rounded_rectangle(box, radius=12, fill=fill, outline=outline, width=4)
        draw.text((box[0] + 18, box[1] + 24), label, fill=outline)

    for x1, x2 in [(184, 242), (384, 442), (598, 662)]:
        y = 135
        draw.line((x1, y, x2, y), fill=outline, width=5)
        draw.polygon([(x2, y), (x2 - 18, y - 10), (x2 - 18, y + 10)], fill=outline)

    for callout_box in [
        (86, 56, 144, 88),
        (286, 56, 344, 88),
        (494, 56, 552, 88),
        (734, 56, 792, 88),
    ]:
        draw.rounded_rectangle(callout_box, radius=8, outline=accent, width=5)

    draw.line((115, 88, 115, 102), fill=accent, width=3)
    draw.line((315, 88, 315, 102), fill=accent, width=3)
    draw.line((523, 88, 523, 102), fill=accent, width=3)
    draw.line((763, 88, 763, 102), fill=accent, width=3)

    draw.text((70, 196), "Drain sample", fill=(80, 80, 80))
    draw.text((268, 196), "Filtre degisimi", fill=(80, 80, 80))
    draw.text((468, 196), "Prime ve purge", fill=(80, 80, 80))
    draw.text((704, 196), "Rolanti izleme", fill=(80, 80, 80))
    return image


def build_safety_layout_reference_image() -> Image.Image:
    image = Image.new("RGB", (940, 280), "white")
    draw = ImageDraw.Draw(image)

    outline = (28, 28, 28)
    caution = (203, 124, 37)
    lane = (112, 112, 112)
    fill = (245, 245, 245)

    draw.rounded_rectangle((300, 82, 472, 196), radius=16, fill=fill, outline=outline, width=5)
    draw.text((355, 130), "UCAV", fill=outline)

    draw.rectangle((52, 204, 250, 242), outline=lane, width=5)
    draw.text((74, 214), "GROUND CREW LANE", fill=lane)

    draw.line((52, 190, 532, 190), fill=outline, width=4)
    draw.text((54, 168), "SAFE LINE", fill=outline)

    draw.arc((378, -8, 758, 272), start=305, end=22, fill=caution, width=6)
    draw.text((684, 54), "CLEAR ARC", fill=caution)

    draw.line((250, 222, 300, 180), fill=lane, width=4)
    draw.line((532, 190, 590, 96), fill=outline, width=4)
    draw.line((452, 112, 640, 52), fill=caution, width=4)

    for box in [(236, 198, 282, 244), (574, 74, 620, 120), (628, 34, 674, 80)]:
        draw.rounded_rectangle(box, radius=8, outline=caution, width=5)

    return image


def build_power_block_reference_image() -> Image.Image:
    image = Image.new("RGB", (940, 270), "white")
    draw = ImageDraw.Draw(image)
    outline = (28, 28, 28)
    accent = (203, 124, 37)
    fill = (245, 245, 245)

    blocks = [
        ((42, 102, 184, 168), "28V BUS"),
        ((250, 54, 430, 116), "GOREV BILGISAYARI"),
        ((250, 128, 430, 190), "EO-IR YUKU"),
        ((510, 92, 712, 154), "RELAY / BREAKER"),
        ((770, 92, 900, 154), "VERI BAGI"),
    ]
    for box, label in blocks:
        draw.rounded_rectangle(box, radius=12, fill=fill, outline=outline, width=4)
        draw.text((box[0] + 18, box[1] + 22), label, fill=outline)

    for pts in [(184, 135, 250, 85), (184, 135, 250, 159), (430, 123, 510, 123), (712, 123, 770, 123)]:
        draw.line(pts, fill=outline, width=5)
        draw.polygon([(pts[2], pts[3]), (pts[2] - 18, pts[3] - 10), (pts[2] - 18, pts[3] + 10)], fill=outline)

    for box in [(110, 52, 156, 98), (330, 16, 376, 62), (330, 202, 376, 248), (606, 44, 652, 90)]:
        draw.rounded_rectangle(box, radius=8, outline=accent, width=5)

    return image


def build_hydraulic_loop_reference_image() -> Image.Image:
    image = Image.new("RGB", (940, 270), "white")
    draw = ImageDraw.Draw(image)
    outline = (28, 28, 28)
    accent = (203, 124, 37)
    fill = (245, 245, 245)

    blocks = [
        ((44, 96, 184, 162), "REZERVUAR"),
        ((236, 96, 376, 162), "POMPA"),
        ((428, 96, 612, 162), "ACTUATOR MANIFOLD"),
        ((674, 96, 866, 162), "FLAP / GEAR ACT."),
    ]
    for box, label in blocks:
        draw.rounded_rectangle(box, radius=12, fill=fill, outline=outline, width=4)
        draw.text((box[0] + 18, box[1] + 24), label, fill=outline)

    for x1, x2 in [(184, 236), (376, 428), (612, 674)]:
        y = 129
        draw.line((x1, y, x2, y), fill=outline, width=5)
        draw.polygon([(x2, y), (x2 - 18, y - 10), (x2 - 18, y + 10)], fill=outline)

    draw.line((770, 186, 116, 186), fill=outline, width=5)
    draw.line((116, 186, 116, 162), fill=outline, width=5)
    draw.text((326, 198), "RETURN LINE", fill=(80, 80, 80))

    for box in [(92, 50, 138, 96), (286, 50, 332, 96), (518, 50, 564, 96), (740, 50, 786, 96)]:
        draw.rounded_rectangle(box, radius=8, outline=accent, width=5)
    return image


def build_landing_gear_reference_image() -> Image.Image:
    image = Image.new("RGB", (920, 270), "white")
    draw = ImageDraw.Draw(image)
    outline = (28, 28, 28)
    accent = (203, 124, 37)

    draw.line((160, 52, 424, 52), fill=outline, width=6)
    draw.line((292, 52, 292, 126), fill=outline, width=6)
    draw.line((292, 126, 244, 214), fill=outline, width=6)
    draw.line((292, 126, 340, 214), fill=outline, width=6)
    draw.ellipse((218, 206, 270, 258), outline=outline, width=5)
    draw.ellipse((314, 206, 366, 258), outline=outline, width=5)
    draw.arc((206, 26, 378, 222), start=304, end=356, fill=accent, width=5)
    draw.arc((206, 26, 378, 222), start=182, end=236, fill=accent, width=5)
    draw.text((452, 46), "MAIN BEAM", fill=outline)
    draw.text((348, 132), "STRUT", fill=outline)
    draw.text((374, 218), "WHEEL", fill=outline)
    return image


def build_temperature_map_reference_image() -> Image.Image:
    image = Image.new("RGB", (920, 268), "white")
    draw = ImageDraw.Draw(image)
    outline = (28, 28, 28)
    colors = [(252, 215, 126), (249, 181, 87), (232, 126, 69), (208, 87, 63), (178, 55, 50)]

    draw.rounded_rectangle((220, 54, 706, 214), radius=18, outline=outline, width=4, fill=(245, 245, 245))
    draw.text((404, 66), "ENGINE BAY", fill=outline)
    nodes = [("T1", 280, 104, 0), ("T2", 410, 90, 1), ("T3", 552, 96, 3), ("T4", 312, 168, 2), ("T5", 530, 168, 4)]
    for label, x, y, color_idx in nodes:
        draw.ellipse((x - 28, y - 28, x + 28, y + 28), fill=colors[color_idx], outline=outline, width=3)
        draw.text((x + 36, y - 8), label, fill=outline)
    draw.text((238, 228), "Higher density indicates elevated residual heat after recovery.", fill=(80, 80, 80))
    return image


def build_comms_chain_reference_image() -> Image.Image:
    image = Image.new("RGB", (940, 268), "white")
    draw = ImageDraw.Draw(image)
    outline = (28, 28, 28)
    accent = (203, 124, 37)
    fill = (245, 245, 245)

    blocks = [
        ((34, 98, 184, 164), "PILOT"),
        ((246, 98, 396, 164), "GOREV"),
        ((458, 98, 640, 164), "RELAY / SATCOM"),
        ((726, 98, 886, 164), "UCAV"),
    ]
    for box, label in blocks:
        draw.rounded_rectangle(box, radius=12, fill=fill, outline=outline, width=4)
        draw.text((box[0] + 44, box[1] + 24), label, fill=outline)

    for x1, x2 in [(184, 246), (396, 458), (640, 726)]:
        y = 131
        draw.line((x1, y, x2, y), fill=outline, width=5)
        draw.polygon([(x2, y), (x2 - 18, y - 10), (x2 - 18, y + 10)], fill=outline)

    for box in [(88, 54, 134, 100), (300, 54, 346, 100), (540, 54, 586, 100), (790, 54, 836, 100)]:
        draw.rounded_rectangle(box, radius=8, outline=accent, width=5)

    draw.text((56, 194), "Voice test", fill=(80, 80, 80))
    draw.text((256, 194), "Target handover", fill=(80, 80, 80))
    draw.text((500, 194), "Latency check", fill=(80, 80, 80))
    draw.text((758, 194), "Ack return", fill=(80, 80, 80))
    return image


def build_pdf(pages: list[PDFPage]) -> bytes:
    objects: list[bytes] = []
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique >>")

    page_images: list[list[tuple[str, int]]] = []
    for page in pages:
        image_refs: list[tuple[str, int]] = []
        for image in page.images:
            compressed = zlib.compress(image.data)
            stream = (
                f"<< /Type /XObject /Subtype /Image /Width {image.width} /Height {image.height} "
                f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode /Length {len(compressed)} >>\nstream\n"
            ).encode("ascii") + compressed + b"\nendstream"
            objects.append(stream)
            image_refs.append((image.name, len(objects)))
        page_images.append(image_refs)

    stream_ids: list[int] = []
    for page in pages:
        stream_data = page.render().encode("latin-1", "replace")
        stream = f"<< /Length {len(stream_data)} >>\nstream\n".encode("ascii") + stream_data + b"endstream"
        objects.append(stream)
        stream_ids.append(len(objects))

    page_ids: list[int] = []
    pages_id = len(objects) + len(stream_ids) + 1
    for stream_id, image_refs in zip(stream_ids, page_images):
        xobject_clause = ""
        if image_refs:
            xobjects = " ".join(f"/{name} {object_id} 0 R" for name, object_id in image_refs)
            xobject_clause = f" /XObject << {xobjects} >>"
        page_obj = (
            f"<< /Type /Page /Parent {pages_id} 0 R "
            f"/MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 1 0 R /F2 2 0 R /F3 3 0 R >>{xobject_clause} >> "
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
    labels = localized_labels(spec.language)

    if spec.language == "tr":
        canvas = UnicodePDFCanvas(doc_code=doc_code, revision=revision, language=spec.language)
        canvas.header_block(
            document_class=infer_document_class(spec.filename, spec.language),
            doc_code=doc_code,
            title=spec.visible_title,
            revision=revision,
            date_text=date_display,
            english_title=spec.english_title,
            revision_note=spec.revision_note,
        )
        canvas.heading(labels["summary"], size=12, gap_after=6)
        canvas.paragraph(spec.summary, font="F1", size=10, leading=14, gap_after=8)
        canvas.heading(labels["operational_context"], size=12, gap_after=6)
        canvas.paragraph(spec.paragraph_one, font="F1", size=10, leading=14, gap_after=8)
        canvas.paragraph(spec.paragraph_two, font="F1", size=10, leading=14, gap_after=10)
        canvas.draw_table(spec.table_headers, spec.table_rows, title=spec.table_title)
        canvas.draw_diagram(title=spec.diagram_title, kind=spec.diagram_kind, caption=spec.diagram_caption)
        canvas.output(output_path)
        return

    canvas = PDFCanvas()
    canvas.header_block(
        document_class=infer_document_class(spec.filename, spec.language),
        doc_code=doc_code,
        title=spec.visible_title,
        revision=revision,
        date_text=date_display,
        language=spec.language,
        english_title=spec.english_title,
        revision_note=spec.revision_note,
    )
    canvas.heading(labels["summary"], size=12, gap_after=6)
    canvas.paragraph(spec.summary, font="F1", size=10, leading=14, gap_after=8)
    canvas.heading(labels["operational_context"], size=12, gap_after=6)
    canvas.paragraph(spec.paragraph_one, font="F1", size=10, leading=14, gap_after=8)
    canvas.paragraph(spec.paragraph_two, font="F1", size=10, leading=14, gap_after=10)
    canvas.draw_table(spec.table_headers, spec.table_rows, title=spec.table_title)
    canvas.draw_diagram(title=spec.diagram_title, kind=spec.diagram_kind, caption=spec.diagram_caption)
    canvas.footer(doc_code=doc_code, revision=revision)

    output_path.write_bytes(build_pdf(canvas.pages))


def collect_document_specs() -> dict[str, DocumentSpec]:
    specs = {}
    specs.update(english_documents())
    specs.update(turkish_documents())
    return specs


def load_manifest_filenames(meta_dir: Path) -> list[str]:
    with (meta_dir / "index.csv").open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [row["filename"] for row in reader]


def resolve_filenames(manifest_filenames: list[str], selected_filename: str | None) -> list[str]:
    if selected_filename is None:
        return manifest_filenames
    if selected_filename not in manifest_filenames:
        raise SystemExit(f"Requested filename is not listed in index.csv: {selected_filename}")
    return [selected_filename]


def english_documents() -> dict[str, DocumentSpec]:
    return {
        "AV_FL_NAV_CL_1001_Preflight_Checklist_R000_2026_04_10.pdf": DocumentSpec(
            filename="AV_FL_NAV_CL_1001_Preflight_Checklist_R000_2026_04_10.pdf",
            language="en",
            visible_title="Preflight Checklist",
            english_title=None,
            revision_note="Baseline issue establishing controlled release checks for apron launch, link readiness, and external-store safeing on the UCAV line.",
            summary="This checklist defines the minimum release standard for dispatching an armed unmanned aircraft from a dispersed operating strip before engine start and taxi. It is written for line crews, launch supervisors, and armament personnel who must certify that the air vehicle is structurally clean, mission-configured, and still in a provable weapon-safe state.",
            paragraph_one="The walk-around starts with aircraft electrical power isolated, intake and exhaust blanks removed under tool control, and all external stations confirmed mechanically safed. The line lead examines the EO-IR window, radome fasteners, wing-root access panels, landing gear servicing marks, and any visible torque witness marks around the SATCOM fairing or removable avionics covers.",
            paragraph_two="Release authority is not granted on observation alone. The launch supervisor records datalink availability, inertial alignment readiness, and station-safe status against the sortie packet, then confirms that the stores inhibit condition reported at the mission console matches the physical pin-and-cover state observed on the aircraft. Any mismatch forces an immediate hold and corrective entry before taxi clearance is reconsidered.",
            table_title="Flight Release Control Table",
            table_headers=["Step", "Control Point", "Acceptance Standard", "Release Action"],
            table_rows=[
                ["1", "EO-IR turret and nose bay", "Optics clear, no cracks or moisture film", "Clean, inspect, and log"],
                ["2", "External store stations", "Safe pins fitted and covers retained", "Witness and initial"],
                ["3", "Nose gear and tire servicing", "Pressure band and servicing marks visible", "Record serviceable"],
                ["4", "SATCOM and datalink fittings", "Fasteners secure, torque marks unbroken", "Authorize next check"],
            ],
            diagram_title="Release Inspection Layout",
            diagram_kind="uav_preflight",
            diagram_caption="Controlled preflight callout layout for the UCAV nose bay, SATCOM fairing, store stations, and nose gear service point.",
        ),
        "AV_FL_NAV_CL_1001_Preflight_Checklist_R001_2026_04_14.pdf": DocumentSpec(
            filename="AV_FL_NAV_CL_1001_Preflight_Checklist_R001_2026_04_14.pdf",
            language="en",
            visible_title="Preflight Checklist",
            english_title=None,
            revision_note="Dust-trial update adding EO-IR contamination inspection and mandatory thermal-cover accountability before release to taxi.",
            summary="This revision updates the release standard after dusty apron taxi trials demonstrated recurring residue on payload optics and inconsistent removal of thermal transport covers. The checklist now forces an explicit contamination inspection and positive cover-control verification before the aircraft is accepted for engine start and taxi handover.",
            paragraph_one="The line walk is still conducted with aircraft electrical power isolated, intake and exhaust blanks accounted for, and all external stations mechanically safed. In addition to the baseline structural checks, the line lead now inspects the EO-IR window for dust haze, abrasive scoring, and residue at the seal interface, then confirms that protective covers removed during transport have been tagged, counted, and transferred back to tool control.",
            paragraph_two="Release authority remains conditional on system and physical-state agreement. After battery-on, the launch supervisor verifies inertial alignment, datalink registration, and control-surface response, then withholds taxi release until the mission console records a clean optics status, positive stores inhibit telemetry, and a complete thermal-cover removal record tied to the sortie packet.",
            table_title="Flight Release Control Table",
            table_headers=["Step", "Control Point", "Acceptance Standard", "Release Action"],
            table_rows=[
                ["1", "EO-IR turret and lens seal", "No cracks, haze, or abrasive residue visible", "Clean, photograph, and log"],
                ["2", "External store stations", "Safe pins fitted and covers retained", "Witness and initial"],
                ["3", "Thermal transport covers", "All covers removed, tagged, and reconciled", "Cross-check with tool control"],
                ["4", "Datalink and release status", "Link active and console status agrees with physical state", "Authorize taxi review"],
            ],
            diagram_title="Release Inspection Layout",
            diagram_kind="uav_preflight",
            diagram_caption="Dust-trial revision layout emphasizing EO-IR contamination inspection and thermal-cover accountability before taxi release.",
        ),
        "AV_FL_NAV_CL_1001_Preflight_Checklist_R002_2026_04_17.pdf": DocumentSpec(
            filename="AV_FL_NAV_CL_1001_Preflight_Checklist_R002_2026_04_17.pdf",
            language="en",
            visible_title="Preflight Checklist",
            english_title=None,
            revision_note="Network-sortie revision adding SATCOM witness-mark verification, relay-health confirmation, and armament release consent before taxi.",
            summary="This revision finalizes the release sequence for long-range network-enabled sorties in which the UCAV depends on SATCOM relay continuity and a validated mission data package. The checklist now elevates SATCOM integrity, relay health, and armament consent from advisory checks to mandatory release gates that must be satisfied before taxi authority is issued.",
            paragraph_one="The line walk remains a controlled inspection with aircraft electrical power isolated, intake and exhaust blanks accounted for, and all external stations mechanically safed. In addition to the dusty-trial contamination checks, the line lead now verifies unbroken torque witness marks on the SATCOM fairing attachment points, confirms that relay-related access panels are properly secured, and records any disturbance to seals or fastener paint before power-up is authorized.",
            paragraph_two="After battery-on, the launch supervisor verifies inertial alignment, encrypted datalink registration, control-surface response, and stores inhibit telemetry, then checks the mission console for positive relay-health status and loaded-mission confirmation. Taxi authority is withheld until the armament officer signs the stores consent line for the uploaded sortie package and the console state agrees with the aircraft's observed safe configuration.",
            table_title="Flight Release Control Table",
            table_headers=["Step", "Control Point", "Acceptance Standard", "Release Action"],
            table_rows=[
                ["1", "EO-IR turret and nose bay", "Optics clear and contamination log closed", "Clean, verify, and log"],
                ["2", "SATCOM fairing witness marks", "Torque witness marks aligned and unbroken", "Record seal status"],
                ["3", "Relay health and mission load", "Console shows relay-ready and mission package valid", "Authorize final review"],
                ["4", "Armament release consent", "Signed by armament officer against sortie packet", "Issue taxi release"],
            ],
            diagram_title="Release Inspection Layout",
            diagram_kind="uav_preflight",
            diagram_caption="Final network-sortie release layout emphasizing SATCOM witness marks, relay readiness, and armament consent before taxi.",
        ),
        "SA_FL_INS_RP_1003_Safety_Inspection_Report_R000_2026_04_11.pdf": DocumentSpec(
            filename="SA_FL_INS_RP_1003_Safety_Inspection_Report_R000_2026_04_11.pdf",
            language="en",
            visible_title="Safety Inspection Report",
            english_title=None,
            revision_note="Initial issue documenting apron safety findings and corrective actions after an armed UAV turnaround rehearsal.",
            summary="This report records the results of a controlled apron safety inspection conducted during an armed UAV turnaround rehearsal involving refuel, stores-safe verification, and mission re-task preparation. The inspection focused on pedestrian separation, visible boundary control, and whether the aircraft stand remained unambiguous to both maintenance and armament personnel during high-tempo ground activity.",
            paragraph_one="The inspection team observed compliant use of wheel chocks, fire bottles, grounding leads, and headset discipline across the launch element. The primary deficiency was not a failure of equipment but a failure of stand presentation: the marked ground-crew lane behind the port wing narrowed where temporary stores and tool cases encroached into the pedestrian route, reducing clear movement space during the simulated loading sequence.",
            paragraph_two="A secondary finding established that the painted safe line remained physically present but became visually weak once night-preparation equipment was placed near the aircraft stand. The team therefore assessed the residual risk as procedural rather than structural and recommended repainting the lane boundary, adding two foldable warning boards, and enforcing a no-stow zone inside the clear arc whenever the aircraft is configured for armed ground handling.",
            table_title="Observed Safety Findings",
            table_headers=["Item", "Condition", "Risk", "Disposition"],
            table_rows=[
                ["A1", "Crew lane narrowed by staged equipment", "Medium", "Repaint and enforce no-stow zone"],
                ["A2", "Fire bottle and grounding placement correct", "Low", "Accept and retain layout"],
                ["A3", "Safe line visibility degraded at night setup", "Medium", "Add warning boards"],
                ["A4", "Weapon-safe tag and chock discipline correct", "Low", "Accept and monitor"],
            ],
            diagram_title="Safety Layout Reference",
            diagram_kind="safety_arc",
            diagram_caption="Apron safety reference showing the crew lane, safe line, and clear-arc boundary around the armed UAV stand.",
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
            visible_title="Motor Bakım Prosedürü",
            english_title="Engine Maintenance Procedure",
            revision_note="İlk yayın. Silahlı İHA motor yakıt hattı servisi, filtre değişimi ve purge akışı kontrollü bakım adımı olarak tanımlandı.",
            summary="Bu prosedür, silahlı insansız hava aracının motor yakıt hattında yapılan temel hat bakımını, filtre değişimini ve ilk çalıştırma öncesi purge sırasını tarif eder. Belge, uçuş hattı ekibinin saha koşullarında hızlı ama izlenebilir bir servis akışı uygulamasını sağlamak için kontrollü teknik referans olarak düzenlenmiştir.",
            paragraph_one="Bakım ekibi önce kanat içi tanktan filtre paketine kadar olan hatta gözle inceleme yapar, yakıt numunesi alır ve su, tortu veya renk bozulması görülürse işlemi derhal durdurur. Hortum, kelepçe ve bağlantı noktalarındaki tork boyası bütün olmalı; motora yakın esnek hatlarda sürtünme izi, gevşeme veya damlama görülmemelidir. Filtre gövdesi üzerindeki mühürlü kapaklar açılmadan önce saha bakım formu hazır bulundurulur.",
            paragraph_two="Filtre değişimi tamamlandıktan sonra prime pompasıyla hat doldurulur ve purge işlemi tanımlı süre boyunca uygulanır. İlk çalıştırma yalnızca yer emniyet subayı, görev konsolu operatörü ve bakım sorumlusu hazır olduğunda yapılır; rölanti değeri kararlı hâle gelmeden devir artışı denenmez ve motor girişinde anormal titreşim, yakıt kokusu veya basınç dalgalanması görülürse prosedür yeniden başlatılır.",
            table_title="Bakım Kontrol Tablosu",
            table_headers=["Adım", "Kontrol Noktası", "Kabul Kriteri", "Kayıt / İşlem"],
            table_rows=[
                ["1", "Tank numunesi", "Su yok, tortu yok, renk kararlı", "Numuneyi onayla"],
                ["2", "Filtre paketi", "Yeni eleman takılı ve mühürlü kapak kapalı", "Seri noyu yaz"],
                ["3", "Prime / purge akışı", "Hat dolu ve purge süresi 60 sn", "Süreyi kaydet"],
                ["4", "İlk rölanti kontrolü", "Kararlı, titreşim ve koku anomalisi yok", "Motor notunu işle"],
            ],
            diagram_title="Yakıt Akış Şeması",
            diagram_kind="engine_flow",
            diagram_caption="Silahlı İHA motor yakıt hattı temel servis akışı: tank, filtre, ölçüm birimi ve motor girişi.",
        ),
        "MT_EN_FUE_PR_1002_Engine_Maintenance_Procedure_R001_2026_04_13.pdf": DocumentSpec(
            filename="MT_EN_FUE_PR_1002_Engine_Maintenance_Procedure_R001_2026_04_13.pdf",
            language="tr",
            visible_title="Motor Bakım Prosedürü",
            english_title="Engine Maintenance Procedure",
            revision_note="Tozlu meydan testlerinden sonra filtre fark basınç kontrolü, uzatılmış purge ve ek servis kaydı zorunlu hâle getirildi.",
            summary="Bu revizyon, tozlu meydan operasyonlarında filtre yüklenmesinin ve hat içindeki ince partiküllerin daha erken yakalanabilmesi için temel motor yakıt hattı prosedürünü günceller. Fark basınç takibi artık yalnızca yardımcı bir gözlem değil, filtre değişimi ve purge öncesi yerine getirilmesi gereken resmî kontrol adımı olarak tanımlanmıştır.",
            paragraph_one="Bakım ekibi kanat içi tanktan filtre paketine kadar olan hattı gözle inceler, yakıt numunesi alır ve su, tortu veya renk bozulması görürse işlemi durdurur. Buna ek olarak filtre girişi ile çıkışı arasındaki fark basınç okunur; limit dışına çıkan değer, prime işlemine geçilmeden önce filtre paketinin yeniden değiştirilmesini ve hat bağlantı noktalarının ikinci kez kontrol edilmesini gerektirir.",
            paragraph_two="Filtre değişimi tamamlandıktan sonra prime pompasıyla hat doldurulur ve purge işlemi uzatılmış süre boyunca uygulanır. İlk çalıştırma yalnızca yer emniyet subayı, görev konsolu operatörü ve bakım sorumlusu hazır olduğunda yapılır; purge süresi bu revizyonda 75 saniyeye çıkarılmıştır ve rölanti kararlı hâle gelmeden önce filtre fark basınç kaydı forma işlenmeden sonraki adıma geçilmez.",
            table_title="Bakım Kontrol Tablosu",
            table_headers=["Adım", "Kontrol Noktası", "Kabul Kriteri", "Kayıt / İşlem"],
            table_rows=[
                ["1", "Tank numunesi", "Su yok, tortu yok, renk kararlı", "Numuneyi onayla"],
                ["2", "Filtre fark basıncı", "Limit içinde ve kayıt altında", "Değeri yaz"],
                ["3", "Prime / purge akışı", "Hat dolu ve purge süresi 75 sn", "Süreyi kaydet"],
                ["4", "Rölanti ve fark basınç kaydı", "Kararlı ve son okuma uyumlu", "Motor notunu işle"],
            ],
            diagram_title="Yakıt Akış Şeması",
            diagram_kind="engine_flow",
            diagram_caption="Revize motor yakıt hattı akışı, filtre fark basınç kontrolünü ve uzatılmış purge adımını vurgular.",
        ),
        "MT_EN_FUE_PR_1002_Engine_Maintenance_Procedure_R002_2026_04_16.pdf": DocumentSpec(
            filename="MT_EN_FUE_PR_1002_Engine_Maintenance_Procedure_R002_2026_04_16.pdf",
            language="tr",
            visible_title="Motor Bakım Prosedürü",
            english_title="Engine Maintenance Procedure",
            revision_note="Ağ destekli yüksek tempo görevler için bağlantı tork doğrulaması, 90 saniye purge ve görev öncesi son kayıt adımı zorunlu hâle getirildi.",
            summary="Bu son revizyon, silahlı İHA motor yakıt hattı prosedürünü ağ destekli yüksek tempo görevler için kesinleştirir. Filtre fark basınç kontrolü korunurken bağlantı tork doğrulaması, uzatılmış 90 saniyelik purge ve ilk rölanti sonrası son kayıt doğrulaması artık görev öncesi bakım serbestisinin ayrılmaz parçası olarak tanımlanmıştır.",
            paragraph_one="Bakım ekibi kanat içi tanktan filtre paketine kadar olan hattı gözle inceler, yakıt numunesi alır ve su, tortu veya renk bozulması görürse işlemi durdurur. Filtre girişi ile çıkışı arasındaki fark basınç okunur; buna ek olarak yakıt hattı kelepçe, rakor ve bağlantı noktalarındaki tork boyaları tek tek doğrulanır. Eksik iz, gevşeme şüphesi veya mühürlü bağlantıda bozulma varsa hat yeniden torklanmadan ve forma işlenmeden bir sonraki adıma geçilmez.",
            paragraph_two="Filtre değişimi tamamlandıktan sonra prime pompasıyla hat doldurulur ve purge işlemi bu revizyonda 90 saniye boyunca uygulanır. İlk çalıştırma yalnızca yer emniyet subayı, görev konsolu operatörü ve bakım sorumlusu hazır olduğunda yapılır; motor rölantide kararlı hâle geldikten sonra veri bağı durum ekranı, fark basınç son değeri ve tork kontrol kaydı aynı bakım formunda kapatılmadan görev paketine serbest bırakma verilmez.",
            table_title="Bakım Kontrol Tablosu",
            table_headers=["Adım", "Kontrol Noktası", "Kabul Kriteri", "Kayıt / İşlem"],
            table_rows=[
                ["1", "Tank numunesi", "Su yok, tortu yok, renk kararlı", "Numuneyi onayla"],
                ["2", "Bağlantı tork doğrulaması", "Tüm tork izleri tam ve bozulmamış", "Torku onayla"],
                ["3", "Prime / purge akışı", "Hat dolu ve purge süresi 90 sn", "Süreyi kaydet"],
                ["4", "Rölanti ve veri bağı durumu", "Kararlı, hata yok, son kayıt kapatıldı", "Motor notunu işle"],
            ],
            diagram_title="Yakıt Akış Şeması",
            diagram_kind="engine_flow",
            diagram_caption="Son revizyon motor yakıt hattı akışı, bağlantı tork doğrulamasını, filtre fark basıncı kontrolünü ve 90 saniyelik purge adımını vurgular.",
        ),
        "QA_EL_PWR_PL_1004_Avionics_Parts_List_R000_2026_04_08.pdf": DocumentSpec(
            filename="QA_EL_PWR_PL_1004_Avionics_Parts_List_R000_2026_04_08.pdf",
            language="tr",
            visible_title="Aviyonik Parça Listesi",
            english_title="Avionics Parts List",
            revision_note="İlk yayın. Silahlı İHA aviyonik güç dağıtımı ve görev bilgisayarı alt grupları izlenebilir parça listesi olarak tanımlandı.",
            summary="Bu belge, silahlı insansız hava aracının temel aviyonik güç dağıtım bileşenlerini ve görev bilgisayarıyla ilişkili kritik alt grupları izlenebilir bir kalite-parça listesi olarak sunar. Liste, depo kabulü, saha değişim kaydı ve seri numarası eşleştirmesi için ortak resmî referans olarak kullanılır.",
            paragraph_one="Parça listesi 28 V ana bus, görev bilgisayarı kartı, EO-IR görev yükü güç arayüzü ve veri bağı sigorta / röle modüllerini kapsar. Her kalem için kabul etiketi durumu, konfigürasyon seviyesi, son fonksiyon testi ve seri numarası kaydı birlikte tutulmalıdır; etiketi eksik veya mührü açılmış birim saha paketine dâhil edilmez.",
            paragraph_two="Kalite mühendisi saha stokundan çekilen her kalemi görev paketi, depo kaydı ve seri numarası cetveli ile tek tek karşılaştırır. Uyuşmayan seri numarası, açık kalmış breaker kartı veya test tarihi geçmiş modül için uygunsuzluk kaydı açılır; parça kullanımdan çekilir ve yerine yedek kabul birimi işlenmeden paket kapatılmaz.",
            table_title="Parça Envanter Tablosu",
            table_headers=["Kalem", "Alt Grup", "Miktar", "Durum / Kayıt"],
            table_rows=[
                ["P-11", "Görev bilgisayarı kartı", "2", "Kabul edildi / SN eşleşti"],
                ["P-24", "28 V bus röle modülü", "3", "Kabul edildi / Etiket tam"],
                ["P-32", "EO-IR güç arayüzü", "1", "İzleniyor / Test tekrarı"],
                ["P-47", "Veri bağı sigorta paketi", "4", "Kabul edildi / Mühür tam"],
            ],
            diagram_title="Güç Dağıtım Bloğu",
            diagram_kind="power_block",
            diagram_caption="Silahlı İHA aviyonik güç dağıtım bloklarını, görev bilgisayarı ve veri bağı besleme akışlarını gösterir.",
        ),
        "MT_HY_ACT_CL_1005_Hydraulic_System_Checklist_R000_2026_04_12.pdf": DocumentSpec(
            filename="MT_HY_ACT_CL_1005_Hydraulic_System_Checklist_R000_2026_04_12.pdf",
            language="en",
            visible_title="Hydraulic System Checklist",
            english_title=None,
            revision_note="Initial checklist formalizing post-repair hydraulic pressurization, leak inspection, and return-line temperature review.",
            summary="This checklist defines the controlled release sequence for the hydraulic loop that powers flap, brake, and landing-gear actuators on the armed unmanned aircraft. It is intended for post-repair maintenance release after hose replacement, actuator servicing, or any depressurization event that requires the loop to be re-verified before taxi.",
            paragraph_one="Technicians begin with reservoir servicing, cap-seal inspection, and a visual sweep of pressure and return lines from the pump manifold to the flap and gear actuators. Couplings must be dry, witness marks must remain aligned, and no metallic residue may be present in the return screen before electrical pump command is authorized.",
            paragraph_two="Once the pump is energized, the crew records nominal pressure rise, checks actuator timing, and compares return-line temperature behavior against the expected stabilization band. Any oscillation outside tolerance, visible seepage at a fitting, or temperature trend inconsistent with commanded movement requires immediate depressurization and repeat inspection before the loop may be accepted as serviceable.",
            table_title="Hydraulic Release Checklist",
            table_headers=["Step", "Control Point", "Acceptance Standard", "Release Action"],
            table_rows=[
                ["1", "Reservoir service level", "Cold-fill mark reached and seal intact", "Record and witness"],
                ["2", "Pump pressure rise", "Nominal pressure achieved without fluctuation", "Log reading"],
                ["3", "Actuator fittings", "Dry, torqued, and witness marks aligned", "Visual acceptance"],
                ["4", "Return-line temperature", "Stable trend after movement cycle", "Authorize release"],
            ],
            diagram_title="Hydraulic Loop Reference",
            diagram_kind="hydraulic_loop",
            diagram_caption="Hydraulic service layout from reservoir to actuator manifold and return line for post-repair release checks.",
        ),
        "AV_LG_LND_DG_1006_Landing_Gear_Diagram_Guide_R000_2026_04_07.pdf": DocumentSpec(
            filename="AV_LG_LND_DG_1006_Landing_Gear_Diagram_Guide_R000_2026_04_07.pdf",
            language="tr",
            visible_title="İniş Takımı Şeması Kılavuzu",
            english_title="Landing Gear Diagram Guide",
            revision_note="İlk yayın. Silahlı İHA ana iniş takımı geometrisi, amortisör uzaması ve teker hizası referansları tanımlandı.",
            summary="Bu kılavuz, silahlı insansız hava aracının ana iniş takımı geometrisini, açık konumdaki amortisör davranışını ve teker hizası referanslarını aynı teknik şema üzerinde toplar. Amaç, saha bakım ekibinin sert iniş veya acil geri dönüş sonrasında görsel karşılaştırmayı tek bir düzen üzerinden yapabilmesidir.",
            paragraph_one="Şemadaki ana kiriş, amortisör ve teker referansları; açık konumdaki takımın nominal hizasını temsil eder. Amortisör uzaması beklenen aralık dışına çıkarsa, yan destek boşluğunda asimetri oluşursa veya teker ekseni referans hattan saparsa uçuş öncesi manuel inceleme ve ek ölçüm gerekir.",
            paragraph_two="Kılavuz özellikle sert pistli geri dönüşler, uplock şüpheleri ve taraflı teker aşınması sonrasında kullanılır. Ekip şemayı fiziksel uçak üzerindeki referanslarla eşleştirir, gerekirse uplock, yan destek ve teker göbeği bölgelerinde ikincil kontrol talep eder ve sonrasında geometri kaydını forma işler.",
            table_title="Geometri Kontrol Tablosu",
            table_headers=["Nokta", "Kontrol Noktası", "Beklenen Durum", "Kayıt / Not"],
            table_rows=[
                ["G1", "Ana kiriş düzlemi", "Nominal eksenle uyumlu", "Görsel onay"],
                ["G2", "Amortisör uzaması", "Standart aralıkta", "Ölç ve yaz"],
                ["G3", "Teker hizası", "Simetrik ve sapmasız", "Görsel onay"],
                ["G4", "Yan destek / uplock", "Anormal boşluk yok", "Bakım notu"],
            ],
            diagram_title="İniş Takımı Referansı",
            diagram_kind="landing_gear",
            diagram_caption="Ana kiriş, amortisör ve teker referanslarıyla iniş takımı geometri karşılaştırması için kullanılan şema.",
        ),
        "SA_EN_TMP_RP_1007_Engine_Temperature_Log_R000_2026_04_15.pdf": DocumentSpec(
            filename="SA_EN_TMP_RP_1007_Engine_Temperature_Log_R000_2026_04_15.pdf",
            language="en",
            visible_title="Engine Temperature Log",
            english_title=None,
            revision_note="Initial issue formalizing post-flight engine-bay temperature capture and cooldown comparison after armed loiter recovery.",
            summary="This report captures the residual thermal condition of the engine bay after extended loiter and descent so that maintenance personnel can compare left-right cooling behavior and identify early evidence of duct blockage, shielding degradation, or abnormal fuel scheduling. The log is intended for immediate post-flight use while the aircraft remains in its controlled recovery configuration.",
            paragraph_one="After propeller stop, the maintenance observer records the designated engine-bay sensor values within two minutes while the aircraft remains pointed into wind and cowl panels stay closed. This first capture preserves a meaningful residual-heat distribution and prevents false gradients caused by premature cooling airflow across the upper deck and firewall area.",
            paragraph_two="A second capture is taken after ten minutes to compare cooldown spread and verify that previously elevated sensors are converging toward the expected pattern. If the upper-left and upper-right channels remain separated beyond the accepted delta, the crew inspects exhaust shielding, nozzle seal condition, harness routing, and any soot residue near the firewall-mounted brackets before the aircraft is released from thermal observation.",
            table_title="Temperature Capture Log",
            table_headers=["Sensor", "2 min", "10 min", "Status"],
            table_rows=[
                ["T1", "188 C", "132 C", "Normal"],
                ["T2", "194 C", "138 C", "Normal"],
                ["T3", "201 C", "149 C", "Watch"],
                ["T4", "176 C", "124 C", "Normal"],
            ],
            diagram_title="Sensor Heat Map",
            diagram_kind="temperature_map",
            diagram_caption="Engine-bay heat map reference showing the relative locations of the post-flight comparison sensors.",
        ),
        "QA_FL_COM_PR_1008_Cockpit_Communication_Test_Procedure_R000_2026_04_18.pdf": DocumentSpec(
            filename="QA_FL_COM_PR_1008_Cockpit_Communication_Test_Procedure_R000_2026_04_18.pdf",
            language="tr",
            visible_title="Kokpit Haberleşme Test Prosedürü",
            english_title="Cockpit Communication Test Procedure",
            revision_note="İlk yayın. Pilot, görev, röle ve UCAV arasındaki veri bağı zinciri test sırası resmî prosedür olarak tanımlandı.",
            summary="Bu prosedür, silahlı insansız hava aracı yer kontrol istasyonunda pilot konsolu, görev konsolu, röle / SATCOM katmanı ve hava aracı arasındaki haberleşme zincirini test etmek için hazırlanmıştır. Ses, veri aktarımı, gecikme kontrolü ve kabul geri dönüşü aynı sırada doğrulanarak görev öncesi iletişim serbestisi verilir.",
            paragraph_one="Test ekibi önce pilot konsolundan ses açma komutunu doğrular, ardından görev konsolundan hedef devri ve görev veri seti mesajını yollar. Röle veya SATCOM katmanında gecikme görülürse paket zaman damgaları kaydedilir; sistem hemen yeniden başlatılmaz, önce hatanın bağın hangi halkasında oluştuğu izole edilir ve fiziksel bağlantı durumu kontrol edilir.",
            paragraph_two="Araç tarafından gelen kabul mesajı ile birlikte stores inhibit, şifreleme durumu ve görev veri seti bayrakları da okunur. Eksik cevap, geciken onay veya hatalı durum bayrağında prosedür operatörü sesli tekrar yapmaya değil; konsol, röle ve UCAV arasındaki fiziksel bağlantı, anahtar yükleme ve SATCOM gecikme kaydını yeniden doğrulamaya yönlendirilir.",
            table_title="Haberleşme Test Tablosu",
            table_headers=["Adım", "Test Halkası", "Beklenen Sonuç", "Kayıt / İşlem"],
            table_rows=[
                ["1", "Pilot konsolu", "Ses açık ve cevap net", "Onay ver"],
                ["2", "Görev konsolu", "Hedef / veri mesajı geçti", "Zamanı yaz"],
                ["3", "Röle / SATCOM", "Gecikme limit içinde", "Ölç ve yaz"],
                ["4", "UCAV geri dönüşü", "Ack alındı ve bayraklar doğru", "Durumu işaretle"],
            ],
            diagram_title="Haberleşme Zinciri Referansı",
            diagram_kind="comms_chain",
            diagram_caption="Pilot, görev, röle ve UCAV arasındaki veri bağı zincirini ve test akış sırasını gösterir.",
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
    parser.add_argument(
        "--filename",
        help="Generate only the requested filename from index.csv.",
    )
    args = parser.parse_args()

    pool_dir = Path(args.pool_dir)
    meta_dir = Path(args.meta_dir)
    pool_dir.mkdir(parents=True, exist_ok=True)

    specs = collect_document_specs()
    manifest_filenames = load_manifest_filenames(meta_dir)

    if set(manifest_filenames) != set(specs):
        missing_specs = sorted(set(manifest_filenames) - set(specs))
        extra_specs = sorted(set(specs) - set(manifest_filenames))
        raise SystemExit(
            "Spec mismatch with index.csv. "
            f"Missing specs: {missing_specs}. Extra specs: {extra_specs}."
        )

    filenames = resolve_filenames(manifest_filenames, args.filename)
    for filename in filenames:
        render_document(specs[filename], pool_dir / filename)
        print(f"Generated {filename}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

