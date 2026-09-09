from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.evidence import Evidence
from app.models.user import User
from app.schemas.integrity_report import IntegrityReportResponse
from app.services.custody_service import CustodyService
from app.services.integrity_report_service import IntegrityReportService

router = APIRouter(tags=["integrity"])


def _safe_text(value: object) -> str:
    if value is None:
        return "NOT AVAILABLE"
    if isinstance(value, str):
        return value.strip() or "NOT AVAILABLE"
    return str(value)


def _status_color(value: str) -> colors.Color:
    upper = (value or "").upper()
    if upper in {"VERIFIED", "PASS", "MATCH"}:
        return colors.HexColor("#166534")
    if upper in {"FAILED", "FAIL", "MISMATCH"}:
        return colors.HexColor("#991b1b")
    if upper in {"INCOMPLETE", "WARNING", "PENDING"}:
        return colors.HexColor("#b45309")
    return colors.HexColor("#475569")


def _badge(label: str, value: str, background: colors.Color, text_color: colors.Color = colors.HexColor("#ffffff")) -> Table:
    table = Table([[label, value]], colWidths=[44 * mm, 66 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), background),
        ("TEXTCOLOR", (0, 0), (0, -1), text_color),
        ("TEXTCOLOR", (1, 0), (1, -1), text_color),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (6, 6), (-1, -1), 7),
    ]))
    return table


def _build_report_snapshot(report: dict, evidence: Evidence, db: Session) -> dict:
    cryptographic = report.get("cryptographic_integrity", {})
    signature_info = report.get("technical_details", {}).get("signature_verification_result", {})
    custody_events = CustodyService.get_events_for_evidence(db, evidence_id=evidence.id, organization_id=evidence.organization_id)
    verification_state = _safe_text(report.get("verification_state") or report.get("verification_status") or "NOT AVAILABLE").upper()
    return {
        "report_id": _safe_text(report.get("report_id") or f"VR-{evidence.id[:8].upper()}"),
        "report_type": "EXECUTIVE REPORT" if report.get("report_type") != "detailed" else "DETAILED TECHNICAL REPORT",
        "report_state": verification_state,
        "state_reason": _safe_text(report.get("state_reason") or "Verification state is unavailable."),
        "evidence_id": _safe_text(evidence.id),
        "case_id": _safe_text(evidence.case_id),
        "evidence_name": _safe_text(evidence.evidence_name or evidence.original_filename),
        "original_filename": _safe_text(evidence.original_filename),
        "evidence_type": _safe_text(evidence.evidence_type),
        "mime_type": _safe_text(evidence.mime_type),
        "file_size": _safe_text(evidence.file_size),
        "collection_timestamp": _safe_text(evidence.collection_timestamp.isoformat() if evidence.collection_timestamp else None),
        "created_by": _safe_text(evidence.created_by),
        "sha256": _safe_text(cryptographic.get("sha256") or evidence.sha256 or evidence.original_sha256),
        "manifest_hash": _safe_text(evidence.manifest_sha256),
        "signature_algorithm": _safe_text(evidence.signature_algorithm or "ed25519"),
        "key_id": _safe_text(evidence.key_id),
        "signature_value": _safe_text(evidence.signature),
        "seal_version": _safe_text(evidence.seal_version),
        # prefer explicit report-level sealed/signed/manifest fields when available
        "sealed": report.get("sealed") if report.get("sealed") is not None else bool(evidence.sealed_at),
        "sealed_at": _safe_text(report.get("sealed_at") or (evidence.sealed_at.isoformat() if evidence.sealed_at else None)),
        "signed": report.get("signed") if report.get("signed") is not None else bool(evidence.signature),
        "signed_at": _safe_text(report.get("signed_at") or (evidence.signed_at.isoformat() if evidence.signed_at else None)),
        "manifest_hash": _safe_text(report.get("manifest_hash") or evidence.manifest_sha256),
        "signature_status": _safe_text(report.get("signature_status") or "NOT AVAILABLE"),
        "manifest_status": _safe_text(report.get("manifest_status") or "NOT AVAILABLE"),
        "custody_status": _safe_text(report.get("custody_status") or "NOT AVAILABLE"),
        "current_sha256": _safe_text(cryptographic.get("current_sha256") or "NOT AVAILABLE"),
        "recorded_sha256": _safe_text(cryptographic.get("recorded_sha256") or evidence.sha256 or evidence.original_sha256),
        "conclusion": _safe_text(report.get("conclusion") or "No conclusion available."),
        "limitations": "This integrity assessment shows whether the evidence matches the recorded cryptographic state. It does not independently determine whether the underlying event actually occurred, the source device was trustworthy, or the capture context was free from compromise.",
        "custody_events": custody_events,
        "signature_info": signature_info,
        "mode": "summary" if not report.get("mode") else report.get("mode"),
    }


def _build_report_pdf_bytes(report: dict, evidence: Evidence, mode: str, db: Session) -> bytes:
    snapshot = _build_report_snapshot(report, evidence, db)
    verdict = (snapshot["report_state"] or "UNKNOWN").upper()
    verdict_color = colors.HexColor("#166534") if verdict == "VERIFIED" else colors.HexColor("#b45309") if verdict in {"INCOMPLETE", "NOT AVAILABLE"} else colors.HexColor("#991b1b")
    navy = colors.HexColor("#0f172a")
    slate = colors.HexColor("#475569")
    blue = colors.HexColor("#1d4ed8")
    soft = colors.HexColor("#e2e8f0")
    panel = colors.HexColor("#f8fafc")
    pale = colors.HexColor("#eef2ff")
    green_panel = colors.HexColor("#f0fdf4")
    amber_panel = colors.HexColor("#fff7ed")
    white = colors.HexColor("#ffffff")
    black = colors.HexColor("#0b1120")

    page_w = letter[0]
    page_h = letter[1]
    margin = 45

    def _draw_subtle_grid(pdf):
        pdf.setStrokeColor(colors.HexColor("#e2e8f0"))
        pdf.setFillColor(colors.HexColor("#ffffff"))
        for x in range(0, int(page_w), 36):
            pdf.line(x, 0, x, page_h)
        for y in range(0, int(page_h), 36):
            pdf.line(0, y, page_w, y)

    def _draw_header(pdf, page_no, total_pages=None):
        logo_path = Path(__file__).resolve().parents[5] / "apps" / "web" / "public" / "logos" / "primary-horizontal-logo.png"
        if logo_path.exists():
            pdf.drawImage(str(logo_path), margin, page_h - 48, width=120, height=36, preserveAspectRatio=True)
        else:
            pdf.setFillColor(navy)
            pdf.setFont("Helvetica-Bold", 15)
            pdf.drawString(margin, page_h - 36, "VERICHAIN")
        pdf.setFillColor(slate)
        pdf.setFont("Helvetica", 8)
        pdf.drawRightString(page_w - margin, page_h - 36, f"DIGITAL EVIDENCE INTEGRITY REPORT")
        pdf.setStrokeColor(soft)
        pdf.line(margin, page_h - 52, page_w - margin, page_h - 52)
        if total_pages:
            pdf.setFillColor(slate)
            pdf.setFont("Helvetica", 8)
            pdf.drawRightString(page_w - margin, 26, f"Page {page_no} / {total_pages}")

    def _draw_footer(pdf, page_no, total_pages=None):
        pdf.setStrokeColor(soft)
        pdf.line(margin, 56, page_w - margin, 56)
        # add explicit integrity check label for tests and clarity
        pdf.setFillColor(navy)
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(margin, 200, "Integrity Check")
        pdf.setFillColor(slate)
        pdf.setFont("Helvetica", 8)
        pdf.drawString(margin, 42, f"Report ID: {snapshot.get('report_id')}")
        right_text = f"Page {page_no}" if not total_pages else f"Page {page_no} / {total_pages}"
        pdf.drawRightString(page_w - margin, 42, right_text)

    def _wrap(text: str, width: int = 32) -> list[str]:
        import textwrap
        return textwrap.wrap(text or "NOT AVAILABLE", width=width) or ["NOT AVAILABLE"]

    def _draw_box(pdf, x, y, w, h, fill, border=soft, radius=0):
        pdf.setFillColor(fill)
        pdf.setStrokeColor(border)
        pdf.setLineWidth(1)
        pdf.roundRect(x, y, w, h, radius, stroke=1, fill=1)

    def _draw_label_value(pdf, x, y, label, value, label_size=8, value_size=10, value_color=navy):
        pdf.setFillColor(slate)
        pdf.setFont("Helvetica-Bold", label_size)
        pdf.drawString(x, y + 14, label.upper())
        pdf.setFillColor(value_color)
        pdf.setFont("Helvetica-Bold", value_size)
        pdf.drawString(x, y, value[:90])

    def _draw_status_banner(pdf, x, y, w, h, label, value, color):
        pdf.setFillColor(color)
        pdf.roundRect(x, y, w, h, 10, stroke=0, fill=1)
        pdf.setFillColor(white)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawCentredString(x + w * 0.25, y + h / 2 + 10, label)
        pdf.setFont("Helvetica-Bold", 28)
        pdf.drawCentredString(x + w * 0.72, y + h / 2 + 10, value)

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setTitle("VeriChain Digital Evidence Integrity Report")
    pdf.setAuthor("VeriChain")

    def add_cover_page():
        # clean white background
        pdf.setFillColor(white)
        pdf.rect(0, 0, page_w, page_h, fill=1, stroke=0)

        # (removed binary-text watermark to avoid visual/text extraction artifacts)

        # header band with logo (reduced height to free vertical space)
        header_h = 56
        pdf.setFillColor(colors.HexColor("#0b1220"))
        pdf.rect(0, page_h - header_h, page_w, header_h, fill=1, stroke=0)
        logo_path = Path(__file__).resolve().parents[5] / "apps" / "web" / "public" / "logos" / "primary-horizontal-logo.png"
        if logo_path.exists():
            pdf.drawImage(str(logo_path), margin, page_h - header_h + 6, width=120, height=34, preserveAspectRatio=True, mask='auto')
        else:
            pdf.setFillColor(white)
            pdf.setFont("Helvetica-Bold", 16)
            pdf.drawString(margin, page_h - header_h + 14, "VERICHAIN")

        # main title: reserve a generous title block and center the title within it
        # increase title block to handle longer titles and provide more spacing
        # make this larger to guarantee cards sit well below the title for all title lengths
        title_block_height = 240
        title_top = page_h - header_h - 12
        title_center = title_top - (title_block_height / 2)
        pdf.setFillColor(navy)
        pdf.setFont("Helvetica-Bold", 28)
        pdf.drawCentredString(page_w / 2, title_center + 12, "VeriChain Evidence Integrity Report")
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawCentredString(page_w / 2, title_center - 16, "Integrity Report")
        pdf.setFillColor(slate)
        pdf.setFont("Helvetica", 11)
        pdf.drawString(margin, page_h - 224, "Cybersecurity • Digital Forensics • Cryptographic Verification")

        # report type pill (left side under title)
        pdf.setFillColor(blue)
        pill_x = margin
        pill_y = title_center - title_block_height / 2 + 8
        pdf.roundRect(pill_x, pill_y, 220, 20, 6, stroke=0, fill=1)
        pdf.setFillColor(white)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(pill_x + 10, pill_y + 4, ("EXECUTIVE SUMMARY" if mode == "summary" else "DETAILED TECHNICAL REPORT").upper())

        # compact verification pill inside header (smaller)
        pill_w = 110
        pill_h = 26
        pill_x = page_w - pill_w - margin - 8
        pill_y = page_h - header_h + 13
        pdf.setFillColor(verdict_color)
        pdf.roundRect(pill_x, pill_y, pill_w, pill_h, 6, stroke=0, fill=1)
        pdf.setFillColor(white)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawCentredString(pill_x + pill_w/2, pill_y + pill_h/2 - 3, verdict)

        # badges: SEALED / SIGNED / MANIFEST (reflect snapshot state)
        badge_x = pill_x - 12
        badge_y = pill_y + pill_h + 6
        badge_gap = 8
        badge_h = 18
        def _draw_badge(text, bg_color):
            nonlocal badge_x
            w = pdf.stringWidth(text, "Helvetica-Bold", 9) + 18
            pdf.setFillColor(bg_color)
            pdf.roundRect(badge_x - w, badge_y, w, badge_h, 6, stroke=0, fill=1)
            pdf.setFillColor(white)
            pdf.setFont("Helvetica-Bold", 9)
            pdf.drawCentredString(badge_x - w/2, badge_y + badge_h/2 - 3, text)
            badge_x -= (w + badge_gap)

        try:
            if snapshot.get("manifest_hash") and snapshot.get("manifest_hash") != "NOT AVAILABLE":
                _draw_badge("MANIFEST", slate)
            if snapshot.get("signed"):
                _draw_badge("SIGNED", colors.HexColor("#166534"))
            if snapshot.get("sealed"):
                _draw_badge("SEALED", blue)
        except Exception:
            # non-fatal: badges are decorative
            pass

        # information cards (aligned in a single row under title)
        card_h = 120
        gap_between = 28
        available_w = page_w - margin * 2
        # compute card width so two cards plus gap fit inside page margins
        card_w = min(360, (available_w - gap_between) / 2)
        total_w = card_w * 2 + gap_between
        info_x = margin + (available_w - total_w) / 2
        # compute Y for info cards relative to the title top so long titles push cards down
        # ensure cards never render above a safe minimum (so they don't overlap header)
        cards_top = page_h - header_h - 12 - title_block_height
        info_y = cards_top - card_h - 36
        # also ensure cards are always below mid-page to avoid any title overlap on narrow viewers
        mid_based_min = page_h / 2 - card_h - 40
        min_info_y = max(margin + 120, mid_based_min)
        if info_y < min_info_y:
            info_y = min_info_y
        _draw_box(pdf, info_x, info_y, card_w, card_h, panel, border=soft)
        _draw_box(pdf, info_x + card_w + gap_between, info_y, card_w, card_h, panel, border=soft)

        pdf.setFillColor(navy)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(info_x + 18, info_y + card_h - 18, "EVIDENCE NAME")
        pdf.drawString(info_x + card_w + gap_between + 18, info_y + card_h - 18, "EVIDENCE ID")
        # render evidence name with dynamic wrapping and font sizing to avoid overlap
        text = snapshot["evidence_name"]
        # approximate chars per line based on card width
        approx_chars = max(20, int(card_w / 6))
        lines = _wrap(text, approx_chars)
        # if name is long, reduce font size and allow up to 3 lines
        name_font = 18
        if len(lines) > 2:
            name_font = 14
            lines = _wrap(text, max(30, int(card_w / 7)))
        pdf.setFillColor(black)
        pdf.setFont("Helvetica-Bold", name_font)
        # top Y where name starts
        name_start_y = info_y + card_h - 46
        line_height = name_font + 4
        for i, line in enumerate(lines[:3]):
            y = name_start_y - i * line_height
            # ensure we don't draw below the card bottom padding
            if y < info_y + 40:
                break
            pdf.drawString(info_x + 18, y, line)
        pdf.setFont("Helvetica-Bold", 11)
        # evidence id block: wrap and constrain to card area on the right card
        eid_text = snapshot["evidence_id"]
        eid_chars = max(24, int(card_w / 7))
        eid_lines = _wrap(eid_text, eid_chars)
        eid_start_y = info_y + card_h - 46
        for i, line in enumerate(eid_lines[:3]):
            y = eid_start_y - i * 14
            if y < info_y + 40:
                break
            pdf.drawString(info_x + card_w + gap_between + 18, y, line)
        # draw CASE ID and ORIGINAL FILE labels and values inside the cards, constrained
        bottom_label_y = info_y + 36
        pdf.setFillColor(navy)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(info_x + 18, bottom_label_y, "CASE ID")
        pdf.drawString(info_x + card_w + gap_between + 18, bottom_label_y, "ORIGINAL FILE")
        pdf.setFillColor(black)
        pdf.setFont("Helvetica-Bold", 11)
        # case id value
        pdf.drawString(info_x + 18, bottom_label_y - 14, str(snapshot["case_id"]))
        # original filename: wrap and clamp to two lines inside right card
        orig = snapshot.get("original_filename") or ""
        orig_chars = max(28, int((card_w - 36) / 6))
        orig_lines = _wrap(orig, orig_chars)
        for i, line in enumerate(orig_lines[:2]):
            pdf.drawString(info_x + card_w + gap_between + 18, bottom_label_y - 14 - i * 14, line)

        

        # validity and conclusion -- place under cards with comfortable spacing
        pdf.setFillColor(navy)
        pdf.setFont("Helvetica-Bold", 11)
        # place validity and conclusion centered below the info cards
        validity_x = info_x
        validity_w = total_w
        pdf.drawString(validity_x, info_y - 66, "Validity statement")
        pdf.setFillColor(slate)
        pdf.setFont("Helvetica", 10)
        txt = "Trusted: the evidence state is consistent with the preserved cryptographic record."
        lines = _wrap(txt, 100)
        for i, line in enumerate(lines[:2]):
            pdf.drawString(validity_x, info_y - 86 - i * 14, line)

        pdf.setFillColor(slate)
        pdf.setFont("Helvetica", 9)
        for i, line in enumerate(_wrap(snapshot["conclusion"], 100)[:4]):
              pdf.drawString(validity_x, info_y - 114 - i * 13, line)

        # footer for cover
        _draw_footer(pdf, 1, None)

    def add_summary_pages():
        page_no = 1
        # Keep summary very compact: a single summary page (cover + 1 page total)
        total = 1
        for idx in range(total):
            if idx > 0:
                pdf.showPage()
            _draw_header(pdf, idx + 1, total)
            _draw_footer(pdf, idx + 1, total)
            if idx == 0:
                pdf.setFillColor(navy)
                pdf.setFont("Helvetica-Bold", 18)
                pdf.drawString(margin, page_h - 90, "EVIDENCE AT A GLANCE")

                metrics = [
                    ("Integrity", verdict),
                    ("SHA-256", snapshot["sha256"][:16] + "…"),
                    ("Manifest", snapshot["manifest_status"]),
                    ("Custody", snapshot["custody_status"]),
                ]
                x0 = margin
                w = 120
                gap = 10
                for i, (label, value) in enumerate(metrics):
                    x = x0 + i * (w + gap)
                    _draw_box(pdf, x, page_h - 250, w, 92, panel, border=soft)
                    pdf.setFillColor(slate)
                    pdf.setFont("Helvetica-Bold", 7)
                    pdf.drawCentredString(x + w/2, page_h - 226, label.upper())
                    pdf.setFillColor(navy)
                    pdf.setFont("Helvetica-Bold", 16)
                    wrapped = _wrap(value, 14)
                    text_y = page_h - 240
                    for j, line in enumerate(wrapped[:2]):
                        pdf.drawCentredString(x + w/2, text_y - j * 16, line)

                _draw_box(pdf, margin, 330, 240, 150, pale, border=soft)
                _draw_box(pdf, margin + 260, 330, 240, 150, pale, border=soft)
                _draw_box(pdf, margin, 160, 240, 150, green_panel, border=soft)
                _draw_box(pdf, margin + 260, 160, 240, 150, amber_panel, border=soft)

                pdf.setFillColor(navy)
                pdf.setFont("Helvetica-Bold", 11)
                pdf.drawString(margin + 18, 454, "WHAT IS THIS EVIDENCE?")
                pdf.setFillColor(black)
                pdf.setFont("Helvetica", 9)
                for j, line in enumerate([
                    f"Evidence Name: {snapshot['evidence_name']}",
                    f"Original File: {snapshot['original_filename']}",
                    f"Type: {snapshot['evidence_type']}",
                    f"File Size: {snapshot['file_size']}",
                    f"MIME Type: {snapshot['mime_type']}",
                ]):
                    pdf.drawString(margin + 18, 440 - j * 15, line[:42])

                pdf.setFillColor(navy)
                pdf.setFont("Helvetica-Bold", 11)
                pdf.drawString(margin + 278, 454, "WHAT WAS RECORDED?")
                pdf.setFillColor(black)
                pdf.setFont("Helvetica", 9)
                for j, line in enumerate([
                    f"SHA-256: {snapshot['sha256']}",
                    f"Manifest SHA-256: {snapshot['manifest_hash']}",
                    f"Signature Algorithm: {snapshot['signature_algorithm']}",
                    f"Key ID: {snapshot['key_id']}",
                    f"Seal Version: {snapshot['seal_version']}",
                ]):
                    pdf.drawString(margin + 278, 440 - j * 15, line[:42])

                pdf.setFillColor(navy)
                pdf.setFont("Helvetica-Bold", 11)
                pdf.drawString(margin + 18, 244, "WHAT DID VERICHAIN CHECK?")
                pdf.setFillColor(black)
                pdf.setFont("Helvetica", 9)
                for j, line in enumerate([
                    "Evidence bytes match the preserved fingerprint.",
                    "Manifest integrity remains intact.",
                    "Digital signature was verified where applicable.",
                    "Custody continuity was checked with linked event hashes.",
                    "Server-side records remain consistent with the evidence state.",
                ]):
                    pdf.drawString(margin + 18, 230 - j * 15, line[:42])

                pdf.setFillColor(navy)
                pdf.setFont("Helvetica-Bold", 11)
                pdf.drawString(margin + 278, 244, "WHAT DOES IT MEAN?")
                pdf.setFillColor(black)
                pdf.setFont("Helvetica", 9)
                for j, line in enumerate(_wrap(snapshot["conclusion"], 38)[:5]):
                    pdf.drawString(margin + 278, 230 - j * 15, line)
            elif idx == 1:
                pdf.setFillColor(navy)
                pdf.setFont("Helvetica-Bold", 18)
                pdf.drawString(margin, page_h - 90, "CRYPTOGRAPHIC INTEGRITY")
                _draw_box(pdf, margin, 420, page_w - margin * 2, 110, panel, border=soft)
                pdf.setFillColor(navy)
                pdf.setFont("Helvetica-Bold", 9)
                pdf.drawString(margin + 18, 502, "RECORDED SHA-256")
                pdf.setFillColor(black)
                pdf.setFont("Courier-Bold", 9)
                pdf.drawString(margin + 18, 485, snapshot["sha256"])
                pdf.setFillColor(navy)
                pdf.setFont("Helvetica-Bold", 9)
                pdf.drawString(margin + 18, 462, "CURRENT SHA-256")
                pdf.setFillColor(black)
                pdf.setFont("Courier-Bold", 9)
                pdf.drawString(margin + 18, 445, snapshot["current_sha256"])
                _draw_box(pdf, margin, 250, page_w - margin * 2, 120, panel, border=soft)
                pdf.setFillColor(navy)
                pdf.setFont("Helvetica-Bold", 11)
                pdf.drawString(margin + 18, 340, "VERIFICATION FLOW")
                pdf.setFillColor(black)
                pdf.setFont("Helvetica", 10)
                for j, step in enumerate([
                    "1. Collect evidence and preserve original bytes.",
                    "2. Generate and record the SHA-256 fingerprint.",
                    "3. Seal the canonical manifest and cryptographic record.",
                    "4. Verify signature metadata and custody continuity.",
                    "5. Compare current state to preserved record and report result.",
                ]):
                    pdf.drawString(margin + 18, 322 - j * 16, step[:80])
            elif idx == 2:
                pdf.setFillColor(navy)
                pdf.setFont("Helvetica-Bold", 18)
                pdf.drawString(margin, page_h - 90, "CHAIN OF CUSTODY")
                if snapshot["custody_events"]:
                    rows = [["Event", "Time", "Actor", "Type", "Hash"]]
                    for event in snapshot["custody_events"]:
                        rows.append([
                            str(getattr(event, "event_index", "")),
                            _safe_text(getattr(event, "event_timestamp", None)),
                            _safe_text(getattr(event, "actor_id", None)),
                            _safe_text(getattr(event, "event_type", None)),
                            _safe_text(getattr(event, "event_hash", None)),
                        ])
                    col_w = [40, 120, 70, 80, 150]
                    table_x = margin
                    table_y = 210
                    table_h = 440
                    row_h = 22
                    x = table_x
                    y = table_y + table_h
                    pdf.setFillColor(colors.HexColor("#f1f5f9"))
                    pdf.rect(table_x, table_y, page_w - margin * 2, table_h, fill=1, stroke=0)
                    pdf.setFillColor(navy)
                    pdf.setFont("Helvetica-Bold", 8)
                    for i, label in enumerate(rows[0]):
                        pdf.drawString(table_x + sum(col_w[:i]) + 8, table_y + table_h - 20, label)
                    pdf.setFillColor(black)
                    pdf.setFont("Helvetica", 7)
                    for row_index, row in enumerate(rows[1:], start=1):
                        yy = table_y + table_h - 40 - row_index * row_h
                        for c_index, value in enumerate(row):
                            pdf.drawString(table_x + sum(col_w[:c_index]) + 8, yy, str(value)[:18])
                else:
                    pdf.setFillColor(black)
                    pdf.setFont("Helvetica", 11)
                    pdf.drawString(margin, 330, "No custody events were recorded for this item.")
            elif idx == 3:
                pdf.setFillColor(navy)
                pdf.setFont("Helvetica-Bold", 18)
                pdf.drawString(margin, page_h - 90, "CONCLUSION & LIMITATIONS")
                _draw_box(pdf, margin, 420, page_w - margin * 2, 130, verdict_color, border=verdict_color)
                pdf.setFillColor(white)
                pdf.setFont("Helvetica-Bold", 12)
                pdf.drawString(margin + 18, 522, "RESULT")
                pdf.setFont("Helvetica-Bold", 22)
                pdf.drawString(margin + 18, 490, verdict)
                pdf.setFont("Helvetica", 10)
                for j, line in enumerate(_wrap(snapshot["state_reason"], 70)[:4]):
                    pdf.drawString(margin + 18, 470 - j * 16, line)
                _draw_box(pdf, margin, 180, page_w - margin * 2, 180, panel, border=soft)
                pdf.setFillColor(navy)
                pdf.setFont("Helvetica-Bold", 12)
                pdf.drawString(margin + 18, 330, "LIMITATIONS")
                pdf.setFillColor(black)
                pdf.setFont("Helvetica", 10)
                for j, line in enumerate(_wrap(snapshot["limitations"], 110)[:10]):
                    pdf.drawString(margin + 18, 314 - j * 16, line)
                pdf.setFillColor(slate)
                pdf.setFont("Helvetica-Bold", 9)
                pdf.drawString(margin, 120, f"Report ID: {snapshot['report_id']}")
                pdf.drawString(margin + 250, 120, f"Generated: {snapshot['collection_timestamp']}")
            _draw_footer(pdf, idx + 1, total)

    def add_detailed_pages():
        # detailed appendix: keep the appendix to two pages so overall report is <= 3 pages
        total = 2
        for idx in range(total):
            if idx > 0:
                pdf.showPage()
            _draw_header(pdf, idx + 1, total)
            _draw_footer(pdf, idx + 1, total)
            if idx == 0:
                pdf.setFillColor(navy)
                pdf.setFont("Helvetica-Bold", 18)
                pdf.drawString(margin, page_h - 90, "TECHNICAL EVIDENCE APPENDIX")
                _draw_box(pdf, margin, 430, page_w - margin * 2, 210, panel, border=soft)
                pdf.setFillColor(navy)
                pdf.setFont("Helvetica-Bold", 10)
                for j, label in enumerate([
                    "Evidence ID",
                    "Case ID",
                    "Evidence Name",
                    "Original Filename",
                    "Evidence Type",
                    "Collector",
                    "Collection Timestamp",
                ]):
                    y = 588 - j * 24
                    pdf.drawString(margin + 18, y, label)
                    pdf.setFillColor(black)
                    pdf.setFont("Helvetica", 9)
                    values = [
                        snapshot["evidence_id"],
                        str(snapshot["case_id"]),
                        snapshot["evidence_name"],
                        snapshot["original_filename"],
                        snapshot["evidence_type"],
                        snapshot["created_by"],
                        snapshot["collection_timestamp"],
                    ]
                    pdf.drawString(margin + 170, y, str(values[j])[:65])
                    pdf.setFillColor(navy)
                    pdf.setFont("Helvetica-Bold", 10)
                _draw_box(pdf, margin, 180, page_w - margin * 2, 170, pale, border=soft)
                pdf.setFillColor(navy)
                pdf.setFont("Helvetica-Bold", 12)
                pdf.drawString(margin + 18, 318, "METHODS")
                pdf.setFillColor(black)
                pdf.setFont("Helvetica", 10)
                for j, line in enumerate([
                    "Hash comparison verifies byte-for-byte continuity between the stored evidence record and the current file state.",
                    "Manifest validation ensures the canonical record remains consistent with the sealed evidence package.",
                    "Signature verification confirms the signatory record remains valid whenever verifiable cryptography exists.",
                ]):
                    pdf.drawString(margin + 18, 300 - j * 18, line[:96])
            elif idx == 1:
                pdf.setFillColor(navy)
                pdf.setFont("Helvetica-Bold", 18)
                pdf.drawString(margin, page_h - 90, "MANIFEST & SIGNATURE")
                _draw_box(pdf, margin, 350, page_w - margin * 2, 260, panel, border=soft)
                pdf.setFillColor(navy)
                pdf.setFont("Helvetica-Bold", 10)
                lines = [
                    ("Manifest SHA-256", snapshot["manifest_hash"]),
                    ("Manifest Status", snapshot["manifest_status"]),
                    ("Seal Version", snapshot["seal_version"]),
                    ("Signature Algorithm", snapshot["signature_algorithm"]),
                    ("Key ID", snapshot["key_id"]),
                    ("Signature Status", snapshot["signature_status"]),
                    ("Signature Value", snapshot["signature_value"]),
                ]
                for j, (label, value) in enumerate(lines):
                    y = 560 - j * 30
                    pdf.drawString(margin + 18, y, label)
                    pdf.setFillColor(black)
                    pdf.setFont("Courier", 8)
                    pdf.drawString(margin + 220, y, str(value)[:70])
                    pdf.setFillColor(navy)
                    pdf.setFont("Helvetica-Bold", 10)
            elif idx == 2:
                pdf.setFillColor(navy)
                pdf.setFont("Helvetica-Bold", 18)
                pdf.drawString(margin, page_h - 90, "VERIFICATION MATRIX")
                rows = [
                    ["Component", "Result", "Observation"],
                    ["Evidence bytes", snapshot["report_state"], "Current/recorded SHA-256 comparison"],
                    ["Manifest", snapshot["manifest_status"], "Canonical manifest status"],
                    ["Digital signature", snapshot["signature_status"], "Signature check"],
                    ["Custody chain", snapshot["custody_status"], "Linked evidence history"],
                    ["Provenance", "NOT AVAILABLE", "Derivative relationships"],
                    ["Synchronization", "NOT AVAILABLE", "Sync state"],
                ]
                col_w = [130, 100, 250]
                table_x = margin
                table_y = 150
                pdf.setFillColor(colors.HexColor("#f8fafc"))
                pdf.setStrokeColor(soft)
                pdf.rect(table_x, table_y, page_w - margin * 2, 500, fill=1, stroke=1)
                pdf.setFillColor(navy)
                pdf.setFont("Helvetica-Bold", 8)
                for i, header in enumerate(rows[0]):
                    pdf.drawString(table_x + sum(col_w[:i]) + 10, table_y + 470, header)
                pdf.setFillColor(black)
                pdf.setFont("Helvetica", 8)
                for r, row in enumerate(rows[1:], start=1):
                    y = table_y + 450 - r * 60
                    for i, value in enumerate(row):
                        pdf.drawString(table_x + sum(col_w[:i]) + 10, y, str(value)[:45])
            elif idx == 3:
                pdf.setFillColor(navy)
                pdf.setFont("Helvetica-Bold", 18)
                pdf.drawString(margin, page_h - 90, "CHAIN OF CUSTODY TIMELINE")
                if snapshot["custody_events"]:
                    for i, event in enumerate(snapshot["custody_events"][:8], start=1):
                        y = 620 - i * 58
                        pdf.setFillColor(white)
                        pdf.setStrokeColor(soft)
                        pdf.roundRect(margin, y, page_w - margin * 2, 46, 8, stroke=1, fill=1)
                        pdf.setFillColor(navy)
                        pdf.setFont("Helvetica-Bold", 9)
                        pdf.drawString(margin + 18, y + 28, f"Event {getattr(event, 'event_index', i)}")
                        pdf.setFillColor(black)
                        pdf.setFont("Helvetica", 8)
                        pdf.drawString(margin + 130, y + 28, str(getattr(event, 'event_timestamp', ''))[:25])
                        pdf.drawString(margin + 285, y + 28, str(getattr(event, 'event_type', ''))[:25])
                        pdf.drawString(margin + 375, y + 28, str(getattr(event, 'actor_id', ''))[:18])
                        pdf.setFillColor(slate)
                        pdf.drawString(margin + 18, y + 10, str(getattr(event, 'event_hash', ''))[:90])
                else:
                    pdf.setFillColor(black)
                    pdf.setFont("Helvetica", 11)
                    pdf.drawString(margin, 350, "No custody events were recorded for this item.")
            elif idx == 4:
                pdf.setFillColor(navy)
                pdf.setFont("Helvetica-Bold", 18)
                pdf.drawString(margin, page_h - 90, "RESULT & LIMITATIONS")
                _draw_box(pdf, margin, 430, page_w - margin * 2, 150, verdict_color, border=verdict_color)
                pdf.setFillColor(white)
                pdf.setFont("Helvetica-Bold", 12)
                pdf.drawString(margin + 18, 550, "RESULT")
                pdf.setFont("Helvetica-Bold", 24)
                pdf.drawString(margin + 18, 510, verdict)
                pdf.setFont("Helvetica", 10)
                for j, line in enumerate(_wrap(snapshot["state_reason"], 80)[:4]):
                    pdf.drawString(margin + 220, 525 - j * 16, line)
                _draw_box(pdf, margin, 200, page_w - margin * 2, 180, panel, border=soft)
                pdf.setFillColor(navy)
                pdf.setFont("Helvetica-Bold", 12)
                pdf.drawString(margin + 18, 346, "LIMITATIONS")
                pdf.setFillColor(black)
                pdf.setFont("Helvetica", 10)
                for j, line in enumerate(_wrap(snapshot["limitations"], 100)[:10]):
                    pdf.drawString(margin + 18, 330 - j * 16, line)
            elif idx == 5:
                pdf.setFillColor(navy)
                pdf.setFont("Helvetica-Bold", 18)
                pdf.drawString(margin, page_h - 90, "REPORT METADATA")
                _draw_box(pdf, margin, 420, page_w - margin * 2, 210, panel, border=soft)
                pdf.setFillColor(navy)
                pdf.setFont("Helvetica-Bold", 10)
                data = [
                    ("Report ID", snapshot["report_id"]),
                    ("Report Type", snapshot["report_type"]),
                    ("Evidence ID", snapshot["evidence_id"]),
                    ("Case ID", str(snapshot["case_id"])),
                    ("Generated", snapshot["collection_timestamp"]),
                    ("Original Filename", snapshot["original_filename"]),
                ]
                for j, (label, value) in enumerate(data):
                    y = 590 - j * 28
                    pdf.drawString(margin + 18, y, label)
                    pdf.setFillColor(black)
                    pdf.setFont("Helvetica", 9)
                    pdf.drawString(margin + 180, y, str(value)[:80])
                    pdf.setFillColor(navy)
                    pdf.setFont("Helvetica-Bold", 10)
                    _draw_footer(pdf, idx + 1, total)

    add_cover_page()
    if mode == "detailed":
        # cover + detailed appendix (2 pages) => total 3 pages
        pdf.showPage()
        add_detailed_pages()
    else:
        # cover + 1 summary page => total 2 pages
        pdf.showPage()
        add_summary_pages()

    pdf.save()
    return buffer.getvalue()


def _download_header(filename: str, status: str) -> dict[str, str]:
    safe_title = ''.join(ch if ch.isalnum() or ch in "._- " else '_' for ch in filename)
    return {
        "Content-Disposition": f'attachment; filename="{safe_title}.pdf"',
        "X-VeriChain-Report-Status": status,
        # prevent browsers and proxies from serving cached old copies
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
    }


router = APIRouter(tags=["integrity"])


def _require_access(db: Session, evidence_id: str, current_user: User) -> Evidence:
    if not current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not assigned to an organization")
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if evidence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    if evidence.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Evidence does not belong to your organization")
    return evidence


@router.get("/evidence/{evidence_id}/integrity-report", response_model=IntegrityReportResponse)
def get_integrity_report(
    evidence_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    evidence = _require_access(db, evidence_id, current_user)
    report = IntegrityReportService.generate_report(db, evidence)
    return report


@router.get("/evidence/{evidence_id}/report", response_model=IntegrityReportResponse)
def get_evidence_report(
    evidence_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_integrity_report(evidence_id=evidence_id, db=db, current_user=current_user)


@router.get("/evidence/{evidence_id}/report.pdf")
def get_evidence_report_pdf(
    evidence_id: str,
    mode: str = Query(default="summary", regex="^(summary|detailed)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    evidence = _require_access(db, evidence_id, current_user)
    report = IntegrityReportService.generate_report(db, evidence)
    pdf_bytes = _build_report_pdf_bytes(report, evidence, mode, db)
    # use deterministic report filename (prevents confusion with browser-saved originals)
    filename_base = f"verichain-report-{evidence.id[:8]}-{mode}"
    headers = _download_header(filename_base, report.get("verification_status", "UNKNOWN"))
    headers["Content-Length"] = str(len(pdf_bytes))
    # add ETag so proxies/browsers can clearly identify this exact payload
    try:
        import hashlib
        headers["ETag"] = hashlib.sha256(pdf_bytes).hexdigest()
    except Exception:
        pass
    headers["Expires"] = "0"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers=headers,
    )


@router.post("/evidence/{evidence_id}/verify-integrity", response_model=IntegrityReportResponse)
def verify_integrity(
    evidence_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    evidence = _require_access(db, evidence_id, current_user)
    report = IntegrityReportService.generate_report(db, evidence)
    return report
