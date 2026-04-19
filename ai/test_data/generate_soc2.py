"""
Generate realistic synthetic SOC-2 Type II reports as PDFs for testing.

Usage:
    python -m test_data.generate_soc2          # from ai/ directory
    python ai/test_data/generate_soc2.py       # from project root
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

# ── Styles ──────────────────────────────────────────────────────────────

_styles = getSampleStyleSheet()

STYLE_TITLE = ParagraphStyle(
    "CoverTitle", parent=_styles["Title"], fontSize=28, leading=34,
    spaceAfter=20, alignment=TA_CENTER,
)
STYLE_SUBTITLE = ParagraphStyle(
    "CoverSubtitle", parent=_styles["Normal"], fontSize=14, leading=18,
    alignment=TA_CENTER, textColor=colors.HexColor("#444444"),
)
STYLE_H1 = ParagraphStyle(
    "SectionH1", parent=_styles["Heading1"], fontSize=16, leading=20,
    spaceAfter=12, spaceBefore=18, textColor=colors.HexColor("#1a1a2e"),
)
STYLE_H2 = ParagraphStyle(
    "SectionH2", parent=_styles["Heading2"], fontSize=13, leading=16,
    spaceAfter=8, spaceBefore=14, textColor=colors.HexColor("#333355"),
)
STYLE_BODY = ParagraphStyle(
    "BodyText2", parent=_styles["Normal"], fontSize=10, leading=14,
    alignment=TA_JUSTIFY, spaceAfter=8,
)
STYLE_BODY_INDENT = ParagraphStyle(
    "BodyIndent", parent=STYLE_BODY, leftIndent=20,
)
STYLE_SMALL = ParagraphStyle(
    "SmallText", parent=_styles["Normal"], fontSize=9, leading=12,
    textColor=colors.HexColor("#666666"),
)
STYLE_CELL = ParagraphStyle(
    "CellText", parent=_styles["Normal"], fontSize=8, leading=10,
)
STYLE_CELL_BOLD = ParagraphStyle(
    "CellBold", parent=STYLE_CELL, fontName="Helvetica-Bold",
)

# ── Criteria metadata ──────────────────────────────────────────────────

CRITERIA_DEFS: dict[str, dict] = {
    "CC6.1": {
        "category": "Logical and Physical Access Controls",
        "activity": "The entity implements logical access security software, infrastructure, and architectures over protected information assets to protect them from security events.",
        "test": "Inspected access control configurations, reviewed access control lists, and tested logical access security mechanisms for a sample of systems.",
    },
    "CC6.2": {
        "category": "Logical and Physical Access Controls",
        "activity": "Prior to issuing system credentials and granting system access, the entity registers and authorizes new internal and external users.",
        "test": "Selected a sample of new hires and verified that access provisioning followed the documented onboarding workflow including manager approval.",
    },
    "CC6.3": {
        "category": "Logical and Physical Access Controls",
        "activity": "The entity authorizes, modifies, or removes access to data, software, functions, and other protected information assets based on roles, responsibilities, or the system design and changes.",
        "test": "Obtained quarterly access review reports, selected a sample of terminated employees and verified timely access removal.",
    },
    "CC6.6": {
        "category": "Logical and Physical Access Controls",
        "activity": "The entity implements logical access security measures to protect against threats from sources outside its system boundaries.",
        "test": "Inspected firewall rules, WAF configuration, and DDoS protection mechanisms. Reviewed network architecture diagrams.",
    },
    "CC6.8": {
        "category": "Logical and Physical Access Controls",
        "activity": "The entity implements controls to prevent or detect and act upon the introduction of unauthorized or malicious software.",
        "test": "Verified endpoint protection deployment across all workstations and servers. Reviewed malware detection logs for the audit period.",
    },
    "CC7.1": {
        "category": "System Operations",
        "activity": "To meet its objectives, the entity uses detection and monitoring procedures to identify changes to configurations that result in the introduction of new vulnerabilities.",
        "test": "Reviewed vulnerability scanning reports and verified remediation of critical and high vulnerabilities within defined SLAs.",
    },
    "CC7.2": {
        "category": "System Operations",
        "activity": "The entity monitors system components and the operation of those components for anomalies that are indicative of malicious acts, natural disasters, and errors.",
        "test": "Inspected SIEM configuration, reviewed alerting rules, and verified that automated monitoring thresholds are reviewed and updated periodically.",
    },
    "CC7.3": {
        "category": "System Operations",
        "activity": "The entity evaluates security events to determine whether they could or have resulted in a failure of the entity to meet its objectives.",
        "test": "Selected a sample of security events and verified that triage, classification, and escalation procedures were followed.",
    },
    "CC7.4": {
        "category": "System Operations",
        "activity": "The entity responds to identified security incidents by executing a defined incident response program to understand, contain, remediate, and communicate security incidents.",
        "test": "Obtained the incident response plan, reviewed incident tickets, and verified that tabletop exercises were conducted during the audit period.",
    },
    "CC8.1": {
        "category": "Change Management",
        "activity": "The entity authorizes, designs, develops or acquires, configures, documents, tests, approves, and implements changes to infrastructure, data, software, and procedures.",
        "test": "Selected a sample of change requests and verified that each followed the documented change management process including peer review and approval.",
    },
    "CC9.1": {
        "category": "Risk Mitigation",
        "activity": "The entity identifies, selects, and develops risk mitigation activities for risks arising from potential business disruptions.",
        "test": "Reviewed business continuity and disaster recovery plans, verified annual testing, and inspected backup restoration test results.",
    },
}


# ── Page templates ─────────────────────────────────────────────────────

def _header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#999999"))
    canvas.drawString(inch, 0.5 * inch, "CONFIDENTIAL — SOC 2 Type II Report")
    canvas.drawRightString(letter[0] - inch, 0.5 * inch, f"Page {doc.page}")
    canvas.restoreState()


def _build_doc(output_path: str) -> BaseDocTemplate:
    doc = BaseDocTemplate(
        output_path, pagesize=letter,
        leftMargin=inch, rightMargin=inch,
        topMargin=inch, bottomMargin=0.8 * inch,
    )
    content_frame = Frame(
        inch, 0.8 * inch,
        letter[0] - 2 * inch, letter[1] - 1.8 * inch,
        id="content",
    )
    cover_frame = Frame(
        inch, 0.8 * inch,
        letter[0] - 2 * inch, letter[1] - 1.8 * inch,
        id="cover",
    )
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[cover_frame]),
        PageTemplate(id="content", frames=[content_frame], onPage=_header_footer),
    ])
    return doc


# ── Content generators ─────────────────────────────────────────────────

def _cover_page(company: str, audit_period: str) -> list:
    return [
        Spacer(1, 2.5 * inch),
        Paragraph("SOC 2 Type II Report", STYLE_TITLE),
        Spacer(1, 0.3 * inch),
        Paragraph(f"<b>{company}</b>", ParagraphStyle(
            "CoName", parent=STYLE_SUBTITLE, fontSize=20, leading=24,
            textColor=colors.HexColor("#1a1a2e"),
        )),
        Spacer(1, 0.2 * inch),
        Paragraph(f"Audit Period: {audit_period}", STYLE_SUBTITLE),
        Spacer(1, 0.5 * inch),
        Paragraph("Prepared by:", STYLE_SUBTITLE),
        Paragraph("<b>Independent Audit Partners LLP</b>", STYLE_SUBTITLE),
        Paragraph("Certified Public Accountants", STYLE_SMALL),
        Spacer(1, 1.5 * inch),
        Paragraph("This report is intended solely for the information and use of the management "
                   f"of {company}, user entities, and prospective user entities.", STYLE_SMALL),
        NextPageTemplate("content"),
        PageBreak(),
    ]


def _table_of_contents() -> list:
    elements: list = []
    elements.append(Paragraph("Table of Contents", STYLE_H1))
    elements.append(Spacer(1, 0.3 * inch))
    toc_entries = [
        ("Section I", "Independent Auditor's Report"),
        ("Section II", "Management's Assertion"),
        ("Section III", "System Description"),
        ("", "A. Overview of Operations"),
        ("", "B. Principal Service Commitments and System Requirements"),
        ("", "C. Infrastructure and Technology"),
        ("", "D. Data Flows and Processing"),
        ("", "E. Personnel and Organizational Structure"),
        ("", "F. Security Policies and Practices"),
        ("", "G. Risk Management Program"),
        ("", "H. Third-Party and Subservice Organization Management"),
        ("Section III-B", "Testing Methodology"),
        ("Section IV", "Trust Services Criteria and Control Activities"),
        ("", "Logical and Physical Access Controls (CC6)"),
        ("", "System Operations (CC7)"),
        ("", "Change Management and Risk Mitigation (CC8-CC9)"),
        ("Section IV-B", "Summary of Testing Results"),
        ("Section V", "Findings and Observations"),
        ("Appendix A", "Complementary User Entity Controls"),
    ]
    for section, title in toc_entries:
        if section:
            elements.append(Paragraph(
                f"<b>{section}</b> — {title}", STYLE_BODY))
        else:
            elements.append(Paragraph(
                f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{title}", STYLE_BODY))
    elements.append(PageBreak())
    return elements


def _auditor_opinion(company: str, audit_period: str, opinion: str) -> list:
    elements: list = []
    elements.append(Paragraph("Section I: Independent Auditor's Report", STYLE_H1))
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(Paragraph(f"To the Management of {company}:", STYLE_BODY))
    elements.append(Paragraph("<b>Scope</b>", STYLE_H2))
    elements.append(Paragraph(
        f"We have examined {company}'s description of its system and the suitability of the design "
        f"and operating effectiveness of controls relevant to the Security, Availability, and "
        f"Confidentiality trust services categories throughout the period {audit_period} "
        f"(the \"Description\"), based on the criteria for a description of a service organization's "
        f"system in DC Section 200A, 2018 Description Criteria for a Description of a Service "
        f"Organization's System in a SOC 2 Report (AICPA, Description Criteria), and the suitability "
        f"of the design and operating effectiveness of controls stated in the Description, based on "
        f"the Trust Services Criteria relevant to Security, Availability, and Confidentiality "
        f"(applicable trust services criteria) set forth in TSP Section 100, 2017 Trust Services "
        f"Criteria for Security, Availability, Processing Integrity, Confidentiality, and Privacy "
        f"(AICPA, Trust Services Criteria).", STYLE_BODY))

    elements.append(Paragraph("<b>Service Organization's Responsibilities</b>", STYLE_H2))
    elements.append(Paragraph(
        f"{company} is responsible for: (1) preparing the Description and its assertion, "
        f"(2) the completeness, accuracy, and method of presentation of both, (3) providing the "
        f"services covered by the Description, (4) specifying the controls that meet the applicable "
        f"trust services criteria, and (5) designing, implementing, and documenting the controls.", STYLE_BODY))

    elements.append(Paragraph("<b>Service Auditor's Responsibilities</b>", STYLE_H2))
    elements.append(Paragraph(
        "Our responsibility is to express an opinion on the Description and on the suitability of the "
        "design and operating effectiveness of controls stated in the Description based on our examination. "
        "We conducted our examination in accordance with attestation standards established by the AICPA.", STYLE_BODY))

    elements.append(Paragraph("<b>Opinion</b>", STYLE_H2))
    if opinion == "unqualified":
        elements.append(Paragraph(
            f"In our opinion, in all material respects, (a) the Description fairly presents the {company} "
            f"system that was designed and implemented throughout the period {audit_period}, based on "
            f"the applicable Description Criteria; and (b) the controls stated in the Description were "
            f"suitably designed and operating effectively to provide reasonable assurance that the "
            f"service organization's service commitments and system requirements were achieved based "
            f"on the applicable Trust Services Criteria.", STYLE_BODY))
    else:
        elements.append(Paragraph(
            f"In our opinion, except for the matters described in our findings, (a) the Description fairly "
            f"presents the {company} system as designed and implemented throughout the period "
            f"{audit_period}; however, (b) certain controls stated in the Description were not suitably "
            f"designed or operating effectively to provide reasonable assurance that the service "
            f"organization's service commitments and system requirements were achieved based on the "
            f"applicable Trust Services Criteria.", STYLE_BODY))

    elements.append(Paragraph("Independent Audit Partners LLP", STYLE_BODY))
    elements.append(Paragraph("March 15, 2026", STYLE_SMALL))
    elements.append(PageBreak())
    return elements


def _management_assertion(company: str, audit_period: str, system_desc: str) -> list:
    elements: list = []
    elements.append(Paragraph("Section II: Management's Assertion", STYLE_H1))
    elements.append(Paragraph(
        f"We, the management of {company}, are responsible for: designing, implementing, operating, "
        f"and maintaining effective controls within the system throughout the period {audit_period}; "
        f"providing a Description of the system that is prepared in accordance with the Description "
        f"Criteria; and stating in the assertion that controls were suitably designed and operating "
        f"effectively.", STYLE_BODY))
    elements.append(Paragraph(
        f"We assert that: (a) the Description fairly presents the {company} system that was designed "
        f"and implemented throughout the period {audit_period}; (b) the controls stated in the "
        f"Description were suitably designed to provide reasonable assurance that the service commitments "
        f"and system requirements would be achieved; and (c) the controls operated effectively throughout "
        f"the period to achieve the service commitments and system requirements.", STYLE_BODY))

    elements.append(Paragraph("<b>Basis for Assertion</b>", STYLE_H2))
    elements.append(Paragraph(
        f"The assertion is based on the criteria described in the AICPA's Trust Services Criteria "
        f"(TSP Section 100). The applicable trust services categories covered by this report are "
        f"Security, Availability, and Confidentiality. The criteria are the control objectives "
        f"and related controls specified by the AICPA.", STYLE_BODY))
    elements.append(Paragraph(
        f"There are inherent limitations in any system of internal control, including the possibility "
        f"of human error and the circumvention of controls. Because of these inherent limitations, "
        f"internal control over a service organization's system may not prevent or detect all errors "
        f"or omissions in processing or reporting. Additionally, projections of any evaluation of the "
        f"system to future periods are subject to the risk that controls may become inadequate because "
        f"of changes in conditions, or that the degree of compliance with controls may deteriorate.",
        STYLE_BODY))

    elements.append(Paragraph("<b>Complementary User Entity Controls</b>", STYLE_H2))
    elements.append(Paragraph(
        f"The {company} system was designed with the assumption that certain controls would be "
        f"implemented by user entities. The description of these complementary user entity controls "
        f"is presented in the Appendix to this report. Our assertion and the service auditor's opinion "
        f"do not extend to the operating effectiveness of these complementary user entity controls.",
        STYLE_BODY))
    elements.append(Paragraph(
        f"Signed: Management of {company}", STYLE_BODY))
    elements.append(Paragraph("March 10, 2026", STYLE_SMALL))
    elements.append(PageBreak())
    return elements


def _system_description(company: str, industry: str, desc_config: dict) -> list:
    elements: list = []
    elements.append(Paragraph("Section III: System Description", STYLE_H1))

    elements.append(Paragraph("<b>A. Overview of Operations</b>", STYLE_H2))
    elements.append(Paragraph(desc_config["overview"], STYLE_BODY))

    elements.append(Paragraph("<b>B. Principal Service Commitments and System Requirements</b>", STYLE_H2))
    elements.append(Paragraph(
        f"{company} establishes operational objectives that are consistent with its mission and strategic "
        f"direction. These objectives encompass performance, compliance, and reporting requirements. "
        f"Management has established the following principal service commitments:", STYLE_BODY))
    for commitment in desc_config.get("service_commitments", [
        "Maintain system availability of 99.9% as measured on a monthly basis.",
        "Protect the confidentiality and integrity of customer data in accordance with contractual obligations.",
        "Process transactions accurately, completely, and in a timely manner.",
        "Comply with applicable legal and regulatory requirements.",
        "Notify affected parties within 72 hours of a confirmed security incident.",
    ]):
        elements.append(Paragraph(f"&bull; {commitment}", STYLE_BODY_INDENT))

    elements.append(Paragraph("<b>C. Infrastructure and Technology</b>", STYLE_H2))
    elements.append(Paragraph(desc_config["infrastructure"], STYLE_BODY))

    elements.append(Paragraph("<b>D. Data Flows and Processing</b>", STYLE_H2))
    elements.append(Paragraph(desc_config["data_flows"], STYLE_BODY))

    elements.append(Paragraph("<b>E. Personnel and Organizational Structure</b>", STYLE_H2))
    elements.append(Paragraph(desc_config["personnel"], STYLE_BODY))

    elements.append(Paragraph("<b>F. Security Policies and Practices</b>", STYLE_H2))
    elements.append(Paragraph(
        f"The following security policies and practices are in place at {company} to support "
        f"the trust services criteria:", STYLE_BODY))
    for practice in desc_config.get("security_practices", []):
        elements.append(Paragraph(f"&bull; {practice}", STYLE_BODY_INDENT))

    elements.append(Paragraph("<b>G. Risk Management Program</b>", STYLE_H2))
    elements.append(Paragraph(
        f"{company} maintains a formal risk management program that includes the identification, "
        f"assessment, and mitigation of risks to the achievement of service commitments and system "
        f"requirements. Risk assessments are performed annually and upon significant changes to the "
        f"system or operating environment. The risk management program includes the following components:",
        STYLE_BODY))
    for item in desc_config.get("risk_management", [
        "Annual enterprise risk assessment covering strategic, operational, financial, and compliance risks.",
        "Threat modeling for new features and system changes prior to deployment.",
        "Vendor risk assessment program for third-party service providers with access to sensitive data.",
        "Regular vulnerability scanning and remediation tracking with defined SLAs.",
        "Risk register maintained and reviewed quarterly by the executive leadership team.",
    ]):
        elements.append(Paragraph(f"&bull; {item}", STYLE_BODY_INDENT))

    elements.append(Paragraph("<b>H. Third-Party and Subservice Organization Management</b>", STYLE_H2))
    elements.append(Paragraph(
        f"{company} relies on the following key subservice organizations in delivering its services. "
        f"The controls of these subservice organizations are excluded from the scope of this report. "
        f"Users should consider the need to obtain SOC reports from these organizations.", STYLE_BODY))
    for vendor in desc_config.get("subservice_orgs", [
        "Cloud infrastructure provider (hosting, compute, storage, networking services).",
        "Identity provider (single sign-on, multi-factor authentication, directory services).",
        "Payment processor (credit card processing, ACH transfers).",
        "Customer support platform (ticketing, communication management).",
    ]):
        elements.append(Paragraph(f"&bull; {vendor}", STYLE_BODY_INDENT))

    elements.append(PageBreak())
    return elements


def _controls_methodology() -> list:
    elements: list = []
    elements.append(Paragraph("Section III-B: Testing Methodology", STYLE_H1))
    elements.append(Paragraph(
        "The service auditor's examination was conducted in accordance with attestation standards "
        "established by the American Institute of Certified Public Accountants (AICPA). The following "
        "methodology was applied:", STYLE_BODY))

    elements.append(Paragraph("<b>Test Procedures</b>", STYLE_H2))
    procedures = [
        ("<b>Inquiry:</b> Discussions were held with management and relevant personnel to obtain an "
         "understanding of the design and implementation of controls. We conducted interviews with "
         "system administrators, security engineers, compliance officers, and operational staff."),
        ("<b>Observation:</b> We observed the application of specific controls by operations and "
         "security personnel during site visits and remote sessions. Observations included monitoring "
         "activities, change management processes, and incident response procedures."),
        ("<b>Inspection:</b> We inspected documents, reports, and electronic records to evaluate the "
         "design and operating effectiveness of controls. This included review of policies, configuration "
         "settings, access logs, change records, and monitoring dashboards."),
        ("<b>Re-performance:</b> For a sample of transactions and events, we independently re-performed "
         "control activities to verify that they operated as described. Re-performance testing included "
         "access provisioning, change approvals, and backup restoration."),
    ]
    for proc in procedures:
        elements.append(Paragraph(f"&bull; {proc}", STYLE_BODY_INDENT))

    elements.append(Paragraph("<b>Sampling Approach</b>", STYLE_H2))
    elements.append(Paragraph(
        "For controls that operate on a transaction or event basis, we selected samples based on the "
        "following guidelines: For daily controls, a sample of 25 items was selected across the audit "
        "period. For weekly controls, a sample of 10 items was selected. For monthly controls, all "
        "12 instances were tested. For quarterly controls, all 4 instances were tested. For annual "
        "controls, the single instance was tested. Samples were selected using a combination of "
        "random and judgmental sampling methods.", STYLE_BODY))

    elements.append(Paragraph("<b>Trust Services Categories in Scope</b>", STYLE_H2))
    elements.append(Paragraph(
        "This report covers the following AICPA Trust Services Categories:", STYLE_BODY))
    categories = [
        ("<b>Security (Common Criteria):</b> The system is protected against unauthorized access, "
         "both logical and physical, to meet the entity's objectives."),
        ("<b>Availability:</b> The system is available for operation and use as committed or agreed "
         "to by the entity."),
        ("<b>Confidentiality:</b> Information designated as confidential is protected as committed "
         "or agreed to by the entity."),
    ]
    for cat in categories:
        elements.append(Paragraph(f"&bull; {cat}", STYLE_BODY_INDENT))

    elements.append(PageBreak())
    return elements


_CRITERIA_GROUPS = [
    ("Logical and Physical Access Controls (CC6)", ["CC6.1", "CC6.2", "CC6.3", "CC6.6", "CC6.8"]),
    ("System Operations (CC7)", ["CC7.1", "CC7.2", "CC7.3", "CC7.4"]),
    ("Change Management and Risk Mitigation (CC8-CC9)", ["CC8.1", "CC9.1"]),
]

_TABLE_STYLE = TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTSIZE", (0, 0), (-1, -1), 8),
    ("TOPPADDING", (0, 0), (-1, -1), 5),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
])


def _controls_table(controls_config: dict) -> list:
    elements: list = []
    elements.append(Paragraph("Section IV: Trust Services Criteria and Control Activities", STYLE_H1))
    elements.append(Paragraph(
        "The following tables present the Trust Services Criteria, the related control activities, "
        "tests of controls performed, and the results of those tests. Controls are organized by "
        "criteria category.", STYLE_BODY))
    elements.append(Spacer(1, 0.15 * inch))

    col_widths = [0.65 * inch, 2.1 * inch, 1.8 * inch, 0.55 * inch, 1.4 * inch]

    for group_label, cids in _CRITERIA_GROUPS:
        elements.append(Paragraph(f"<b>{group_label}</b>", STYLE_H2))

        header = [
            Paragraph("<b>Criteria</b>", STYLE_CELL_BOLD),
            Paragraph("<b>Control Activity Description</b>", STYLE_CELL_BOLD),
            Paragraph("<b>Test Performed</b>", STYLE_CELL_BOLD),
            Paragraph("<b>Test Result</b>", STYLE_CELL_BOLD),
            Paragraph("<b>Exceptions</b>", STYLE_CELL_BOLD),
        ]
        rows = [header]

        for cid in cids:
            cdef = CRITERIA_DEFS[cid]
            ctrl = controls_config.get(cid, {})
            passed = ctrl.get("passed", True)
            exception_text = ctrl.get("exception", "None noted.")

            rows.append([
                Paragraph(f"<b>{cid}</b>", STYLE_CELL),
                Paragraph(cdef["activity"], STYLE_CELL),
                Paragraph(cdef["test"], STYLE_CELL),
                Paragraph(
                    '<font color="#22c55e"><b>Pass</b></font>' if passed
                    else '<font color="#ef4444"><b>Fail</b></font>',
                    STYLE_CELL,
                ),
                Paragraph(
                    "None noted." if passed else exception_text,
                    STYLE_CELL,
                ),
            ])

        tbl = Table(rows, colWidths=col_widths, repeatRows=1, splitInRow=True)
        tbl.setStyle(_TABLE_STYLE)
        elements.append(tbl)
        elements.append(Spacer(1, 0.3 * inch))

    elements.append(PageBreak())
    return elements


def _testing_summary(controls_config: dict) -> list:
    elements: list = []
    elements.append(Paragraph("Section IV-B: Summary of Testing Results", STYLE_H1))

    total = len(CRITERIA_DEFS)
    exceptions = sum(1 for cfg in controls_config.values() if not cfg.get("passed", True))
    passed = total - exceptions

    elements.append(Paragraph(
        f"The following summarizes the results of our testing of the {total} control activities "
        f"evaluated during this examination:", STYLE_BODY))
    elements.append(Spacer(1, 0.15 * inch))

    summary_data = [
        [Paragraph("<b>Metric</b>", STYLE_CELL_BOLD), Paragraph("<b>Result</b>", STYLE_CELL_BOLD)],
        [Paragraph("Total controls tested", STYLE_CELL), Paragraph(str(total), STYLE_CELL)],
        [Paragraph("Controls operating effectively (Pass)", STYLE_CELL),
         Paragraph(f'<font color="#22c55e"><b>{passed}</b></font>', STYLE_CELL)],
        [Paragraph("Controls with exceptions (Fail)", STYLE_CELL),
         Paragraph(f'<font color="#ef4444"><b>{exceptions}</b></font>' if exceptions else "0", STYLE_CELL)],
        [Paragraph("Pass rate", STYLE_CELL),
         Paragraph(f"{passed / total * 100:.1f}%", STYLE_CELL)],
        [Paragraph("Trust services categories tested", STYLE_CELL),
         Paragraph("Security, Availability, Confidentiality", STYLE_CELL)],
        [Paragraph("Total test procedures performed", STYLE_CELL),
         Paragraph(str(total * 4), STYLE_CELL)],
        [Paragraph("Samples inspected", STYLE_CELL),
         Paragraph(str(total * 12), STYLE_CELL)],
    ]

    tbl = Table(summary_data, colWidths=[3.5 * inch, 3.0 * inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
    ]))
    elements.append(tbl)
    elements.append(Spacer(1, 0.2 * inch))

    if exceptions == 0:
        elements.append(Paragraph(
            "All controls tested were found to be operating effectively throughout the audit period. "
            "No exceptions or deviations were noted during our examination.", STYLE_BODY))
    else:
        elements.append(Paragraph(
            f"During our examination, {exceptions} of {total} controls tested were found to have "
            f"exceptions. The details of these exceptions, including management's responses and "
            f"remediation plans, are described in Section V: Findings and Observations.", STYLE_BODY))
        elements.append(Paragraph(
            "It is important to note that the existence of exceptions does not necessarily indicate "
            "that the service organization's controls are materially ineffective. The significance "
            "of each exception should be evaluated in the context of the overall control environment "
            "and compensating controls that may be in place.", STYLE_BODY))

    elements.append(PageBreak())
    return elements


def _findings_section(controls_config: dict, company: str) -> list:
    elements: list = []
    elements.append(Paragraph("Section V: Findings and Observations", STYLE_H1))

    exceptions = {
        cid: cfg for cid, cfg in controls_config.items()
        if not cfg.get("passed", True)
    }

    if not exceptions:
        elements.append(Paragraph(
            "No exceptions were noted during our testing of the controls described in this report. "
            "All controls were operating effectively throughout the audit period.", STYLE_BODY))
        elements.append(PageBreak())
        return elements

    elements.append(Paragraph(
        f"During our examination, we identified the following exceptions in the operation of "
        f"controls at {company}:", STYLE_BODY))
    elements.append(Spacer(1, 0.1 * inch))

    for i, (cid, cfg) in enumerate(exceptions.items(), 1):
        cdef = CRITERIA_DEFS.get(cid, {})
        elements.append(Paragraph(f"<b>Finding {i}: {cid} — {cdef.get('category', '')}</b>", STYLE_H2))

        elements.append(Paragraph(f"<b>Condition:</b> {cfg.get('exception', 'Exception noted.')}", STYLE_BODY))

        elements.append(Paragraph(
            f"<b>Criteria:</b> {cdef.get('activity', 'N/A')}", STYLE_BODY))

        elements.append(Paragraph(
            f"<b>Risk/Effect:</b> {cfg.get('risk_effect', 'Increased risk of unauthorized access or system compromise.')}",
            STYLE_BODY))

        elements.append(Paragraph(
            f"<b>Management Response:</b> {cfg.get('mgmt_response', 'Management acknowledges this finding and has implemented corrective actions.')}",
            STYLE_BODY))

        if cfg.get("compensating_control"):
            elements.append(Paragraph(
                f"<b>Compensating Control:</b> {cfg['compensating_control']}", STYLE_BODY))

        elements.append(Spacer(1, 0.15 * inch))

    elements.append(PageBreak())
    return elements


def _appendix(company: str) -> list:
    elements: list = []
    elements.append(Paragraph("Appendix A: Complementary User Entity Controls", STYLE_H1))
    elements.append(Paragraph(
        f"{company}'s controls were designed with the assumption that certain complementary "
        f"controls would be implemented by user entities. The examination did not extend to "
        f"controls at user entities. User entities should evaluate whether the following "
        f"complementary controls are in place within their own environments:", STYLE_BODY))
    elements.append(Spacer(1, 0.1 * inch))

    cuecs = [
        ("CUEC-1: User Authentication",
         "User entities are responsible for managing user access credentials and passwords in "
         "accordance with their own security policies, including enforcement of password complexity "
         "requirements and periodic rotation."),
        ("CUEC-2: Network Security",
         "User entities are responsible for ensuring that their own systems and networks connecting "
         "to the service are appropriately secured, including the use of firewalls, intrusion "
         "detection systems, and encrypted connections."),
        ("CUEC-3: Personnel Changes",
         "User entities are responsible for notifying the service organization promptly of any "
         "changes in personnel that affect user access, including terminations, role changes, and "
         "new hires requiring access."),
        ("CUEC-4: Business Continuity",
         "User entities are responsible for implementing their own business continuity and disaster "
         "recovery plans for business processes dependent on the service, including regular testing "
         "of recovery procedures."),
        ("CUEC-5: Output Reconciliation",
         "User entities are responsible for reviewing and reconciling output reports provided by "
         "the service organization to ensure completeness and accuracy of processed data."),
        ("CUEC-6: Regulatory Compliance",
         "User entities are responsible for ensuring compliance with applicable laws and regulations "
         "governing the use and protection of data processed by the service, including data "
         "residency requirements."),
        ("CUEC-7: Endpoint Security",
         "User entities are responsible for maintaining current anti-malware and endpoint protection "
         "software on all devices used to access the service."),
        ("CUEC-8: Security Awareness",
         "User entities are responsible for ensuring that their personnel who access the service "
         "receive appropriate security awareness training relevant to the services being consumed."),
    ]
    for title, desc in cuecs:
        elements.append(Paragraph(f"<b>{title}</b>", STYLE_H2))
        elements.append(Paragraph(desc, STYLE_BODY))

    elements.append(PageBreak())

    elements.append(Paragraph("Appendix B: Glossary of Terms", STYLE_H1))
    glossary = [
        ("SOC 2", "System and Organization Controls 2 — a framework developed by the AICPA for "
         "managing customer data based on five Trust Services Criteria."),
        ("Type II", "A report that covers the design and operating effectiveness of controls over "
         "a specified period of time (as opposed to Type I which covers a point in time)."),
        ("Trust Services Criteria (TSC)", "Criteria established by the AICPA used to evaluate "
         "controls relevant to Security, Availability, Processing Integrity, Confidentiality, "
         "and Privacy."),
        ("Common Criteria (CC)", "Control criteria that apply across all Trust Services Categories, "
         "focusing on the foundational security principles."),
        ("Unqualified Opinion", "An auditor's opinion that the controls are suitably designed and "
         "operating effectively, with no material exceptions noted."),
        ("Qualified Opinion", "An auditor's opinion that includes reservations about certain "
         "aspects of the controls due to identified exceptions."),
        ("Exception", "An instance where a control did not operate as designed or was not "
         "operating effectively during the audit period."),
        ("Compensating Control", "An alternative control that provides a similar level of "
         "assurance when the primary control has a deficiency."),
        ("CUEC", "Complementary User Entity Control — a control that the service organization "
         "assumes is implemented by its customers."),
        ("MFA", "Multi-Factor Authentication — a security mechanism requiring two or more forms "
         "of verification before granting access."),
        ("SIEM", "Security Information and Event Management — a system that aggregates and "
         "analyzes security log data from across the IT environment."),
        ("PHI", "Protected Health Information — individually identifiable health information "
         "that is subject to HIPAA regulations."),
        ("PII", "Personally Identifiable Information — data that can be used to identify, "
         "contact, or locate an individual."),
    ]
    for term, defn in glossary:
        elements.append(Paragraph(f"<b>{term}:</b> {defn}", STYLE_BODY))

    return elements


# ── Main generator ─────────────────────────────────────────────────────

def generate_soc2_report(
    company_name: str,
    industry: str,
    audit_period: str,
    overall_opinion: str,
    controls_config: dict,
    system_description: dict,
    output_path: str,
) -> str:
    """Generate a synthetic SOC-2 Type II report PDF.

    Args:
        company_name: Company legal name.
        industry: Industry description.
        audit_period: e.g. "January 1, 2025 - December 31, 2025".
        overall_opinion: "unqualified" or "qualified".
        controls_config: Dict of criteria_id -> {passed, exception, mgmt_response, ...}.
        system_description: Dict with keys: overview, infrastructure, data_flows, personnel, security_practices.
        output_path: Where to write the PDF.

    Returns:
        The output_path written to.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    doc = _build_doc(output_path)

    story: list = []
    story.extend(_cover_page(company_name, audit_period))
    story.extend(_table_of_contents())
    story.extend(_auditor_opinion(company_name, audit_period, overall_opinion))
    story.extend(_management_assertion(company_name, audit_period, ""))
    story.extend(_system_description(company_name, industry, system_description))
    story.extend(_controls_methodology())
    story.extend(_controls_table(controls_config))
    story.extend(_testing_summary(controls_config))
    story.extend(_findings_section(controls_config, company_name))
    story.extend(_appendix(company_name))

    doc.build(story)
    return output_path


# ── Report definitions ─────────────────────────────────────────────────

def generate_coinbase_report(output_dir: str) -> str:
    return generate_soc2_report(
        company_name="Coinbase Global, Inc.",
        industry="Financial Technology / Cryptocurrency Exchange",
        audit_period="January 1, 2025 - December 31, 2025",
        overall_opinion="unqualified",
        controls_config={
            "CC6.1": {"passed": True},
            "CC6.2": {"passed": True},
            "CC6.3": {"passed": True},
            "CC6.6": {"passed": True},
            "CC6.8": {"passed": True},
            "CC7.1": {"passed": True},
            "CC7.2": {
                "passed": False,
                "exception": (
                    "Automated alerting thresholds were not reviewed quarterly as stated in "
                    "the policy. During Q2 and Q3, the Security Operations team did not "
                    "perform the scheduled threshold review, resulting in alerting rules that "
                    "were last calibrated in Q1."
                ),
                "risk_effect": (
                    "Stale alerting thresholds may result in increased false negatives, "
                    "potentially allowing anomalous activity to go undetected."
                ),
                "mgmt_response": (
                    "Management acknowledges this finding. Effective October 2025, the SOC team "
                    "has implemented monthly threshold reviews with sign-off tracked in Jira. "
                    "An automated reminder workflow has been deployed to prevent recurrence."
                ),
            },
            "CC7.3": {"passed": True},
            "CC7.4": {"passed": True},
            "CC8.1": {"passed": True},
            "CC9.1": {"passed": True},
        },
        system_description={
            "overview": (
                "Coinbase Global, Inc. operates one of the largest cryptocurrency exchange platforms "
                "in the United States. The platform enables users to buy, sell, store, and transfer "
                "digital assets including Bitcoin, Ethereum, and over 200 other cryptocurrencies. "
                "Coinbase serves both retail consumers and institutional clients through its Coinbase "
                "Pro and Coinbase Prime offerings. The company processes billions of dollars in "
                "cryptocurrency transactions monthly and maintains custodial wallets for millions "
                "of users worldwide."
            ),
            "infrastructure": (
                "Coinbase's production environment is hosted on Amazon Web Services (AWS) across "
                "multiple availability zones and regions for redundancy. Key infrastructure components "
                "include: AWS EC2 and ECS for compute workloads, Amazon RDS (PostgreSQL) for relational "
                "data storage, Amazon DynamoDB for high-throughput key-value operations, Amazon S3 for "
                "object storage and backups, and CloudFront for content delivery. The primary application "
                "is built on Ruby on Rails with a microservices architecture using Go and Python for "
                "performance-critical services. All infrastructure is managed through Terraform with "
                "changes deployed via a CI/CD pipeline using GitHub Actions."
            ),
            "data_flows": (
                "User data flows through the system as follows: (1) Users authenticate via the web or "
                "mobile application with multi-factor authentication required for all accounts. "
                "(2) Transaction requests are submitted through the API gateway and validated by the "
                "order matching engine. (3) Cryptocurrency transactions are signed using hardware "
                "security modules (HSMs) with multi-party computation (MPC) protocols. (4) User "
                "personally identifiable information (PII) including government-issued IDs, social "
                "security numbers, and financial data is encrypted at rest using AES-256 and in "
                "transit using TLS 1.3. (5) Fiat currency transactions are processed through "
                "established banking partners with real-time fraud monitoring."
            ),
            "personnel": (
                "Coinbase employs approximately 3,500 full-time employees. The Security team consists "
                "of 85 dedicated security engineers and analysts organized into Application Security, "
                "Infrastructure Security, Security Operations (SOC), and Governance, Risk & Compliance "
                "(GRC) functions. The CISO reports directly to the CEO with a dotted line to the "
                "Board's Audit Committee. All employees undergo background checks and complete "
                "mandatory security awareness training quarterly."
            ),
            "security_practices": [
                "Multi-factor authentication (MFA) required for all employee and user accounts",
                "AES-256 encryption at rest for all sensitive data; TLS 1.3 for all data in transit",
                "Hardware security modules (HSMs) for cryptographic key management",
                "24/7 Security Operations Center (SOC) with SIEM-based monitoring",
                "Annual third-party penetration testing by a Big 4 firm",
                "Bug bounty program through HackerOne",
                "Quarterly access reviews for all systems",
                "Incident response plan tested via tabletop exercises biannually",
                "Business continuity and disaster recovery plans tested annually",
                "SOC 2 Type II audit conducted annually; ISO 27001 certified",
            ],
            "subservice_orgs": [
                "Amazon Web Services, Inc. (AWS) — cloud infrastructure, compute, storage, and networking.",
                "Okta, Inc. — identity and access management, single sign-on, multi-factor authentication.",
                "Stripe, Inc. — fiat currency payment processing for customer deposits and withdrawals.",
                "Datadog, Inc. — infrastructure monitoring, log management, and APM.",
                "Zendesk, Inc. — customer support ticketing and communication platform.",
            ],
        },
        output_path=os.path.join(output_dir, "coinbase_soc2.pdf"),
    )


def generate_healthpulse_report(output_dir: str) -> str:
    return generate_soc2_report(
        company_name="HealthPulse, Inc.",
        industry="Healthcare Technology / AI Diagnostics",
        audit_period="January 1, 2025 - December 31, 2025",
        overall_opinion="qualified",
        controls_config={
            "CC6.1": {
                "passed": False,
                "exception": (
                    "Multi-factor authentication (MFA) was not enforced for all administrative "
                    "accounts during Q1 and Q2 of the audit period. Specifically, 12 of 34 "
                    "administrative accounts (35%) were configured with password-only authentication "
                    "for the first six months of the period. MFA was retroactively enforced in July 2025."
                ),
                "risk_effect": (
                    "Administrative accounts without MFA are significantly more vulnerable to "
                    "credential-based attacks. Given that HealthPulse processes protected health "
                    "information (PHI), unauthorized access to admin accounts could result in a "
                    "reportable HIPAA breach."
                ),
                "mgmt_response": (
                    "Management acknowledges this finding. MFA has been enforced for all accounts "
                    "since July 2025. A technical control has been implemented in our identity provider "
                    "(Okta) to prevent the creation of accounts without MFA. Additionally, a weekly "
                    "automated scan verifies MFA compliance across all accounts."
                ),
            },
            "CC6.2": {"passed": True},
            "CC6.3": {
                "passed": False,
                "exception": (
                    "Access reviews were not performed quarterly as documented in the access "
                    "management policy. Only one access review was completed during the audit "
                    "period (in Q3). Furthermore, three former employees retained active accounts "
                    "for an average of 45 days after their termination date. One former engineer "
                    "retained access to the production database for 67 days post-termination."
                ),
                "risk_effect": (
                    "Failure to perform timely access reviews and deprovisioning increases the "
                    "risk of unauthorized access by former employees. The production database "
                    "contains PHI for approximately 2.3 million patients."
                ),
                "mgmt_response": (
                    "Management has implemented automated access review workflows in our identity "
                    "management system. HR termination events now trigger immediate account "
                    "deactivation via an automated SCIM integration with Okta. Quarterly access "
                    "reviews are now tracked with mandatory completion deadlines."
                ),
                "compensating_control": (
                    "VPN access was revoked for all terminated employees within 24 hours of "
                    "termination. While application-level accounts remained active, network-level "
                    "access was restricted, limiting the exposure."
                ),
            },
            "CC6.6": {"passed": True},
            "CC6.8": {"passed": True},
            "CC7.1": {"passed": True},
            "CC7.2": {"passed": True},
            "CC7.3": {"passed": True},
            "CC7.4": {
                "passed": False,
                "exception": (
                    "The incident response plan was documented and approved by management; however, "
                    "no tabletop exercises or simulated incident drills were conducted during the "
                    "audit period. The policy requires annual testing of the incident response "
                    "plan, but the last documented test was in September 2023."
                ),
                "risk_effect": (
                    "An untested incident response plan may not function effectively during an "
                    "actual security incident, potentially increasing response time and the scope "
                    "of a breach. This is particularly concerning given the PHI data handled."
                ),
                "mgmt_response": (
                    "Management has scheduled quarterly tabletop exercises starting January 2026. "
                    "The first exercise has been completed and documented. A retainer agreement "
                    "with a third-party incident response firm has also been executed to provide "
                    "additional expertise during incidents."
                ),
            },
            "CC8.1": {"passed": True},
            "CC9.1": {"passed": True},
        },
        system_description={
            "overview": (
                "HealthPulse, Inc. provides an AI-powered clinical decision support platform that "
                "assists healthcare providers with diagnostic imaging analysis. The platform uses "
                "deep learning models trained on medical imaging datasets to identify anomalies in "
                "X-rays, CT scans, and MRI images. HealthPulse integrates with electronic health "
                "record (EHR) systems via FHIR (Fast Healthcare Interoperability Resources) APIs "
                "and serves over 450 hospitals and clinics across the United States. The platform "
                "processes approximately 50,000 diagnostic images daily."
            ),
            "infrastructure": (
                "HealthPulse's production environment is hosted on Google Cloud Platform (GCP) within "
                "a HIPAA-compliant project configuration. Key components include: Google Kubernetes "
                "Engine (GKE) for container orchestration, Cloud SQL (PostgreSQL) for structured data, "
                "Cloud Healthcare API for FHIR resources, Google Cloud Storage for medical image "
                "storage, and Vertex AI for ML model serving. The application backend is built in "
                "Python using FastAPI, with TensorFlow and PyTorch for the ML inference pipeline. "
                "Infrastructure is managed via Terraform with deployments through Cloud Build."
            ),
            "data_flows": (
                "Protected health information (PHI) flows through the system as follows: (1) Medical "
                "images are received from hospital PACS systems via DICOM protocol over a VPN tunnel. "
                "(2) Images are de-identified using a HIPAA-compliant de-identification engine before "
                "processing by AI models. (3) AI inference results are generated and stored in the "
                "FHIR-compliant clinical data store. (4) Results are transmitted back to the ordering "
                "provider's EHR system via FHIR API. (5) All PHI is encrypted at rest using Google-managed "
                "encryption keys (AES-256) and in transit using TLS 1.2+. (6) Audit logs of all PHI "
                "access are maintained for seven years per HIPAA requirements."
            ),
            "personnel": (
                "HealthPulse employs 180 full-time employees. The engineering team of 85 includes "
                "a dedicated Security & Compliance team of 6 members led by the VP of Security, who "
                "reports to the CTO. The company employs a part-time HIPAA Privacy Officer and a "
                "part-time HIPAA Security Officer. All employees with access to PHI undergo HIPAA "
                "training upon hiring and annually thereafter. Background checks are performed "
                "for all employees."
            ),
            "security_practices": [
                "Multi-factor authentication (MFA) enforced for all accounts (as of July 2025)",
                "AES-256 encryption at rest via Google-managed encryption; TLS 1.2+ in transit",
                "HIPAA Business Associate Agreements (BAAs) with all subprocessors",
                "De-identification pipeline for medical images before AI processing",
                "SIEM monitoring via Google Chronicle with automated alerting",
                "Annual third-party penetration testing",
                "HIPAA-compliant audit logging with 7-year retention",
                "Incident response plan documented (testing cadence under improvement)",
                "Business continuity plan with RTO of 4 hours and RPO of 1 hour",
            ],
            "subservice_orgs": [
                "Google Cloud Platform (GCP) — cloud infrastructure, Kubernetes, storage, and ML serving.",
                "Okta, Inc. — identity management and multi-factor authentication.",
                "Snowflake, Inc. — analytics data warehouse for de-identified aggregate metrics.",
                "PagerDuty, Inc. — incident alerting and on-call management.",
                "Aptible, Inc. — HIPAA-compliant container hosting for legacy FHIR adapters.",
            ],
        },
        output_path=os.path.join(output_dir, "healthpulse_soc2.pdf"),
    )


# ── CLI entry point ────────────────────────────────────────────────────

if __name__ == "__main__":
    out_dir = str(Path(__file__).parent)

    print("Generating Coinbase SOC-2 report...")
    p1 = generate_coinbase_report(out_dir)
    print(f"  -> {p1}")

    print("Generating HealthPulse SOC-2 report...")
    p2 = generate_healthpulse_report(out_dir)
    print(f"  -> {p2}")

    print("Done.")
