# ============================================================
# pdf_report.py — PDF Report Generator (v2)
#
# Generates a professional client proposal PDF after analysis.
# Uses reportlab for PDF creation.
#
# Install: pip install reportlab
# ============================================================

import io
from datetime import datetime

# ---- Try to import reportlab ----
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, KeepTogether
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


def generate_report(client_name, analysis_result, recommended_policies, agent_name="Insurance Agent"):
    """
    Generates a professional PDF client proposal.

    Parameters:
        client_name (str): Client's name
        analysis_result (dict): The analysis from ai_engine
        recommended_policies (list): List of recommended policy dicts
        agent_name (str): The agent's name for the report

    Returns:
        bytes: The PDF file as bytes (ready for download)
        OR None if reportlab is not installed
    """
    if not REPORTLAB_AVAILABLE:
        return None

    # ---- Create PDF in memory (no file saved to disk) ----
    buffer = io.BytesIO()

    # ---- Document setup ----
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch
    )

    # ---- Define custom styles ----
    styles = getSampleStyleSheet()

    # Title style — large, dark blue
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontSize=22,
        textColor=colors.HexColor("#0d1b2a"),
        spaceAfter=4,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold"
    )

    # Subtitle style
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#8892b0"),
        spaceAfter=2,
        alignment=TA_CENTER
    )

    # Section heading
    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#1a2f5e"),
        spaceBefore=16,
        spaceAfter=6,
        fontName="Helvetica-Bold",
        borderPadding=(0, 0, 4, 0)
    )

    # Body text
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#333333"),
        spaceAfter=4,
        leading=16
    )

    # Small label
    label_style = ParagraphStyle(
        "Label",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#8892b0"),
        spaceAfter=2
    )

    # ---- Build the content story ----
    story = []
    today = datetime.now().strftime("%B %d, %Y")
    intent = analysis_result.get("intent", "family")

    # ===== HEADER SECTION =====
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph("🛡️ Insurance Proposal Report", title_style))
    story.append(Paragraph(f"Prepared by {agent_name} · {today}", subtitle_style))
    story.append(Spacer(1, 0.1 * inch))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a2f5e")))
    story.append(Spacer(1, 0.15 * inch))

    # ===== CLIENT DETAILS =====
    story.append(Paragraph("CLIENT INFORMATION", heading_style))

    client_data = [
        ["Client Name:", client_name if client_name.strip() else "Valued Client"],
        ["Date:", today],
        ["Prepared By:", agent_name],
        ["Detected Need:", intent.title() + " Insurance"],
        ["Analysis Confidence:", analysis_result.get("confidence", "medium").title()],
    ]

    client_table = Table(client_data, colWidths=[2 * inch, 4.5 * inch])
    client_table.setStyle(TableStyle([
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1a2f5e")),
        ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#333333")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f8f9ff"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e0e6ff")),
        ("ROUNDEDCORNERS", [4]),
    ]))
    story.append(client_table)

    # ===== CLIENT NEED SUMMARY =====
    story.append(Paragraph("NEEDS ANALYSIS SUMMARY", heading_style))

    summary_text = analysis_result.get(
        "summary",
        f"Client has been identified as needing {intent} insurance based on their conversation."
    )
    story.append(Paragraph(summary_text, body_style))

    # Show key signals if available
    key_signals = analysis_result.get("key_signals", [])
    if key_signals:
        signals_text = "Key indicators detected: " + ", ".join([f"<i>{s}</i>" for s in key_signals])
        story.append(Paragraph(signals_text, label_style))

    story.append(Spacer(1, 0.1 * inch))

    # ===== RECOMMENDED POLICIES =====
    story.append(Paragraph("RECOMMENDED POLICIES", heading_style))
    story.append(Paragraph(
        f"Based on the client's needs, we recommend the following {len(recommended_policies)} policies ranked by value:",
        body_style
    ))
    story.append(Spacer(1, 0.1 * inch))

    for i, policy in enumerate(recommended_policies):
        # Policy card as a mini table
        rank_label = ["🥇 TOP PICK", "🥈 ALTERNATIVE", "🥉 BUDGET OPTION"][i] if i < 3 else f"#{i+1}"

        policy_header_data = [[
            f"{rank_label}: {policy['name']}",
            f"Profit Score: {policy['profit_score']}/100"
        ]]

        header_table = Table(policy_header_data, colWidths=[4.5 * inch, 2 * inch])
        header_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1a2f5e")),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING", (0, 0), (0, -1), 10),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("RIGHTPADDING", (1, 0), (1, -1), 10),
        ]))
        story.append(header_table)

        # Policy details table
        highlights = policy.get("highlights", [])
        highlights_str = " · ".join(highlights) if highlights else "—"

        policy_details_data = [
            ["Annual Premium", f"${policy['premium']:,}"],
            ["Coverage Amount", policy.get("coverage", "—")],
            ["Key Benefits", highlights_str],
            ["Ideal For", policy.get("ideal_for", "—")],
            ["Description", policy.get("description", "—")],
        ]

        detail_table = Table(policy_details_data, colWidths=[1.8 * inch, 4.7 * inch])
        detail_table.setStyle(TableStyle([
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#555555")),
            ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#111111")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (0, -1), 10),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f5f7ff"), colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dde3f5")),
        ]))
        story.append(detail_table)
        story.append(Spacer(1, 0.15 * inch))

    # ===== FINANCIAL SUMMARY =====
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#dde3f5")))
    story.append(Paragraph("FINANCIAL SUMMARY", heading_style))

    total_premium = sum(p["premium"] for p in recommended_policies)
    estimated_commission = round(total_premium * 0.15)

    summary_data = [
        ["METRIC", "VALUE"],
        ["Total Annual Premium (all plans)", f"${total_premium:,}"],
        ["Estimated Agent Commission (15%)", f"${estimated_commission:,}"],
        ["Number of Policies Recommended", str(len(recommended_policies))],
        ["Top Profit Score", f"{max(p['profit_score'] for p in recommended_policies)}/100"],
    ]

    summary_table = Table(summary_data, colWidths=[4 * inch, 2.5 * inch])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d1b2a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 1), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (0, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f0f4ff"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dde3f5")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e8f4e8")),
        ("TEXTCOLOR", (0, -1), (0, -1), colors.HexColor("#1a5e1a")),
        ("TEXTCOLOR", (1, -1), (1, -1), colors.HexColor("#1a5e1a")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    story.append(summary_table)

    # ===== FOOTER =====
    story.append(Spacer(1, 0.3 * inch))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#dde3f5")))
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(
        f"This proposal was generated by the Insurance Agent Sales Co-Pilot · {today} · For agent use only.",
        label_style
    ))
    story.append(Paragraph(
        "Premiums and benefits are indicative. Final terms subject to underwriting and policy issuance.",
        label_style
    ))

    # ---- Build the PDF ----
    doc.build(story)
    buffer.seek(0)

    return buffer.getvalue()
