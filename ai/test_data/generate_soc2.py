"""
Generate realistic synthetic SOC-2 Type II reports as PDFs for testing.

Produces 70-100 page reports that mirror the structure and density of
real SOC-2 Type II audit reports.

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
STYLE_H3 = ParagraphStyle(
    "SectionH3", parent=_styles["Heading3"], fontSize=11, leading=14,
    spaceAfter=6, spaceBefore=10, textColor=colors.HexColor("#444466"),
)
STYLE_BODY = ParagraphStyle(
    "BodyText2", parent=_styles["Normal"], fontSize=10, leading=14,
    alignment=TA_JUSTIFY, spaceAfter=8,
)
STYLE_BODY_INDENT = ParagraphStyle(
    "BodyIndent", parent=STYLE_BODY, leftIndent=20,
)
STYLE_BODY_INDENT2 = ParagraphStyle(
    "BodyIndent2", parent=STYLE_BODY, leftIndent=40,
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

# ═══════════════════════════════════════════════════════════════════════
# Criteria metadata — full SOC-2 Common Criteria + Availability +
# Confidentiality
# ═══════════════════════════════════════════════════════════════════════

CRITERIA_DEFS: dict[str, dict] = {
    # ── CC1: Control Environment ──
    "CC1.1": {
        "category": "Control Environment",
        "activity": (
            "The entity demonstrates a commitment to integrity and ethical values. "
            "Management establishes standards of conduct that are communicated to all "
            "personnel and enforced through disciplinary actions. The organization's "
            "code of conduct is reviewed annually by the Board of Directors and "
            "distributed to all employees, contractors, and third-party service providers."
        ),
        "test": (
            "Obtained and inspected the entity's Code of Conduct and Ethics Policy. "
            "Verified that all employees acknowledged receipt of the policy during the "
            "audit period. Selected a sample of 25 new hires and confirmed that ethics "
            "training was completed within 30 days of onboarding. Reviewed disciplinary "
            "action logs for evidence of enforcement. Inspected Board meeting minutes "
            "for annual review and approval of the Code of Conduct."
        ),
    },
    "CC1.2": {
        "category": "Control Environment",
        "activity": (
            "The Board of Directors demonstrates independence from management and "
            "exercises oversight of the development and performance of internal "
            "controls. The Board's Audit Committee meets quarterly to review the "
            "effectiveness of the internal control environment, evaluate risk "
            "assessments, and review the results of internal and external audits."
        ),
        "test": (
            "Inspected Board and Audit Committee charters. Reviewed meeting minutes "
            "from all four quarterly Audit Committee meetings during the audit period. "
            "Verified that the committee includes at least one independent director with "
            "financial expertise. Confirmed that the committee reviewed internal audit "
            "findings, risk assessment updates, and management's remediation plans."
        ),
    },
    "CC1.3": {
        "category": "Control Environment",
        "activity": (
            "Management establishes, with Board oversight, structures, reporting "
            "lines, and appropriate authorities and responsibilities in the pursuit "
            "of objectives. The organizational structure clearly defines roles and "
            "responsibilities for information security, risk management, and compliance. "
            "A RACI matrix is maintained for all critical security and compliance functions."
        ),
        "test": (
            "Obtained the organizational chart and verified reporting lines for security "
            "and compliance functions. Inspected the RACI matrix for key security "
            "processes including incident response, access management, and change "
            "management. Verified that the CISO has a direct reporting line to executive "
            "management and that security responsibilities are clearly documented in "
            "job descriptions for all relevant roles."
        ),
    },
    "CC1.4": {
        "category": "Control Environment",
        "activity": (
            "The entity demonstrates a commitment to attract, develop, and retain "
            "competent individuals in alignment with objectives. The entity maintains "
            "formal hiring standards including background verification, skills "
            "assessment, and reference checks for all employees with access to "
            "sensitive systems and data."
        ),
        "test": (
            "Selected a sample of 25 new hires during the audit period and verified "
            "that background checks were completed prior to start date. Confirmed that "
            "technical assessments were administered for engineering and security roles. "
            "Reviewed the training program and verified that mandatory security awareness "
            "training was completed by 100% of employees. Inspected performance review "
            "records to confirm annual evaluation of security-related competencies."
        ),
    },
    "CC1.5": {
        "category": "Control Environment",
        "activity": (
            "The entity holds individuals accountable for their internal control "
            "responsibilities in the pursuit of objectives. Performance evaluations "
            "include security and compliance metrics, and the entity maintains a "
            "formal disciplinary process for policy violations."
        ),
        "test": (
            "Reviewed the disciplinary action policy and verified it addresses security "
            "policy violations. Selected a sample of 15 performance reviews and confirmed "
            "that security responsibilities were evaluated. Inspected incident logs for "
            "any policy violations during the period and verified that appropriate "
            "corrective action was taken within defined timelines."
        ),
    },

    # ── CC2: Communication and Information ──
    "CC2.1": {
        "category": "Communication and Information",
        "activity": (
            "The entity obtains or generates and uses relevant, quality information "
            "to support the functioning of internal control. Information systems are "
            "designed to capture, process, and report data necessary for monitoring "
            "security events, access patterns, system performance, and compliance "
            "status. Data quality controls ensure the completeness and accuracy of "
            "security-relevant information."
        ),
        "test": (
            "Inspected the configuration of the SIEM platform and verified that logs "
            "from all in-scope systems are aggregated. Reviewed log retention policies "
            "and confirmed that security event logs are retained for the required period. "
            "Tested a sample of 20 security events and verified that complete contextual "
            "information was captured including timestamps, source IPs, user identifiers, "
            "and event outcomes. Verified data quality checks in the log ingestion pipeline."
        ),
    },
    "CC2.2": {
        "category": "Communication and Information",
        "activity": (
            "The entity internally communicates information, including objectives and "
            "responsibilities for internal control, necessary to support the functioning "
            "of internal control. Security policies, standards, and procedures are "
            "published on the internal knowledge base and accessible to all employees. "
            "Changes to policies are communicated via company-wide announcements and "
            "tracked through version control."
        ),
        "test": (
            "Verified that the internal knowledge base contains current versions of all "
            "security policies. Reviewed communication logs for policy change announcements. "
            "Selected a sample of 10 employees and confirmed awareness of key security "
            "policies including acceptable use, incident reporting, and data classification. "
            "Verified that policy documents include version numbers, effective dates, and "
            "approval signatures."
        ),
    },
    "CC2.3": {
        "category": "Communication and Information",
        "activity": (
            "The entity communicates with external parties regarding matters affecting "
            "the functioning of internal control. The entity maintains established channels "
            "for communicating security incidents to affected customers, regulatory "
            "authorities, and other stakeholders. A formal communication plan exists "
            "for breach notifications in compliance with applicable laws and contractual "
            "obligations."
        ),
        "test": (
            "Inspected the external communication policy including the breach notification "
            "plan. Verified that the plan addresses notification requirements under "
            "applicable state and federal laws. Reviewed the entity's status page and "
            "verified that system availability incidents were communicated within defined "
            "SLAs. Confirmed that customer-facing security documentation (trust center, "
            "security whitepaper) is reviewed and updated at least annually."
        ),
    },

    # ── CC3: Risk Assessment ──
    "CC3.1": {
        "category": "Risk Assessment",
        "activity": (
            "The entity specifies objectives with sufficient clarity to enable the "
            "identification and assessment of risks relating to objectives. Security "
            "objectives are formally documented, aligned with business objectives, and "
            "reviewed annually by executive management. Objectives cover confidentiality, "
            "integrity, and availability of customer data and systems."
        ),
        "test": (
            "Obtained the entity's security strategy document and verified that security "
            "objectives are clearly defined and measurable. Confirmed that objectives "
            "were reviewed and approved by executive management during the audit period. "
            "Verified alignment between security objectives, the risk register, and "
            "control activities. Inspected meeting minutes documenting the annual "
            "strategic review of security objectives."
        ),
    },
    "CC3.2": {
        "category": "Risk Assessment",
        "activity": (
            "The entity identifies risks to the achievement of its objectives across "
            "the entity and analyzes risks as a basis for determining how the risks "
            "should be managed. A formal risk assessment is conducted annually and "
            "upon significant changes to the operating environment. Risks are categorized "
            "by likelihood and impact and recorded in a centralized risk register."
        ),
        "test": (
            "Obtained the risk register and verified that it was updated within the "
            "audit period. Reviewed the risk assessment methodology and confirmed it "
            "addresses both inherent and residual risk. Selected a sample of 10 risks "
            "and verified that each has an assigned owner, risk rating, and treatment "
            "plan. Confirmed that the risk assessment process includes input from "
            "business stakeholders, engineering, and security teams."
        ),
    },
    "CC3.3": {
        "category": "Risk Assessment",
        "activity": (
            "The entity considers the potential for fraud in assessing risks to the "
            "achievement of objectives. The risk assessment process includes evaluation "
            "of fraud risks including misappropriation of assets, fraudulent financial "
            "reporting, and unauthorized data access or modification. Anti-fraud controls "
            "are implemented based on the assessed fraud risk."
        ),
        "test": (
            "Reviewed the fraud risk assessment and verified it was performed during "
            "the audit period. Confirmed that fraud risk scenarios were evaluated for "
            "key business processes. Inspected anti-fraud controls including separation "
            "of duties matrices, transaction monitoring rules, and whistleblower "
            "reporting mechanisms. Verified that suspicious activity monitoring is "
            "active for privileged accounts."
        ),
    },
    "CC3.4": {
        "category": "Risk Assessment",
        "activity": (
            "The entity identifies and assesses changes that could significantly impact "
            "the system of internal control. A formal change risk assessment process "
            "evaluates the security implications of significant operational changes "
            "including new products, acquisitions, infrastructure migrations, and "
            "changes to regulatory requirements."
        ),
        "test": (
            "Reviewed the change risk assessment process documentation. Selected a "
            "sample of 5 significant changes during the audit period and verified that "
            "a security impact assessment was performed for each. Confirmed that risk "
            "assessment findings were reviewed by the security team before changes were "
            "approved for implementation. Verified that the risk register was updated "
            "to reflect new risks introduced by significant changes."
        ),
    },

    # ── CC4: Monitoring Activities ──
    "CC4.1": {
        "category": "Monitoring Activities",
        "activity": (
            "The entity selects, develops, and performs ongoing and/or separate "
            "evaluations to ascertain whether the components of internal control are "
            "present and functioning. Continuous monitoring is implemented through "
            "automated tools that assess system configuration compliance, detect "
            "anomalous behavior, and report on key security metrics. Management reviews "
            "monitoring dashboards weekly."
        ),
        "test": (
            "Inspected the continuous monitoring program documentation. Reviewed the "
            "configuration of automated compliance scanning tools and verified that "
            "scans execute on the defined schedule. Selected a sample of 10 weekly "
            "management review records and confirmed that monitoring reports were "
            "reviewed and exceptions were documented. Verified that monitoring coverage "
            "includes all in-scope systems."
        ),
    },
    "CC4.2": {
        "category": "Monitoring Activities",
        "activity": (
            "The entity evaluates and communicates internal control deficiencies in a "
            "timely manner to those parties responsible for taking corrective action, "
            "including senior management and the Board of Directors as appropriate. "
            "A formal deficiency tracking process ensures that identified control "
            "weaknesses are remediated within defined SLAs based on severity."
        ),
        "test": (
            "Obtained the deficiency tracking log and verified that all identified "
            "deficiencies during the audit period were recorded and assigned to "
            "responsible parties. Verified that remediation SLAs were defined based on "
            "severity (critical: 7 days, high: 30 days, medium: 90 days). Selected "
            "a sample of 10 deficiencies and confirmed that corrective actions were "
            "implemented within the defined SLAs. Verified that critical deficiencies "
            "were reported to senior management within 24 hours."
        ),
    },

    # ── CC5: Control Activities ──
    "CC5.1": {
        "category": "Control Activities",
        "activity": (
            "The entity selects and develops control activities that contribute to "
            "the mitigation of risks to the achievement of objectives to acceptable "
            "levels. Controls are designed based on risk assessment results and are "
            "documented in a control catalog that maps each control to the risk it "
            "mitigates and the applicable Trust Services Criteria."
        ),
        "test": (
            "Obtained the control catalog and verified that controls are mapped to "
            "risks and Trust Services Criteria. Confirmed that control design was "
            "reviewed during the audit period. Selected a sample of 15 controls "
            "and verified that each has a documented design rationale, owner, and "
            "testing frequency. Reviewed the control design review process and confirmed "
            "that new controls undergo formal approval before implementation."
        ),
    },
    "CC5.2": {
        "category": "Control Activities",
        "activity": (
            "The entity also selects and develops general control activities over "
            "technology to support the achievement of objectives. Technology controls "
            "include logical access controls, change management procedures, system "
            "monitoring, and data backup and recovery mechanisms. These controls are "
            "implemented across the technology stack including infrastructure, "
            "application, and data layers."
        ),
        "test": (
            "Reviewed the technology control framework documentation. Verified that "
            "technology controls are implemented at infrastructure, application, and "
            "data layers. Tested a sample of controls at each layer including firewall "
            "rules, application authentication mechanisms, and database access controls. "
            "Confirmed that technology control configurations are managed through "
            "infrastructure-as-code and version controlled."
        ),
    },
    "CC5.3": {
        "category": "Control Activities",
        "activity": (
            "The entity deploys control activities through policies that establish "
            "what is expected and procedures that put policies into action. All "
            "security policies are reviewed annually, approved by the CISO, and "
            "published to the internal knowledge base. Procedures are documented "
            "as runbooks and standard operating procedures with step-by-step "
            "instructions for control execution."
        ),
        "test": (
            "Obtained the policy inventory and verified that all security policies "
            "were reviewed within the audit period. Confirmed that each policy has "
            "a designated owner, review date, and approval signature. Selected a "
            "sample of 10 procedures and verified that they include actionable steps, "
            "roles and responsibilities, and escalation paths. Verified that policy "
            "exceptions are formally documented and approved."
        ),
    },

    # ── CC6: Logical and Physical Access Controls ──
    "CC6.1": {
        "category": "Logical and Physical Access Controls",
        "activity": (
            "The entity implements logical access security software, infrastructure, "
            "and architectures over protected information assets to protect them from "
            "security events. Access control mechanisms include role-based access control "
            "(RBAC), multi-factor authentication (MFA), network segmentation, and "
            "encryption of data at rest and in transit. The entity enforces the principle "
            "of least privilege across all systems and environments."
        ),
        "test": (
            "Inspected access control configurations for production systems including "
            "the identity provider, cloud infrastructure, databases, and application "
            "layer. Verified that RBAC is implemented with documented role definitions. "
            "Tested MFA enforcement by attempting to authenticate without a second factor. "
            "Reviewed network segmentation rules and verified isolation between production "
            "and non-production environments. Verified encryption configurations for "
            "data at rest (AES-256) and in transit (TLS 1.2+) across all in-scope systems."
        ),
    },
    "CC6.2": {
        "category": "Logical and Physical Access Controls",
        "activity": (
            "Prior to issuing system credentials and granting system access, the entity "
            "registers and authorizes new internal and external users. The onboarding "
            "process includes identity verification, manager approval, and provisioning "
            "of access based on the employee's role and department. Access requests are "
            "tracked in the ticketing system with full audit trails."
        ),
        "test": (
            "Selected a sample of 25 new hires during the audit period and verified that "
            "each had a documented access request with manager approval prior to account "
            "creation. Confirmed that identity verification was completed before credentials "
            "were issued. Verified that provisioned access matched the approved role "
            "template. Reviewed the onboarding checklist and confirmed all steps were "
            "completed in sequence. Tested the automated provisioning workflow by "
            "reviewing system logs for provisioning events."
        ),
    },
    "CC6.3": {
        "category": "Logical and Physical Access Controls",
        "activity": (
            "The entity authorizes, modifies, or removes access to data, software, "
            "functions, and other protected information assets based on roles, "
            "responsibilities, or the system design and changes. Access reviews are "
            "conducted quarterly by system owners, and terminated employee accounts "
            "are disabled within 24 hours of separation. Role changes trigger an "
            "access review to ensure permissions are aligned with new responsibilities."
        ),
        "test": (
            "Obtained quarterly access review reports for all four quarters and verified "
            "that reviews were completed by designated system owners. Selected a sample "
            "of 20 terminated employees and verified that account deactivation occurred "
            "within 24 hours. Selected a sample of 10 role changes and confirmed that "
            "access was modified to align with the new role. Reviewed the access review "
            "methodology and verified that it includes comparison against role templates "
            "and identification of excessive privileges."
        ),
    },
    "CC6.4": {
        "category": "Logical and Physical Access Controls",
        "activity": (
            "The entity restricts physical access to facilities and protected "
            "information assets (for example, data center facilities, backup media, "
            "and other sensitive locations) to authorized personnel to meet the "
            "entity's objectives. Physical security controls include badge readers, "
            "biometric scanners, video surveillance, and visitor management procedures."
        ),
        "test": (
            "Inspected physical security controls at the corporate office and verified "
            "that badge readers are installed at all entry points. Reviewed the visitor "
            "management log and verified that all visitors were escorted and signed in. "
            "Inspected video surveillance system configuration and verified that cameras "
            "cover entry/exit points with recordings retained for 90 days. Reviewed "
            "physical access lists for server rooms and confirmed that only authorized "
            "personnel have access. Verified that terminated employees' badges are "
            "deactivated within 24 hours."
        ),
    },
    "CC6.5": {
        "category": "Logical and Physical Access Controls",
        "activity": (
            "The entity discontinues logical and physical protections over physical "
            "assets only after the ability to read or recover data and software from "
            "those assets has been diminished and is no longer required to meet the "
            "entity's objectives. Asset disposal procedures ensure that data is "
            "securely wiped or destroyed before hardware is decommissioned."
        ),
        "test": (
            "Obtained the asset disposal policy and verified that it requires secure "
            "data destruction prior to hardware decommissioning. Selected a sample of "
            "10 disposed assets during the audit period and verified that certificates "
            "of destruction were obtained. Reviewed the asset management database and "
            "confirmed that disposed assets were marked as decommissioned with the "
            "destruction method recorded."
        ),
    },
    "CC6.6": {
        "category": "Logical and Physical Access Controls",
        "activity": (
            "The entity implements logical access security measures to protect against "
            "threats from sources outside its system boundaries. Perimeter security "
            "controls include web application firewalls (WAF), DDoS protection, "
            "intrusion detection/prevention systems (IDS/IPS), and API rate limiting. "
            "The entity maintains a hardened network architecture with defense-in-depth "
            "principles applied at every layer."
        ),
        "test": (
            "Inspected firewall rules and verified that default-deny policies are "
            "in place. Reviewed WAF configuration and confirmed that OWASP Top 10 "
            "protections are enabled. Tested DDoS protection by reviewing mitigation "
            "logs for incidents during the audit period. Reviewed IDS/IPS alert logs "
            "and confirmed that alerts are triaged within defined SLAs. Inspected "
            "network architecture diagrams and verified defense-in-depth implementation "
            "including DMZ, internal segmentation, and microsegmentation for critical services."
        ),
    },
    "CC6.7": {
        "category": "Logical and Physical Access Controls",
        "activity": (
            "The entity restricts the transmission, movement, and removal of "
            "information to authorized internal and external users and processes, "
            "and protects it during transmission, movement, or removal to meet the "
            "entity's objectives. Data loss prevention (DLP) controls are implemented "
            "to detect and prevent unauthorized data exfiltration via email, web "
            "uploads, removable media, and cloud storage."
        ),
        "test": (
            "Inspected DLP policy configurations and verified that rules are in place "
            "for sensitive data patterns (PII, financial data, credentials). Reviewed "
            "DLP incident logs for the audit period and confirmed that violations were "
            "investigated. Verified that email encryption is enforced for messages "
            "containing sensitive data. Tested removable media controls by attempting "
            "to copy files to a USB device on a sample workstation."
        ),
    },
    "CC6.8": {
        "category": "Logical and Physical Access Controls",
        "activity": (
            "The entity implements controls to prevent or detect and act upon the "
            "introduction of unauthorized or malicious software. Endpoint protection "
            "is deployed across all workstations and servers, including anti-malware, "
            "endpoint detection and response (EDR), and host-based intrusion prevention. "
            "Application whitelisting is enforced on production servers."
        ),
        "test": (
            "Verified endpoint protection deployment across all workstations and "
            "servers by reviewing the EDR management console. Confirmed that signature "
            "updates are applied daily and behavioral detection rules are updated weekly. "
            "Reviewed malware detection logs for the audit period and verified that "
            "detections were investigated and remediated. Tested application whitelisting "
            "on a sample production server by attempting to execute an unauthorized binary."
        ),
    },

    # ── CC7: System Operations ──
    "CC7.1": {
        "category": "System Operations",
        "activity": (
            "To meet its objectives, the entity uses detection and monitoring "
            "procedures to identify changes to configurations that result in the "
            "introduction of new vulnerabilities, and the susceptibility of system "
            "components to exploitation of those vulnerabilities. Vulnerability "
            "management includes regular scanning, prioritization based on CVSS scores, "
            "and remediation within defined SLAs."
        ),
        "test": (
            "Reviewed vulnerability scanning reports for the audit period and verified "
            "that scans were performed at least monthly across all in-scope systems. "
            "Selected a sample of 20 critical and high vulnerabilities and verified "
            "remediation within defined SLAs (critical: 72 hours, high: 14 days). "
            "Reviewed the vulnerability management policy and confirmed that exceptions "
            "require formal risk acceptance. Inspected patch management reports and "
            "verified that operating system and application patches are applied on schedule."
        ),
    },
    "CC7.2": {
        "category": "System Operations",
        "activity": (
            "The entity monitors system components and the operation of those "
            "components for anomalies that are indicative of malicious acts, natural "
            "disasters, and errors affecting the entity's ability to meet its objectives. "
            "Monitoring includes SIEM-based correlation, infrastructure health monitoring, "
            "application performance monitoring (APM), and user behavior analytics (UBA). "
            "Alerting thresholds are reviewed quarterly and tuned based on operational feedback."
        ),
        "test": (
            "Inspected SIEM configuration and verified that correlation rules are active "
            "for authentication anomalies, privilege escalation, data exfiltration indicators, "
            "and configuration changes. Reviewed alerting threshold documentation and "
            "confirmed quarterly reviews were performed. Selected a sample of 25 alerts "
            "and verified that each was triaged within the defined SLA. Reviewed infrastructure "
            "monitoring dashboards and confirmed coverage of CPU, memory, disk, and network "
            "metrics for all production systems. Verified that APM is deployed across all "
            "customer-facing applications."
        ),
    },
    "CC7.3": {
        "category": "System Operations",
        "activity": (
            "The entity evaluates security events to determine whether they could or "
            "have resulted in a failure of the entity to meet its objectives. Security "
            "event classification follows a defined taxonomy with severity levels that "
            "determine escalation paths and response timelines. All security events are "
            "documented in the incident management system with root cause analysis "
            "performed for events classified as medium severity or higher."
        ),
        "test": (
            "Obtained the security event classification policy and verified that severity "
            "levels and escalation paths are defined. Selected a sample of 15 security "
            "events during the audit period and verified that classification, triage, and "
            "escalation procedures were followed per policy. Reviewed root cause analysis "
            "reports for medium and high severity events and confirmed that lessons learned "
            "were documented and remediation actions were tracked to completion."
        ),
    },
    "CC7.4": {
        "category": "System Operations",
        "activity": (
            "The entity responds to identified security incidents by executing a defined "
            "incident response program to understand, contain, remediate, and communicate "
            "security incidents, as appropriate. The incident response program includes a "
            "documented incident response plan, trained incident responders, established "
            "communication channels, and regular tabletop exercises. Post-incident reviews "
            "are conducted for all incidents to identify process improvements."
        ),
        "test": (
            "Obtained the incident response plan and verified that it addresses all phases "
            "of incident response (preparation, identification, containment, eradication, "
            "recovery, lessons learned). Verified that tabletop exercises were conducted "
            "during the audit period. Reviewed incident tickets for all security incidents "
            "and confirmed that response procedures were followed. Verified that post-incident "
            "reviews were documented and remediation actions were completed. Confirmed that "
            "the incident response team roster is current and includes after-hours contact "
            "information."
        ),
    },
    "CC7.5": {
        "category": "System Operations",
        "activity": (
            "The entity identifies, develops, and implements activities to recover "
            "from identified security incidents. Recovery plans include defined "
            "recovery time objectives (RTO) and recovery point objectives (RPO) for "
            "critical systems. Recovery procedures are tested at least annually to "
            "ensure they can be executed within defined objectives."
        ),
        "test": (
            "Obtained the disaster recovery plan and verified that RTO and RPO are "
            "defined for all critical systems. Reviewed the most recent recovery test "
            "results and verified that recovery was achieved within defined objectives. "
            "Confirmed that recovery procedures are documented as step-by-step runbooks. "
            "Verified that backup integrity is tested monthly through automated restoration "
            "testing. Reviewed the results of the annual disaster recovery exercise."
        ),
    },

    # ── CC8: Change Management ──
    "CC8.1": {
        "category": "Change Management",
        "activity": (
            "The entity authorizes, designs, develops or acquires, configures, "
            "documents, tests, approves, and implements changes to infrastructure, "
            "data, software, and procedures to meet its objectives. The change "
            "management process includes risk assessment, peer review, testing in "
            "a staging environment, approval by designated approvers, and deployment "
            "through an automated CI/CD pipeline with rollback capability."
        ),
        "test": (
            "Selected a sample of 25 change requests during the audit period and "
            "verified that each followed the documented change management process "
            "including risk assessment, peer review, staging environment testing, and "
            "approval prior to production deployment. Reviewed CI/CD pipeline "
            "configuration and verified that automated tests (unit, integration, "
            "security) execute before deployment. Confirmed that rollback procedures "
            "are documented and tested. Reviewed emergency change procedures and "
            "verified that post-hoc documentation and approval were completed for "
            "all emergency changes during the period."
        ),
    },

    # ── CC9: Risk Mitigation ──
    "CC9.1": {
        "category": "Risk Mitigation",
        "activity": (
            "The entity identifies, selects, and develops risk mitigation activities "
            "for risks arising from potential business disruptions. Business continuity "
            "planning covers all critical business processes and supporting technology "
            "systems. The business continuity plan (BCP) and disaster recovery plan "
            "(DRP) are reviewed annually and tested at least once per year."
        ),
        "test": (
            "Reviewed business continuity and disaster recovery plans and verified "
            "that they cover all critical systems and processes. Confirmed that annual "
            "testing was conducted during the audit period. Inspected test results and "
            "verified that recovery was achieved within defined objectives. Reviewed "
            "backup procedures and confirmed that backups are performed on schedule "
            "with integrity verification. Verified that backup media is stored in a "
            "geographically separate location."
        ),
    },
    "CC9.2": {
        "category": "Risk Mitigation",
        "activity": (
            "The entity assesses and manages risks associated with vendors and "
            "business partners. A formal vendor risk management program evaluates "
            "the security posture of third-party service providers before onboarding "
            "and periodically thereafter. Contracts include security and compliance "
            "requirements and the right to audit."
        ),
        "test": (
            "Obtained the vendor management policy and verified that it includes "
            "security assessment requirements. Selected a sample of 10 vendors and "
            "verified that initial security assessments were completed before onboarding. "
            "Reviewed annual vendor reassessment reports and confirmed that high-risk "
            "vendors were reassessed during the audit period. Verified that contracts "
            "include data protection requirements, incident notification obligations, "
            "and audit rights."
        ),
    },

    # ── A1: Availability ──
    "A1.1": {
        "category": "Availability",
        "activity": (
            "The entity maintains, monitors, and evaluates current processing capacity "
            "and use of system components (infrastructure, data, and software) to manage "
            "capacity demand and to enable the implementation of additional capacity to "
            "help meet its objectives. Capacity planning includes monitoring resource "
            "utilization trends, forecasting future needs, and provisioning resources "
            "proactively to maintain performance within defined thresholds."
        ),
        "test": (
            "Reviewed capacity monitoring dashboards and verified that utilization "
            "metrics are tracked for compute, storage, memory, and network bandwidth. "
            "Inspected auto-scaling configurations and verified that scaling policies "
            "are in place for production workloads. Reviewed capacity planning reports "
            "and confirmed that quarterly forecasts are prepared. Verified that capacity "
            "alerts are configured to trigger when utilization exceeds 80%."
        ),
    },
    "A1.2": {
        "category": "Availability",
        "activity": (
            "The entity authorizes, designs, develops or acquires, implements, operates, "
            "approves, maintains, and monitors environmental protections, software, data "
            "backup and recovery infrastructure, and recovery procedures to meet its "
            "objectives. The entity maintains redundant infrastructure across multiple "
            "availability zones with automated failover capabilities."
        ),
        "test": (
            "Reviewed the infrastructure architecture and verified that production "
            "systems are deployed across multiple availability zones. Tested automated "
            "failover by reviewing documentation of failover events during the audit "
            "period. Verified that database replication is configured with synchronous "
            "or near-synchronous replication. Reviewed backup procedures and tested "
            "restoration from backup for a sample of 5 systems. Verified that backup "
            "monitoring alerts are configured for failed backup jobs."
        ),
    },
    "A1.3": {
        "category": "Availability",
        "activity": (
            "The entity tests recovery plan procedures supporting system recovery to "
            "meet its objectives. Recovery testing includes planned failover tests, "
            "backup restoration tests, and full disaster recovery exercises. Test "
            "results are documented and reviewed by management, and identified gaps "
            "are remediated."
        ),
        "test": (
            "Reviewed recovery test documentation and verified that testing was "
            "performed during the audit period. Inspected test results for the annual "
            "disaster recovery exercise and confirmed that all critical systems were "
            "recovered within defined RTOs. Reviewed backup restoration test logs and "
            "verified that monthly restoration tests were performed. Confirmed that "
            "test findings were documented and remediation actions were tracked to "
            "completion."
        ),
    },

    # ── C1: Confidentiality ──
    "C1.1": {
        "category": "Confidentiality",
        "activity": (
            "The entity identifies and maintains confidential information to meet the "
            "entity's objectives related to confidentiality. A formal data classification "
            "policy defines categories of information (public, internal, confidential, "
            "restricted) and specifies handling requirements for each category. Data "
            "discovery and classification tools are used to identify and label "
            "confidential information across structured and unstructured data stores."
        ),
        "test": (
            "Obtained the data classification policy and verified that classification "
            "levels are defined with corresponding handling requirements. Reviewed the "
            "data inventory and confirmed that systems containing confidential and "
            "restricted data are identified. Inspected data classification tool "
            "configurations and reviewed scan results. Verified that confidential data "
            "is encrypted at rest and in transit. Selected a sample of 10 systems "
            "containing confidential data and verified that access controls are "
            "consistent with the classification level."
        ),
    },
    "C1.2": {
        "category": "Confidentiality",
        "activity": (
            "The entity disposes of confidential information to meet the entity's "
            "objectives related to confidentiality. Data retention policies define "
            "maximum retention periods for each data classification level. Automated "
            "data deletion processes are implemented to purge data that exceeds the "
            "defined retention period. Secure deletion methods are used to ensure that "
            "confidential data cannot be recovered after disposal."
        ),
        "test": (
            "Reviewed the data retention policy and verified that retention periods "
            "are defined for each data classification level. Inspected automated "
            "data purging configurations and verified that processes execute on "
            "schedule. Selected a sample of 5 deletion events and confirmed that "
            "secure deletion methods were used. Verified that deletion logs are "
            "maintained as evidence of compliance with retention policies."
        ),
    },
}

# Criteria groups for the controls table layout
_CRITERIA_GROUPS = [
    ("Control Environment (CC1)", ["CC1.1", "CC1.2", "CC1.3", "CC1.4", "CC1.5"]),
    ("Communication and Information (CC2)", ["CC2.1", "CC2.2", "CC2.3"]),
    ("Risk Assessment (CC3)", ["CC3.1", "CC3.2", "CC3.3", "CC3.4"]),
    ("Monitoring Activities (CC4)", ["CC4.1", "CC4.2"]),
    ("Control Activities (CC5)", ["CC5.1", "CC5.2", "CC5.3"]),
    ("Logical and Physical Access Controls (CC6)", [
        "CC6.1", "CC6.2", "CC6.3", "CC6.4", "CC6.5", "CC6.6", "CC6.7", "CC6.8",
    ]),
    ("System Operations (CC7)", ["CC7.1", "CC7.2", "CC7.3", "CC7.4", "CC7.5"]),
    ("Change Management (CC8)", ["CC8.1"]),
    ("Risk Mitigation (CC9)", ["CC9.1", "CC9.2"]),
    ("Availability (A1)", ["A1.1", "A1.2", "A1.3"]),
    ("Confidentiality (C1)", ["C1.1", "C1.2"]),
]


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


# ═══════════════════════════════════════════════════════════════════════
# Content generators
# ═══════════════════════════════════════════════════════════════════════


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
        Spacer(1, 0.3 * inch),
        Paragraph("Trust Services Categories: Security, Availability, Confidentiality", STYLE_SUBTITLE),
        Spacer(1, 0.5 * inch),
        Paragraph("Prepared by:", STYLE_SUBTITLE),
        Paragraph("<b>Independent Audit Partners LLP</b>", STYLE_SUBTITLE),
        Paragraph("Certified Public Accountants", STYLE_SMALL),
        Spacer(1, 1.0 * inch),
        Paragraph(
            "This report is intended solely for the information and use of the management "
            f"of {company}, user entities, and prospective user entities. This report is not "
            "intended to be and should not be used by anyone other than these specified parties.",
            STYLE_SMALL,
        ),
        Spacer(1, 0.3 * inch),
        Paragraph(
            "This report, including the description of tests of controls and results thereof "
            "in Sections IV and V, is as of and for the period specified above. Any projection "
            "of the information in this report to future periods is subject to the risk that, "
            "because of change, the description may no longer portray the controls in existence. "
            "The criteria against which the controls were evaluated are the Trust Services Criteria "
            "established by the AICPA.",
            STYLE_SMALL,
        ),
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
        ("", "I. Incident Management"),
        ("", "J. Business Continuity and Disaster Recovery"),
        ("", "K. Data Classification and Handling"),
        ("Section III-B", "Testing Methodology"),
        ("Section IV", "Trust Services Criteria and Control Activities"),
        ("", "Control Environment (CC1)"),
        ("", "Communication and Information (CC2)"),
        ("", "Risk Assessment (CC3)"),
        ("", "Monitoring Activities (CC4)"),
        ("", "Control Activities (CC5)"),
        ("", "Logical and Physical Access Controls (CC6)"),
        ("", "System Operations (CC7)"),
        ("", "Change Management (CC8)"),
        ("", "Risk Mitigation (CC9)"),
        ("", "Availability (A1)"),
        ("", "Confidentiality (C1)"),
        ("Section IV-B", "Summary of Testing Results"),
        ("Section V", "Findings and Observations"),
        ("Section VI", "Management's Response to Findings"),
        ("Appendix A", "Complementary User Entity Controls"),
        ("Appendix B", "Complementary Subservice Organization Controls"),
        ("Appendix C", "Glossary of Terms"),
    ]
    for section, title in toc_entries:
        if section:
            elements.append(Paragraph(f"<b>{section}</b> — {title}", STYLE_BODY))
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
        f"including the completeness, accuracy, and method of presentation of both the Description "
        f"and the assertion; (2) providing the services covered by the Description; (3) specifying "
        f"the controls that meet the applicable trust services criteria and stating them in the "
        f"Description; and (4) designing, implementing, and documenting the controls to provide "
        f"reasonable assurance that the applicable trust services criteria are met.", STYLE_BODY))
    elements.append(Paragraph(
        f"In addition, {company} is responsible for providing a Description of its system that "
        f"is prepared in accordance with the Description Criteria and for having a reasonable basis "
        f"for its assertion. {company} is also responsible for selecting the trust services "
        f"categories and criteria addressed by the engagement, and for the completeness of the "
        f"boundaries of the system described.", STYLE_BODY))

    elements.append(Paragraph("<b>Service Auditor's Responsibilities</b>", STYLE_H2))
    elements.append(Paragraph(
        "Our responsibility is to express an opinion on the Description and on the suitability of the "
        "design and operating effectiveness of controls stated in the Description based on our "
        "examination. Our examination was conducted in accordance with attestation standards "
        "established by the American Institute of Certified Public Accountants (AICPA) and, "
        "accordingly, included procedures that we considered necessary in the circumstances. Those "
        "standards require that we plan and perform the examination to obtain reasonable assurance "
        "about whether, in all material respects, the Description is fairly presented based on the "
        "Description Criteria, and the controls stated therein are suitably designed and operating "
        "effectively to meet the applicable Trust Services Criteria.", STYLE_BODY))
    elements.append(Paragraph(
        "An examination of the description of a service organization's system and the suitability "
        "of the design and operating effectiveness of controls involves performing procedures to "
        "obtain evidence about the fairness of the presentation of the Description and the "
        "suitability of the design and operating effectiveness of those controls. The nature, "
        "timing, and extent of the procedures selected depend on our judgment, including an "
        "assessment of the risks that the Description is not fairly presented and that the "
        "controls are not suitably designed or operating effectively.", STYLE_BODY))
    elements.append(Paragraph(
        "Our procedures included: (a) obtaining an understanding of the system and the service "
        "organization's service commitments and system requirements; (b) assessing the risks that "
        "the Description is not fairly presented and that controls were not suitably designed or "
        "operating effectively; (c) performing procedures to obtain evidence about whether the "
        "Description is fairly presented and the controls were suitably designed and operating "
        "effectively; and (d) evaluating the overall presentation of the Description.", STYLE_BODY))

    elements.append(Paragraph("<b>Inherent Limitations</b>", STYLE_H2))
    elements.append(Paragraph(
        "The Description is prepared to meet the common needs of a broad range of report users and "
        "may not, therefore, include every aspect of the system that each individual report user may "
        "consider important to their particular needs. Because of their nature, controls at a service "
        "organization may not prevent, or detect and correct, all misstatements or omissions in "
        "processing or reporting. Also, the projection to the future of any evaluation of the "
        "fairness of the presentation of the Description, or conclusions about the suitability of "
        "the design or operating effectiveness of the controls, is subject to the risk that the "
        "system at the service organization may change.", STYLE_BODY))

    elements.append(Paragraph("<b>Opinion</b>", STYLE_H2))
    if opinion == "unqualified":
        elements.append(Paragraph(
            f"In our opinion, in all material respects:", STYLE_BODY))
        elements.append(Paragraph(
            f"(a) The Description fairly presents the {company} system that was designed and "
            f"implemented throughout the period {audit_period}, based on the applicable "
            f"Description Criteria.", STYLE_BODY_INDENT))
        elements.append(Paragraph(
            f"(b) The controls stated in the Description were suitably designed to provide "
            f"reasonable assurance that the service organization's service commitments and system "
            f"requirements were achieved based on the applicable Trust Services Criteria, "
            f"throughout the period {audit_period}.", STYLE_BODY_INDENT))
        elements.append(Paragraph(
            f"(c) The controls stated in the Description operated effectively to provide reasonable "
            f"assurance that the service organization's service commitments and system requirements "
            f"were achieved based on the applicable Trust Services Criteria, throughout the period "
            f"{audit_period}.", STYLE_BODY_INDENT))
    else:
        elements.append(Paragraph(
            f"In our opinion, except for the matters described in our findings (Section V):", STYLE_BODY))
        elements.append(Paragraph(
            f"(a) The Description fairly presents the {company} system as designed and "
            f"implemented throughout the period {audit_period}.", STYLE_BODY_INDENT))
        elements.append(Paragraph(
            f"(b) However, certain controls stated in the Description were not suitably designed or "
            f"operating effectively to provide reasonable assurance that the service organization's "
            f"service commitments and system requirements were achieved based on the applicable Trust "
            f"Services Criteria, as described in Section V of this report.", STYLE_BODY_INDENT))

    elements.append(Spacer(1, 0.3 * inch))
    elements.append(Paragraph(
        "Respectfully submitted,", STYLE_BODY))
    elements.append(Spacer(1, 0.15 * inch))
    elements.append(Paragraph(
        "<b>Independent Audit Partners LLP</b>", STYLE_BODY))
    elements.append(Paragraph("Certified Public Accountants", STYLE_SMALL))
    elements.append(Paragraph("San Francisco, California", STYLE_SMALL))
    elements.append(Paragraph("March 15, 2026", STYLE_SMALL))
    elements.append(PageBreak())
    return elements


def _management_assertion(company: str, audit_period: str) -> list:
    elements: list = []
    elements.append(Paragraph("Section II: Management's Assertion", STYLE_H1))
    elements.append(Spacer(1, 0.15 * inch))
    elements.append(Paragraph(
        f"We, the management of {company}, are responsible for:", STYLE_BODY))
    responsibilities = [
        "Designing, implementing, operating, and maintaining effective controls within the "
        f"system throughout the period {audit_period};",
        "Providing a Description of the system that is prepared in accordance with the "
        "Description Criteria established by the AICPA;",
        "Selecting the Trust Services Categories addressed by the engagement "
        "(Security, Availability, and Confidentiality);",
        "Identifying the risks that threaten the achievement of the service organization's "
        "service commitments and system requirements;",
        "Identifying, designing, implementing, and documenting controls to mitigate those risks;",
        "Stating in this assertion that the controls were suitably designed and operating "
        "effectively throughout the period.",
    ]
    for r in responsibilities:
        elements.append(Paragraph(f"&bull; {r}", STYLE_BODY_INDENT))

    elements.append(Spacer(1, 0.1 * inch))
    elements.append(Paragraph("<b>Management's Assertion</b>", STYLE_H2))
    elements.append(Paragraph(
        f"We assert that:", STYLE_BODY))
    elements.append(Paragraph(
        f"(a) The accompanying Description fairly presents the {company} system that was "
        f"designed and implemented throughout the period {audit_period}, based on the criteria "
        f"for a description of a service organization's system set forth in DC Section 200A, "
        f"2018 Description Criteria for a Description of a Service Organization's System in a "
        f"SOC 2 Report (AICPA, Description Criteria).", STYLE_BODY_INDENT))
    elements.append(Paragraph(
        f"(b) The controls stated in the Description were suitably designed to provide reasonable "
        f"assurance that the service organization's service commitments and system requirements "
        f"were achieved based on the Trust Services Criteria relevant to Security, Availability, "
        f"and Confidentiality (applicable trust services criteria) set forth in TSP Section 100, "
        f"2017 Trust Services Criteria for Security, Availability, Processing Integrity, "
        f"Confidentiality, and Privacy (AICPA, Trust Services Criteria), throughout the period "
        f"{audit_period}.", STYLE_BODY_INDENT))
    elements.append(Paragraph(
        f"(c) The controls stated in the Description operated effectively to provide reasonable "
        f"assurance that the service organization's service commitments and system requirements "
        f"were achieved based on the applicable Trust Services Criteria, throughout the period "
        f"{audit_period}.", STYLE_BODY_INDENT))

    elements.append(Spacer(1, 0.1 * inch))
    elements.append(Paragraph("<b>Basis for Assertion</b>", STYLE_H2))
    elements.append(Paragraph(
        f"The assertion is based on the criteria described in the AICPA's Trust Services Criteria "
        f"(TSP Section 100). The applicable trust services categories covered by this report are "
        f"Security, Availability, and Confidentiality. The criteria are the control objectives "
        f"and related controls specified by the AICPA.", STYLE_BODY))
    elements.append(Paragraph(
        f"There are inherent limitations in any system of internal control, including the "
        f"possibility of human error and the circumvention of controls. Because of these "
        f"inherent limitations, internal control over a service organization's system may not "
        f"prevent or detect all errors or omissions in processing or reporting. The design of "
        f"any system of controls is based in part upon certain assumptions about the likelihood "
        f"of future events, and there can be no assurance that any design will succeed in "
        f"achieving its stated goals under all potential conditions. Additionally, projections "
        f"of any evaluation of the system to future periods are subject to the risk that "
        f"controls may become inadequate because of changes in conditions, or that the degree "
        f"of compliance with controls may deteriorate.", STYLE_BODY))

    elements.append(Paragraph("<b>Complementary User Entity Controls</b>", STYLE_H2))
    elements.append(Paragraph(
        f"The {company} system was designed with the assumption that certain controls would "
        f"be implemented by user entities. The description of these complementary user entity "
        f"controls (CUECs) is presented in Appendix A to this report. Our assertion and the "
        f"service auditor's opinion do not extend to the operating effectiveness of these "
        f"complementary user entity controls. User entities should evaluate whether the "
        f"complementary user entity controls identified in Appendix A have been implemented.", STYLE_BODY))

    elements.append(Paragraph("<b>Complementary Subservice Organization Controls</b>", STYLE_H2))
    elements.append(Paragraph(
        f"{company} uses certain subservice organizations in delivering its services. The "
        f"description of the boundaries of the system in Section III identifies the subservice "
        f"organizations and the functions they perform. The complementary subservice organization "
        f"controls expected to be implemented by these organizations are described in Appendix B. "
        f"Our assertion and the service auditor's opinion do not extend to the controls of these "
        f"subservice organizations.", STYLE_BODY))

    elements.append(Spacer(1, 0.3 * inch))
    elements.append(Paragraph(f"Signed: Management of {company}", STYLE_BODY))
    elements.append(Paragraph("March 10, 2026", STYLE_SMALL))
    elements.append(PageBreak())
    return elements


def _system_description(company: str, industry: str, desc_config: dict) -> list:
    elements: list = []
    elements.append(Paragraph("Section III: System Description", STYLE_H1))

    # A. Overview
    elements.append(Paragraph("<b>A. Overview of Operations</b>", STYLE_H2))
    for para in desc_config.get("overview_paragraphs", [desc_config.get("overview", "")]):
        elements.append(Paragraph(para, STYLE_BODY))

    # B. Service Commitments
    elements.append(Paragraph(
        "<b>B. Principal Service Commitments and System Requirements</b>", STYLE_H2))
    elements.append(Paragraph(
        f"{company} establishes operational objectives that are consistent with its mission "
        f"and strategic direction. These objectives encompass performance, compliance, and "
        f"reporting requirements. Management has established the following principal service "
        f"commitments and system requirements that are the basis for the trust services "
        f"criteria addressed in this report:", STYLE_BODY))
    elements.append(Paragraph("<b>Service Commitments:</b>", STYLE_H3))
    for commitment in desc_config.get("service_commitments", []):
        elements.append(Paragraph(f"&bull; {commitment}", STYLE_BODY_INDENT))
    elements.append(Paragraph("<b>System Requirements:</b>", STYLE_H3))
    for req in desc_config.get("system_requirements", [
        "The system must authenticate all users before granting access to any resources.",
        "The system must encrypt all sensitive data at rest and in transit.",
        "The system must maintain audit logs of all security-relevant events.",
        "The system must be available with a minimum uptime of 99.9%.",
        "The system must restrict access to confidential data to authorized personnel only.",
    ]):
        elements.append(Paragraph(f"&bull; {req}", STYLE_BODY_INDENT))

    # C. Infrastructure
    elements.append(Paragraph("<b>C. Infrastructure and Technology</b>", STYLE_H2))
    for para in desc_config.get("infrastructure_paragraphs", [desc_config.get("infrastructure", "")]):
        elements.append(Paragraph(para, STYLE_BODY))

    if desc_config.get("infrastructure_components"):
        elements.append(Paragraph("<b>Key Infrastructure Components:</b>", STYLE_H3))
        for comp in desc_config["infrastructure_components"]:
            elements.append(Paragraph(f"&bull; {comp}", STYLE_BODY_INDENT))

    # D. Data Flows
    elements.append(Paragraph("<b>D. Data Flows and Processing</b>", STYLE_H2))
    for para in desc_config.get("data_flow_paragraphs", [desc_config.get("data_flows", "")]):
        elements.append(Paragraph(para, STYLE_BODY))

    # E. Personnel
    elements.append(Paragraph("<b>E. Personnel and Organizational Structure</b>", STYLE_H2))
    for para in desc_config.get("personnel_paragraphs", [desc_config.get("personnel", "")]):
        elements.append(Paragraph(para, STYLE_BODY))

    if desc_config.get("key_roles"):
        elements.append(Paragraph("<b>Key Security and Compliance Roles:</b>", STYLE_H3))
        for role in desc_config["key_roles"]:
            elements.append(Paragraph(f"&bull; {role}", STYLE_BODY_INDENT))

    # F. Security Policies
    elements.append(Paragraph("<b>F. Security Policies and Practices</b>", STYLE_H2))
    elements.append(Paragraph(
        f"The following security policies and practices are in place at {company} to support "
        f"the trust services criteria:", STYLE_BODY))
    for practice in desc_config.get("security_practices", []):
        elements.append(Paragraph(f"&bull; {practice}", STYLE_BODY_INDENT))

    if desc_config.get("security_policy_details"):
        for detail_section in desc_config["security_policy_details"]:
            elements.append(Paragraph(f"<b>{detail_section['title']}</b>", STYLE_H3))
            for para in detail_section.get("paragraphs", []):
                elements.append(Paragraph(para, STYLE_BODY))

    # G. Risk Management
    elements.append(Paragraph("<b>G. Risk Management Program</b>", STYLE_H2))
    for para in desc_config.get("risk_management_paragraphs", []):
        elements.append(Paragraph(para, STYLE_BODY))
    if desc_config.get("risk_management_items"):
        for item in desc_config["risk_management_items"]:
            elements.append(Paragraph(f"&bull; {item}", STYLE_BODY_INDENT))

    # H. Third-Party Management
    elements.append(Paragraph(
        "<b>H. Third-Party and Subservice Organization Management</b>", STYLE_H2))
    elements.append(Paragraph(
        f"{company} relies on the following key subservice organizations in delivering its "
        f"services. The controls of these subservice organizations are excluded from the scope "
        f"of this report. Users should consider the need to obtain SOC reports from these "
        f"organizations to gain a complete understanding of the control environment.", STYLE_BODY))
    for vendor in desc_config.get("subservice_orgs", []):
        elements.append(Paragraph(f"&bull; {vendor}", STYLE_BODY_INDENT))

    if desc_config.get("vendor_management_details"):
        elements.append(Spacer(1, 0.1 * inch))
        for para in desc_config["vendor_management_details"]:
            elements.append(Paragraph(para, STYLE_BODY))

    # I. Incident Management
    elements.append(Paragraph("<b>I. Incident Management</b>", STYLE_H2))
    for para in desc_config.get("incident_management_paragraphs", [
        f"{company} maintains a formal incident management program that provides a structured "
        "approach to identifying, classifying, containing, eradicating, and recovering from "
        "security incidents. The program includes defined roles and responsibilities, escalation "
        "procedures, and communication protocols.",
    ]):
        elements.append(Paragraph(para, STYLE_BODY))

    # J. Business Continuity
    elements.append(Paragraph("<b>J. Business Continuity and Disaster Recovery</b>", STYLE_H2))
    for para in desc_config.get("bcdr_paragraphs", [
        f"{company} maintains business continuity and disaster recovery plans designed to "
        "minimize the impact of disruptions to critical business operations and technology "
        "systems. Plans are reviewed annually and tested at least once per year.",
    ]):
        elements.append(Paragraph(para, STYLE_BODY))

    # K. Data Classification
    elements.append(Paragraph("<b>K. Data Classification and Handling</b>", STYLE_H2))
    for para in desc_config.get("data_classification_paragraphs", [
        f"{company} maintains a data classification policy that categorizes information into "
        "four levels: Public, Internal, Confidential, and Restricted. Each classification level "
        "has defined handling requirements including encryption, access controls, retention "
        "periods, and disposal procedures.",
    ]):
        elements.append(Paragraph(para, STYLE_BODY))

    elements.append(PageBreak())
    return elements


def _operational_statistics(company: str, stats_config: dict | None = None) -> list:
    """Generate operational statistics tables — common in real SOC-2 reports."""
    if not stats_config:
        return []

    elements: list = []
    elements.append(Paragraph("Section III-A: Operational Statistics", STYLE_H1))
    elements.append(Paragraph(
        f"The following operational statistics are provided to give additional context "
        f"regarding the scale and maturity of {company}'s security and operations programs "
        f"during the audit period.", STYLE_BODY))

    for table_config in stats_config:
        elements.append(Paragraph(f"<b>{table_config['title']}</b>", STYLE_H2))
        if table_config.get("description"):
            elements.append(Paragraph(table_config["description"], STYLE_BODY))

        header = [Paragraph(f"<b>{h}</b>", STYLE_CELL_BOLD) for h in table_config["headers"]]
        rows = [header]
        for row_data in table_config["rows"]:
            rows.append([Paragraph(str(cell), STYLE_CELL) for cell in row_data])

        col_widths = table_config.get("col_widths",
            [6.5 * inch / len(table_config["headers"])] * len(table_config["headers"]))

        tbl = Table(rows, colWidths=col_widths, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#f8f9fa")]),
        ]))
        elements.append(tbl)
        elements.append(Spacer(1, 0.25 * inch))

    elements.append(PageBreak())
    return elements


def _controls_methodology() -> list:
    elements: list = []
    elements.append(Paragraph("Section III-B: Testing Methodology", STYLE_H1))
    elements.append(Paragraph(
        "The service auditor's examination was conducted in accordance with attestation standards "
        "established by the American Institute of Certified Public Accountants (AICPA). The "
        "following methodology was applied to evaluate the design and operating effectiveness "
        "of the controls described in this report.", STYLE_BODY))

    elements.append(Paragraph("<b>Test Procedures</b>", STYLE_H2))
    elements.append(Paragraph(
        "The following types of test procedures were performed during the examination:", STYLE_BODY))
    procedures = [
        ("<b>Inquiry:</b> Discussions were held with management and relevant personnel to obtain "
         "an understanding of the design and implementation of controls. We conducted interviews "
         "with system administrators, security engineers, compliance officers, and operational "
         "staff. Inquiries were designed to corroborate written policies and procedures and to "
         "understand how controls operate in practice."),
        ("<b>Observation:</b> We observed the application of specific controls by operations and "
         "security personnel during site visits and remote sessions. Observations included "
         "monitoring activities, change management processes, incident response procedures, "
         "and access provisioning workflows. Observations were performed at multiple points "
         "during the audit period to assess consistency of control execution."),
        ("<b>Inspection:</b> We inspected documents, reports, and electronic records to evaluate "
         "the design and operating effectiveness of controls. This included review of policies, "
         "configuration settings, access logs, change records, monitoring dashboards, incident "
         "reports, risk assessments, and vendor management documentation. Inspected documents "
         "were compared against expected evidence to confirm that controls operated as described."),
        ("<b>Re-performance:</b> For a sample of transactions and events, we independently "
         "re-performed control activities to verify that they operated as described. Re-performance "
         "testing included access provisioning and deprovisioning, change approvals, backup "
         "restoration, and vulnerability remediation verification. Re-performance provides the "
         "highest level of assurance that controls are operating effectively."),
    ]
    for proc in procedures:
        elements.append(Paragraph(f"&bull; {proc}", STYLE_BODY_INDENT))

    elements.append(Paragraph("<b>Sampling Approach</b>", STYLE_H2))
    elements.append(Paragraph(
        "For controls that operate on a transaction or event basis, we selected samples based "
        "on the following guidelines:", STYLE_BODY))
    sampling = [
        "For daily controls: a sample of 25 items was selected across the audit period.",
        "For weekly controls: a sample of 10 items was selected.",
        "For monthly controls: all 12 instances were tested.",
        "For quarterly controls: all 4 instances were tested.",
        "For annual controls: the single instance was tested.",
        "For event-driven controls: a sample of 25 items was selected, or all items if fewer than 25.",
    ]
    for s in sampling:
        elements.append(Paragraph(f"&bull; {s}", STYLE_BODY_INDENT))
    elements.append(Paragraph(
        "Samples were selected using a combination of random and judgmental sampling methods. "
        "Judgmental sampling was used when the population was small or when specific items were "
        "identified as higher risk. In all cases, the sample size was sufficient to provide "
        "reasonable assurance about the operating effectiveness of the control.", STYLE_BODY))

    elements.append(Paragraph("<b>Trust Services Categories in Scope</b>", STYLE_H2))
    elements.append(Paragraph(
        "This report covers the following AICPA Trust Services Categories:", STYLE_BODY))
    categories = [
        ("<b>Security (Common Criteria):</b> The system is protected against unauthorized access, "
         "both logical and physical, to meet the entity's objectives. The Security category "
         "addresses controls related to access management, system monitoring, incident response, "
         "and risk management."),
        ("<b>Availability:</b> The system is available for operation and use as committed or "
         "agreed to by the entity. The Availability category addresses controls related to "
         "system capacity, disaster recovery, business continuity, and infrastructure redundancy."),
        ("<b>Confidentiality:</b> Information designated as confidential is protected as "
         "committed or agreed to by the entity. The Confidentiality category addresses controls "
         "related to data classification, encryption, data loss prevention, and secure disposal."),
    ]
    for cat in categories:
        elements.append(Paragraph(f"&bull; {cat}", STYLE_BODY_INDENT))

    elements.append(Paragraph("<b>Assessment of Risk</b>", STYLE_H2))
    elements.append(Paragraph(
        "Our assessment of the risks of material misstatement of the Description and of the "
        "risk that controls were not suitably designed or operating effectively considered the "
        "nature of the services provided, the complexity of the system, the entity's control "
        "environment, and the results of our inquiries, observations, and inspections. Based "
        "on our risk assessment, we determined the nature, timing, and extent of our testing "
        "procedures.", STYLE_BODY))

    elements.append(PageBreak())
    return elements


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


def _controls_table(controls_config: dict, lite: bool = False) -> list:
    elements: list = []
    elements.append(Paragraph(
        "Section IV: Trust Services Criteria and Control Activities", STYLE_H1))
    elements.append(Paragraph(
        "The following tables present the Trust Services Criteria, the related control "
        "activities, tests of controls performed, and the results of those tests. Controls "
        "are organized by criteria category. For each criterion, the table presents the "
        "control activity description, the specific test procedures performed by the service "
        "auditor, the test result (Pass or Fail), and any exceptions noted.", STYLE_BODY))
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
            cdef = CRITERIA_DEFS.get(cid)
            if cdef is None:
                continue
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

    if not lite:
        elements.extend(_detailed_testing_narratives(controls_config))

    return elements


def _detailed_testing_narratives(controls_config: dict) -> list:
    """Generate 1/2 to 1 page of detailed testing narrative per criterion."""
    elements: list = []
    elements.append(Paragraph(
        "Section IV-A: Detailed Testing Results by Criterion", STYLE_H1))
    elements.append(Paragraph(
        "The following section provides detailed testing narratives for each criterion "
        "evaluated during this examination. For each criterion, we describe the specific "
        "procedures performed, the evidence obtained, the population and sample sizes, "
        "and our conclusions regarding the design and operating effectiveness of the "
        "related controls.", STYLE_BODY))
    elements.append(Spacer(1, 0.15 * inch))

    for group_label, cids in _CRITERIA_GROUPS:
        elements.append(Paragraph(f"<b>{group_label}</b>", STYLE_H2))

        for cid in cids:
            cdef = CRITERIA_DEFS.get(cid)
            if cdef is None:
                continue
            ctrl = controls_config.get(cid, {})
            passed = ctrl.get("passed", True)

            elements.append(Paragraph(f"<b>{cid}: {cdef['category']}</b>", STYLE_H3))

            elements.append(Paragraph(
                f"<b>Control Description:</b> {cdef['activity']}", STYLE_BODY))

            elements.append(Paragraph(
                f"<b>Testing Procedures:</b> {cdef['test']}", STYLE_BODY))

            # Generate detailed narrative based on the criterion
            narrative = _generate_testing_narrative(cid, cdef, ctrl)
            for para in narrative:
                elements.append(Paragraph(para, STYLE_BODY))

            result_text = (
                '<font color="#22c55e"><b>No exceptions noted.</b></font> The control was '
                'found to be suitably designed and operating effectively throughout the '
                'audit period.'
            ) if passed else (
                '<font color="#ef4444"><b>Exception identified.</b></font> See Section V '
                'for details of the exception and management\'s response.'
            )
            elements.append(Paragraph(f"<b>Conclusion:</b> {result_text}", STYLE_BODY))
            elements.append(Spacer(1, 0.15 * inch))

    elements.append(PageBreak())
    return elements


def _generate_testing_narrative(cid: str, cdef: dict, ctrl: dict) -> list[str]:
    """Generate detailed testing narrative paragraphs for a criterion."""
    category = cdef.get("category", "")

    # Common narrative elements based on category
    narratives: dict[str, list[str]] = {
        "Control Environment": [
            "<b>Population and Sample:</b> The population consisted of all employees and "
            "contractors active during the audit period. Our sample of 25 was selected using "
            "stratified random sampling across departments and hire dates to ensure "
            "representative coverage. For each sampled individual, we obtained and inspected "
            "evidence of compliance with the applicable control requirements.",
            "<b>Evidence Obtained:</b> We obtained policy documents, training completion "
            "records, acknowledgment forms, performance review documentation, and meeting "
            "minutes. All evidence was verified against source systems and cross-referenced "
            "with HR records to confirm completeness and accuracy. We noted no discrepancies "
            "between the evidence obtained and the expected control operation.",
        ],
        "Communication and Information": [
            "<b>Population and Sample:</b> We evaluated all communication channels and "
            "information systems used to support internal control during the audit period. "
            "For periodic communications, we sampled 10 instances. For system-generated "
            "reports, we tested all monthly instances (12 total). For event-driven "
            "communications, we selected 15 instances across the audit period.",
            "<b>Evidence Obtained:</b> We inspected system configurations, communication "
            "logs, policy publication records, and stakeholder notification evidence. "
            "We verified that information quality controls were operating as designed by "
            "re-performing data validation checks on a sample of security event reports. "
            "The evidence confirmed that communication and information processes support "
            "the effective functioning of internal controls.",
        ],
        "Risk Assessment": [
            "<b>Population and Sample:</b> We evaluated all risk assessment activities "
            "performed during the audit period, including the annual enterprise risk "
            "assessment, ad-hoc risk assessments for significant changes, and the ongoing "
            "risk monitoring program. We selected a sample of 10 risks from the risk "
            "register for detailed examination.",
            "<b>Evidence Obtained:</b> We obtained the risk register, risk assessment "
            "methodology documentation, risk committee meeting minutes, and individual "
            "risk treatment plans. For each sampled risk, we verified that the risk "
            "rating was supported by documented analysis, that a treatment plan was "
            "defined and assigned to a responsible owner, and that the treatment plan "
            "was being executed per the documented timeline. We also verified that the "
            "risk assessment methodology appropriately considers both inherent and "
            "residual risk levels.",
        ],
        "Monitoring Activities": [
            "<b>Population and Sample:</b> We evaluated all monitoring activities "
            "performed during the audit period, including automated continuous monitoring, "
            "management review activities, and internal audit activities. For recurring "
            "monitoring activities, we tested all instances during the period. For "
            "event-driven monitoring, we selected a sample of 15 instances.",
            "<b>Evidence Obtained:</b> We obtained monitoring dashboards, compliance "
            "scan results, management review records, and deficiency tracking logs. "
            "We verified that automated monitoring tools were configured to cover all "
            "in-scope systems and that alerts were generated and triaged per defined "
            "procedures. We confirmed that deficiencies identified through monitoring "
            "were tracked to remediation.",
        ],
        "Control Activities": [
            "<b>Population and Sample:</b> We evaluated the control activity framework "
            "including the control catalog, control design documentation, and control "
            "execution evidence. We selected a sample of 15 controls for detailed "
            "testing of both design and operating effectiveness.",
            "<b>Evidence Obtained:</b> We obtained the control catalog with risk and "
            "criteria mappings, control design documentation, control testing schedules, "
            "and evidence of control execution. We verified that each sampled control "
            "had a documented design rationale, assigned owner, and defined testing "
            "frequency. We re-performed a subset of control activities to verify "
            "operating effectiveness.",
        ],
        "Logical and Physical Access Controls": [
            "<b>Population and Sample:</b> The population consisted of all user accounts, "
            "access events, and physical access records during the audit period. We "
            "selected samples using a combination of random and risk-based sampling. "
            "For access provisioning, we sampled 25 new accounts. For access reviews, "
            "we tested all quarterly review instances. For deprovisioning, we sampled "
            "20 terminated employees. For physical access, we sampled 15 access events.",
            "<b>Evidence Obtained:</b> We obtained identity provider configurations, "
            "access control lists, role definitions, access request tickets with approval "
            "records, access review completion reports, termination processing records, "
            "physical access logs, and visitor management records. We verified "
            "configurations by direct inspection of the identity management system, "
            "cloud IAM policies, and database access controls. Network segmentation "
            "was verified through inspection of VPC configurations and firewall rules.",
        ],
        "System Operations": [
            "<b>Population and Sample:</b> We evaluated all system operations controls "
            "active during the audit period. For vulnerability management, we sampled "
            "20 vulnerabilities across all severity levels. For monitoring, we tested "
            "25 alert instances. For incident response, we reviewed all incidents "
            "reported during the period. For recovery testing, we reviewed all scheduled "
            "test executions.",
            "<b>Evidence Obtained:</b> We obtained vulnerability scan reports, patch "
            "management records, SIEM configuration documentation, alert triage records, "
            "incident tickets with response documentation, incident response plans, "
            "tabletop exercise reports, and disaster recovery test results. We verified "
            "that vulnerability remediation SLAs were met by comparing discovery dates "
            "with remediation dates for each sampled vulnerability.",
        ],
        "Change Management": [
            "<b>Population and Sample:</b> The population consisted of all changes "
            "deployed to the production environment during the audit period. We selected "
            "a stratified random sample of 25 changes including standard changes, "
            "expedited changes, and emergency changes to ensure coverage across all "
            "change types.",
            "<b>Evidence Obtained:</b> We obtained change request tickets, peer review "
            "records, approval workflows, staging environment test results, CI/CD "
            "pipeline execution logs, deployment records, and post-deployment verification "
            "evidence. For each sampled change, we verified that the documented change "
            "management process was followed including risk assessment, peer review, "
            "testing, and approval prior to production deployment. We also verified "
            "that automated security tests executed as part of the CI/CD pipeline.",
        ],
        "Risk Mitigation": [
            "<b>Population and Sample:</b> We evaluated the business continuity and "
            "disaster recovery programs, vendor risk management activities, and risk "
            "treatment implementations during the audit period. We selected a sample "
            "of 10 vendors for vendor management testing and reviewed all BC/DR "
            "test executions.",
            "<b>Evidence Obtained:</b> We obtained business continuity plans, disaster "
            "recovery plans, BC/DR test results, backup monitoring reports, backup "
            "restoration test results, vendor security assessment reports, vendor "
            "contracts with security provisions, and vendor reassessment documentation. "
            "We verified that recovery objectives were met during testing and that "
            "vendor assessments were completed per the documented schedule.",
        ],
        "Availability": [
            "<b>Population and Sample:</b> We evaluated all availability-related "
            "controls including capacity management, redundancy configurations, "
            "backup and recovery mechanisms, and recovery testing activities during "
            "the audit period.",
            "<b>Evidence Obtained:</b> We obtained capacity monitoring dashboards, "
            "auto-scaling configurations, infrastructure architecture documentation, "
            "database replication configurations, backup job monitoring reports, "
            "backup restoration test results, and disaster recovery exercise reports. "
            "We verified that production systems are deployed across multiple "
            "availability zones by inspecting cloud infrastructure configurations. "
            "We confirmed that automated failover mechanisms are in place by reviewing "
            "failover event logs during the audit period.",
        ],
        "Confidentiality": [
            "<b>Population and Sample:</b> We evaluated all confidentiality controls "
            "including data classification, encryption, data loss prevention, and "
            "data disposal mechanisms during the audit period. We selected a sample "
            "of 10 systems containing confidential data for detailed testing.",
            "<b>Evidence Obtained:</b> We obtained the data classification policy, "
            "data inventory, encryption configurations, DLP policy configurations, "
            "DLP incident logs, data retention policies, and data disposal records. "
            "We verified that encryption configurations match the requirements specified "
            "in the data classification policy by inspecting database encryption "
            "settings, storage bucket encryption configurations, and TLS configurations "
            "for all customer-facing endpoints.",
        ],
    }

    return narratives.get(category, [
        "<b>Population and Sample:</b> We evaluated all instances of the control "
        "activity during the audit period and selected samples using risk-based "
        "and random sampling methods.",
        "<b>Evidence Obtained:</b> We obtained relevant documentation, system "
        "configurations, and operational records to evaluate both the design and "
        "operating effectiveness of the control.",
    ])


def _testing_summary(controls_config: dict) -> list:
    elements: list = []
    elements.append(Paragraph("Section IV-B: Summary of Testing Results", STYLE_H1))

    total = len(CRITERIA_DEFS)
    exceptions = sum(
        1 for cid in CRITERIA_DEFS
        if not controls_config.get(cid, {}).get("passed", True)
    )
    passed = total - exceptions

    elements.append(Paragraph(
        f"The following summarizes the results of our testing of the {total} control "
        f"activities evaluated during this examination:", STYLE_BODY))
    elements.append(Spacer(1, 0.15 * inch))

    summary_data = [
        [Paragraph("<b>Metric</b>", STYLE_CELL_BOLD),
         Paragraph("<b>Result</b>", STYLE_CELL_BOLD)],
        [Paragraph("Total controls tested", STYLE_CELL),
         Paragraph(str(total), STYLE_CELL)],
        [Paragraph("Controls operating effectively (Pass)", STYLE_CELL),
         Paragraph(f'<font color="#22c55e"><b>{passed}</b></font>', STYLE_CELL)],
        [Paragraph("Controls with exceptions (Fail)", STYLE_CELL),
         Paragraph(f'<font color="#ef4444"><b>{exceptions}</b></font>'
                   if exceptions else "0", STYLE_CELL)],
        [Paragraph("Pass rate", STYLE_CELL),
         Paragraph(f"{passed / total * 100:.1f}%", STYLE_CELL)],
        [Paragraph("Trust services categories tested", STYLE_CELL),
         Paragraph("Security, Availability, Confidentiality", STYLE_CELL)],
        [Paragraph("Total test procedures performed", STYLE_CELL),
         Paragraph(str(total * 4), STYLE_CELL)],
        [Paragraph("Total samples inspected", STYLE_CELL),
         Paragraph(str(total * 12), STYLE_CELL)],
        [Paragraph("Audit period", STYLE_CELL),
         Paragraph("January 1, 2025 - December 31, 2025", STYLE_CELL)],
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
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f8f9fa")]),
    ]))
    elements.append(tbl)
    elements.append(Spacer(1, 0.2 * inch))

    if exceptions == 0:
        elements.append(Paragraph(
            "All controls tested were found to be operating effectively throughout the "
            "audit period. No exceptions or deviations were noted during our examination. "
            "The overall control environment demonstrates a strong commitment to security, "
            "availability, and confidentiality.", STYLE_BODY))
    else:
        elements.append(Paragraph(
            f"During our examination, {exceptions} of {total} controls tested were found "
            f"to have exceptions. The details of these exceptions, including management's "
            f"responses and remediation plans, are described in Section V: Findings and "
            f"Observations.", STYLE_BODY))
        elements.append(Paragraph(
            "It is important to note that the existence of exceptions does not necessarily "
            "indicate that the service organization's controls are materially ineffective. "
            "The significance of each exception should be evaluated in the context of the "
            "overall control environment, the nature and severity of the exception, and "
            "compensating controls that may be in place.", STYLE_BODY))

    # Category breakdown table
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(Paragraph("<b>Results by Category</b>", STYLE_H2))

    cat_rows = [[
        Paragraph("<b>Category</b>", STYLE_CELL_BOLD),
        Paragraph("<b>Controls Tested</b>", STYLE_CELL_BOLD),
        Paragraph("<b>Pass</b>", STYLE_CELL_BOLD),
        Paragraph("<b>Fail</b>", STYLE_CELL_BOLD),
    ]]
    for group_label, cids in _CRITERIA_GROUPS:
        cat_total = len(cids)
        cat_fail = sum(
            1 for cid in cids
            if not controls_config.get(cid, {}).get("passed", True)
        )
        cat_pass = cat_total - cat_fail
        cat_rows.append([
            Paragraph(group_label, STYLE_CELL),
            Paragraph(str(cat_total), STYLE_CELL),
            Paragraph(f'<font color="#22c55e">{cat_pass}</font>', STYLE_CELL),
            Paragraph(
                f'<font color="#ef4444">{cat_fail}</font>' if cat_fail else "0",
                STYLE_CELL,
            ),
        ])

    cat_tbl = Table(cat_rows, colWidths=[3.0 * inch, 1.2 * inch, 1.2 * inch, 1.1 * inch])
    cat_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f8f9fa")]),
    ]))
    elements.append(cat_tbl)

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
            "No exceptions were noted during our testing of the controls described in this "
            "report. All controls were operating effectively throughout the audit period. "
            "The overall control environment demonstrates a mature and well-managed security "
            "program that effectively supports the entity's service commitments and system "
            "requirements.", STYLE_BODY))
        elements.append(Paragraph(
            "While no exceptions were identified, we noted the following areas where the "
            "entity could further strengthen its control environment:", STYLE_BODY))
        elements.append(Paragraph(
            "&bull; Continue to enhance monitoring capabilities by expanding user behavior "
            "analytics coverage to all critical applications.", STYLE_BODY_INDENT))
        elements.append(Paragraph(
            "&bull; Consider implementing additional automated compliance verification "
            "mechanisms to further reduce the reliance on manual reviews.", STYLE_BODY_INDENT))
        elements.append(PageBreak())
        return elements

    elements.append(Paragraph(
        f"During our examination, we identified the following exceptions in the operation "
        f"of controls at {company}. Each finding includes a description of the condition, "
        f"the applicable criteria, the risk or effect, management's response, and any "
        f"compensating controls in place.", STYLE_BODY))
    elements.append(Spacer(1, 0.1 * inch))

    for i, (cid, cfg) in enumerate(exceptions.items(), 1):
        cdef = CRITERIA_DEFS.get(cid, {})
        elements.append(Paragraph(
            f"<b>Finding {i}: {cid} — {cdef.get('category', '')}</b>", STYLE_H2))

        elements.append(Paragraph(
            f"<b>Condition:</b> {cfg.get('exception', 'Exception noted.')}", STYLE_BODY))
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

        if cfg.get("remediation_timeline"):
            elements.append(Paragraph(
                f"<b>Remediation Timeline:</b> {cfg['remediation_timeline']}", STYLE_BODY))

        elements.append(Spacer(1, 0.15 * inch))

    elements.append(PageBreak())
    return elements


def _management_response_section(controls_config: dict, company: str) -> list:
    elements: list = []
    elements.append(Paragraph("Section VI: Management's Response to Findings", STYLE_H1))

    exceptions = {
        cid: cfg for cid, cfg in controls_config.items()
        if not cfg.get("passed", True)
    }

    if not exceptions:
        elements.append(Paragraph(
            "No findings requiring management response were identified during this examination.",
            STYLE_BODY))
        elements.append(PageBreak())
        return elements

    elements.append(Paragraph(
        f"{company} management takes the findings identified in this report seriously and "
        f"has committed to remediation of all identified exceptions. The following summarizes "
        f"management's response and remediation activities:", STYLE_BODY))

    for cid, cfg in exceptions.items():
        cdef = CRITERIA_DEFS.get(cid, {})
        elements.append(Paragraph(
            f"<b>{cid} — {cdef.get('category', '')}</b>", STYLE_H3))
        elements.append(Paragraph(
            f"<b>Status:</b> {cfg.get('remediation_status', 'Remediation in progress')}",
            STYLE_BODY))
        elements.append(Paragraph(
            f"<b>Actions Taken:</b> {cfg.get('mgmt_response', 'Management has implemented corrective actions.')}",
            STYLE_BODY))
        if cfg.get("remediation_timeline"):
            elements.append(Paragraph(
                f"<b>Expected Completion:</b> {cfg['remediation_timeline']}", STYLE_BODY))
        elements.append(Spacer(1, 0.1 * inch))

    elements.append(PageBreak())
    return elements


def _appendix_cuec(company: str) -> list:
    elements: list = []
    elements.append(Paragraph(
        "Appendix A: Complementary User Entity Controls", STYLE_H1))
    elements.append(Paragraph(
        f"{company}'s controls were designed with the assumption that certain complementary "
        f"controls would be implemented by user entities. The examination did not extend to "
        f"controls at user entities. User entities should evaluate whether the following "
        f"complementary controls are in place within their own environments:", STYLE_BODY))
    elements.append(Spacer(1, 0.1 * inch))

    cuecs = [
        ("CUEC-1: User Authentication and Access Management",
         "User entities are responsible for managing user access credentials and passwords in "
         "accordance with their own security policies, including enforcement of password complexity "
         "requirements, periodic rotation, and multi-factor authentication for privileged access. "
         "User entities should implement automated account lifecycle management to ensure timely "
         "provisioning and deprovisioning of access."),
        ("CUEC-2: Network Security",
         "User entities are responsible for ensuring that their own systems and networks connecting "
         "to the service are appropriately secured, including the use of firewalls, intrusion "
         "detection systems, and encrypted connections. User entities should implement network "
         "segmentation to isolate systems that connect to the service."),
        ("CUEC-3: Personnel Changes",
         "User entities are responsible for notifying the service organization promptly of any "
         "changes in personnel that affect user access, including terminations, role changes, and "
         "new hires requiring access. Notification should occur within 24 hours of the personnel "
         "change."),
        ("CUEC-4: Business Continuity Planning",
         "User entities are responsible for implementing their own business continuity and disaster "
         "recovery plans for business processes dependent on the service, including regular testing "
         "of recovery procedures and maintenance of up-to-date contact information for key personnel."),
        ("CUEC-5: Output Reconciliation and Validation",
         "User entities are responsible for reviewing and reconciling output reports provided by "
         "the service organization to ensure completeness and accuracy of processed data. User "
         "entities should implement automated validation checks where feasible."),
        ("CUEC-6: Regulatory Compliance",
         "User entities are responsible for ensuring compliance with applicable laws and regulations "
         "governing the use and protection of data processed by the service, including data "
         "residency requirements, industry-specific regulations, and cross-border data transfer "
         "restrictions."),
        ("CUEC-7: Endpoint Security",
         "User entities are responsible for maintaining current anti-malware and endpoint protection "
         "software on all devices used to access the service. User entities should enforce full-disk "
         "encryption on all endpoint devices and implement mobile device management (MDM) for "
         "mobile devices."),
        ("CUEC-8: Security Awareness Training",
         "User entities are responsible for ensuring that their personnel who access the service "
         "receive appropriate security awareness training relevant to the services being consumed, "
         "including phishing awareness, data handling procedures, and incident reporting."),
        ("CUEC-9: API Key and Secret Management",
         "User entities are responsible for securely managing API keys, tokens, and secrets used "
         "to authenticate with the service. Keys should be rotated periodically, stored in "
         "secure vaults, and never embedded in source code or configuration files accessible "
         "to unauthorized personnel."),
        ("CUEC-10: Monitoring and Logging",
         "User entities are responsible for monitoring and logging their interactions with the "
         "service, including API calls, authentication events, and data transfers. Logs should "
         "be retained in accordance with the user entity's retention policies and reviewed "
         "periodically for anomalous activity."),
    ]
    for title, desc in cuecs:
        elements.append(Paragraph(f"<b>{title}</b>", STYLE_H3))
        elements.append(Paragraph(desc, STYLE_BODY))

    elements.append(PageBreak())
    return elements


def _appendix_csoc(company: str, subservice_controls: list[dict] | None = None) -> list:
    elements: list = []
    elements.append(Paragraph(
        "Appendix B: Complementary Subservice Organization Controls", STYLE_H1))
    elements.append(Paragraph(
        f"The following complementary subservice organization controls (CSOCs) are expected "
        f"to be in place at the subservice organizations used by {company}. These controls "
        f"were not tested as part of this examination. User entities and {company} should "
        f"obtain SOC reports from these organizations to evaluate the design and operating "
        f"effectiveness of their controls.", STYLE_BODY))

    if subservice_controls:
        for sc in subservice_controls:
            elements.append(Paragraph(f"<b>{sc['org']}</b>", STYLE_H3))
            for ctrl in sc.get("controls", []):
                elements.append(Paragraph(f"&bull; {ctrl}", STYLE_BODY_INDENT))
    else:
        elements.append(Paragraph(
            "&bull; Cloud infrastructure provider is expected to maintain physical security "
            "controls, environmental controls, and logical access controls over the infrastructure "
            "supporting the entity's production environment.", STYLE_BODY_INDENT))
        elements.append(Paragraph(
            "&bull; Identity provider is expected to maintain controls over authentication "
            "services, MFA enforcement, and directory synchronization.", STYLE_BODY_INDENT))

    elements.append(PageBreak())
    return elements


def _appendix_glossary() -> list:
    elements: list = []
    elements.append(Paragraph("Appendix C: Glossary of Terms", STYLE_H1))
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
        ("CSOC", "Complementary Subservice Organization Control — a control expected to be "
         "implemented by a subservice organization used by the service organization."),
        ("MFA", "Multi-Factor Authentication — a security mechanism requiring two or more forms "
         "of verification before granting access."),
        ("RBAC", "Role-Based Access Control — a method of restricting access based on the roles "
         "assigned to individual users within an organization."),
        ("SIEM", "Security Information and Event Management — a system that aggregates and "
         "analyzes security log data from across the IT environment."),
        ("EDR", "Endpoint Detection and Response — a security solution that monitors endpoint "
         "devices for suspicious activity and provides automated response capabilities."),
        ("IDS/IPS", "Intrusion Detection System / Intrusion Prevention System — network security "
         "tools that monitor for and respond to malicious network activity."),
        ("WAF", "Web Application Firewall — a security control that filters and monitors HTTP "
         "traffic between a web application and the Internet."),
        ("DLP", "Data Loss Prevention — technologies and processes designed to detect and prevent "
         "unauthorized transmission of sensitive data."),
        ("PHI", "Protected Health Information — individually identifiable health information "
         "that is subject to HIPAA regulations."),
        ("PII", "Personally Identifiable Information — data that can be used to identify, "
         "contact, or locate an individual."),
        ("CVSS", "Common Vulnerability Scoring System — an open standard for assessing the "
         "severity of computer system security vulnerabilities."),
        ("RTO", "Recovery Time Objective — the targeted duration of time within which a "
         "business process must be restored after a disaster."),
        ("RPO", "Recovery Point Objective — the maximum targeted period in which data might "
         "be lost from an IT service due to a major incident."),
        ("CI/CD", "Continuous Integration / Continuous Deployment — a set of practices that "
         "enable development teams to deliver code changes more frequently and reliably."),
        ("HSM", "Hardware Security Module — a physical computing device that safeguards and "
         "manages digital keys for strong authentication."),
        ("FHIR", "Fast Healthcare Interoperability Resources — a standard for exchanging "
         "healthcare information electronically."),
        ("HIPAA", "Health Insurance Portability and Accountability Act — US legislation that "
         "provides data privacy and security provisions for safeguarding medical information."),
        ("AES-256", "Advanced Encryption Standard with 256-bit keys — a symmetric encryption "
         "algorithm widely used for protecting sensitive data."),
        ("TLS", "Transport Layer Security — a cryptographic protocol designed to provide "
         "communications security over a computer network."),
        ("SCIM", "System for Cross-domain Identity Management — an open standard for automating "
         "the exchange of user identity information."),
    ]
    for term, defn in glossary:
        elements.append(Paragraph(f"<b>{term}:</b> {defn}", STYLE_BODY))

    return elements


# ═══════════════════════════════════════════════════════════════════════
# Main generator
# ═══════════════════════════════════════════════════════════════════════

def generate_soc2_report(
    company_name: str,
    industry: str,
    audit_period: str,
    overall_opinion: str,
    controls_config: dict,
    system_description: dict,
    output_path: str,
    subservice_controls: list[dict] | None = None,
    operational_statistics: list[dict] | None = None,
    lite: bool = False,
) -> str:
    """Generate a SOC-2 Type II report PDF.

    Args:
        lite: If True, produce a compact ~15 page version (faster for
              demos when rate limits are tight). If False (default),
              produce the full ~70 page version.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    doc = _build_doc(output_path)

    # In lite mode, trim multi-paragraph system description to first
    # paragraph per section and skip heavy sections.
    if lite:
        system_description = _trim_system_description(system_description)

    story: list = []
    story.extend(_cover_page(company_name, audit_period))
    story.extend(_table_of_contents())
    story.extend(_auditor_opinion(company_name, audit_period, overall_opinion))
    story.extend(_management_assertion(company_name, audit_period))
    story.extend(_system_description(company_name, industry, system_description))
    if not lite:
        story.extend(_operational_statistics(company_name, operational_statistics))
    story.extend(_controls_methodology())
    story.extend(_controls_table(controls_config, lite=lite))
    story.extend(_testing_summary(controls_config))
    story.extend(_findings_section(controls_config, company_name))
    if not lite:
        story.extend(_management_response_section(controls_config, company_name))
    story.extend(_appendix_cuec(company_name))
    if not lite:
        story.extend(_appendix_csoc(company_name, subservice_controls))
    story.extend(_appendix_glossary())

    doc.build(story)
    return output_path


def _trim_system_description(desc: dict) -> dict:
    """Trim multi-paragraph system description fields to first paragraph only."""
    trimmed = dict(desc)
    for key in list(trimmed.keys()):
        if key.endswith("_paragraphs") and isinstance(trimmed[key], list) and len(trimmed[key]) > 1:
            trimmed[key] = trimmed[key][:1]
    if "security_policy_details" in trimmed:
        trimmed["security_policy_details"] = []
    if "infrastructure_components" in trimmed:
        trimmed["infrastructure_components"] = trimmed["infrastructure_components"][:6]
    if "key_roles" in trimmed:
        trimmed["key_roles"] = trimmed["key_roles"][:3]
    return trimmed


# ═══════════════════════════════════════════════════════════════════════
# Report definitions
# ═══════════════════════════════════════════════════════════════════════

def generate_coinbase_report(output_dir: str, lite: bool = False) -> str:
    filename = "coinbase_soc2_lite.pdf" if lite else "coinbase_soc2.pdf"
    return generate_soc2_report(
        company_name="Coinbase Global, Inc.",
        industry="Financial Technology / Cryptocurrency Exchange",
        lite=lite,
        audit_period="January 1, 2025 - December 31, 2025",
        overall_opinion="unqualified",
        controls_config={
            # All 38 criteria — mostly pass, one exception for realism
            "CC1.1": {"passed": True},
            "CC1.2": {"passed": True},
            "CC1.3": {"passed": True},
            "CC1.4": {"passed": True},
            "CC1.5": {"passed": True},
            "CC2.1": {"passed": True},
            "CC2.2": {"passed": True},
            "CC2.3": {"passed": True},
            "CC3.1": {"passed": True},
            "CC3.2": {"passed": True},
            "CC3.3": {"passed": True},
            "CC3.4": {"passed": True},
            "CC4.1": {"passed": True},
            "CC4.2": {"passed": True},
            "CC5.1": {"passed": True},
            "CC5.2": {"passed": True},
            "CC5.3": {"passed": True},
            "CC6.1": {"passed": True},
            "CC6.2": {"passed": True},
            "CC6.3": {"passed": True},
            "CC6.4": {"passed": True},
            "CC6.5": {"passed": True},
            "CC6.6": {"passed": True},
            "CC6.7": {"passed": True},
            "CC6.8": {"passed": True},
            "CC7.1": {"passed": True},
            "CC7.2": {
                "passed": False,
                "exception": (
                    "Automated alerting thresholds were not reviewed quarterly as stated in "
                    "the monitoring policy. During Q2 and Q3 of the audit period, the Security "
                    "Operations Center (SOC) team did not perform the scheduled quarterly "
                    "threshold review for SIEM alerting rules. The last documented threshold "
                    "calibration occurred in Q1, resulting in alerting rules that were potentially "
                    "stale for approximately six months. Specifically, 14 of 47 correlation rules "
                    "had not been tuned since January 2025, including rules for authentication "
                    "anomalies, privilege escalation detection, and data exfiltration indicators. "
                    "The Q4 review was completed on October 8, 2025 and all rules were updated."
                ),
                "risk_effect": (
                    "Stale alerting thresholds may result in increased false negatives, "
                    "potentially allowing anomalous activity to go undetected for extended "
                    "periods. Conversely, stale thresholds may also generate excessive false "
                    "positives, leading to alert fatigue among SOC analysts and potentially "
                    "causing legitimate threats to be overlooked. Given the volume of "
                    "cryptocurrency transactions processed by Coinbase (approximately $12 billion "
                    "monthly during the audit period), even brief gaps in detection capability "
                    "represent significant risk."
                ),
                "mgmt_response": (
                    "Management acknowledges this finding. Effective October 2025, the SOC team "
                    "has implemented monthly threshold reviews (exceeding the quarterly requirement) "
                    "with documented sign-off tracked in Jira (project: SOC-TUNE). An automated "
                    "reminder workflow has been deployed via PagerDuty to prevent recurrence. "
                    "Additionally, management has implemented automated drift detection that "
                    "compares current alerting rule configurations against the approved baseline "
                    "and flags any rules that have not been reviewed within the defined window. "
                    "The VP of Security Operations has been assigned as the control owner with "
                    "explicit accountability for quarterly reviews."
                ),
                "compensating_control": (
                    "While the threshold review was not performed in Q2 and Q3, the underlying "
                    "correlation rules remained active and continued to generate alerts based on "
                    "the Q1 thresholds. The SOC team continued to triage all generated alerts per "
                    "standard operating procedures. No security incidents were identified that "
                    "could be attributed to the stale thresholds during the gap period."
                ),
                "remediation_timeline": "Completed October 2025. Monthly reviews are now in effect.",
                "remediation_status": "Remediated",
            },
            "CC7.3": {"passed": True},
            "CC7.4": {"passed": True},
            "CC7.5": {"passed": True},
            "CC8.1": {"passed": True},
            "CC9.1": {"passed": True},
            "CC9.2": {"passed": True},
            "A1.1": {"passed": True},
            "A1.2": {"passed": True},
            "A1.3": {"passed": True},
            "C1.1": {"passed": True},
            "C1.2": {"passed": True},
        },
        system_description={
            "overview_paragraphs": [
                "Coinbase Global, Inc. (\"Coinbase\" or the \"Company\") operates one of the largest "
                "cryptocurrency exchange platforms in the United States and is a publicly traded "
                "company on the NASDAQ (ticker: COIN). Founded in 2012 and headquartered in San "
                "Francisco, California, the platform enables users to buy, sell, store, transfer, "
                "and stake digital assets including Bitcoin, Ethereum, and over 250 other "
                "cryptocurrencies and digital tokens.",

                "Coinbase serves both retail consumers and institutional clients through multiple "
                "product offerings. The Coinbase retail platform provides an accessible interface "
                "for individual investors to purchase and manage digital assets. Coinbase Advanced "
                "Trade (formerly Coinbase Pro) offers professional-grade trading tools with advanced "
                "charting, order types, and lower fees for active traders. Coinbase Prime serves "
                "institutional clients including hedge funds, family offices, and corporate "
                "treasuries with prime brokerage services, custodial solutions, and algorithmic "
                "trading capabilities. Coinbase Cloud provides blockchain infrastructure services "
                "including staking, node management, and developer APIs.",

                "As of the end of the audit period, Coinbase managed approximately $130 billion "
                "in assets on behalf of its customers and processed an average of $12 billion in "
                "cryptocurrency transactions per month. The platform serves over 110 million "
                "verified users across more than 100 countries, with approximately 8.5 million "
                "monthly transacting users.",

                "The Company is registered as a Money Services Business (MSB) with the Financial "
                "Crimes Enforcement Network (FinCEN) and holds money transmitter licenses in 48 "
                "states and territories. Coinbase is also registered with the Securities and "
                "Exchange Commission (SEC) as a broker-dealer through its subsidiary, Coinbase "
                "Capital Markets. The Company is subject to regulatory oversight from multiple "
                "federal and state agencies, including the SEC, CFTC, FinCEN, and state financial "
                "regulators.",

                "Coinbase maintains a rigorous compliance program that includes Bank Secrecy Act "
                "(BSA) and Anti-Money Laundering (AML) procedures, Know Your Customer (KYC) "
                "verification, sanctions screening (OFAC), suspicious activity reporting, and "
                "transaction monitoring. The compliance team of over 200 professionals ensures "
                "adherence to all applicable financial regulations.",
            ],
            "service_commitments": [
                "Maintain system availability of 99.95% as measured on a monthly basis for all "
                "production services, with a target of 99.99% for critical trading systems.",
                "Protect the confidentiality and integrity of customer data in accordance with "
                "contractual obligations, applicable laws, and industry standards.",
                "Process cryptocurrency and fiat currency transactions accurately, completely, "
                "and in a timely manner.",
                "Maintain custodial controls over customer cryptocurrency assets using "
                "institutional-grade custody solutions.",
                "Comply with applicable financial regulations including BSA/AML, KYC, OFAC "
                "sanctions screening, and state money transmitter requirements.",
                "Notify affected parties within 72 hours of a confirmed security incident that "
                "involves customer data or assets.",
                "Maintain SOC 2 Type II and SOC 1 Type II certifications on an annual basis.",
                "Ensure that all customer personally identifiable information (PII) is encrypted "
                "at rest and in transit using industry-standard encryption algorithms.",
            ],
            "system_requirements": [
                "The system must authenticate all users before granting access to any resources, "
                "with multi-factor authentication required for all accounts.",
                "The system must encrypt all sensitive data at rest using AES-256 and in transit "
                "using TLS 1.2 or higher.",
                "The system must maintain comprehensive audit logs of all security-relevant events "
                "with a minimum retention period of seven years.",
                "The system must provide 99.95% uptime for production services as measured monthly.",
                "The system must implement role-based access controls that enforce the principle "
                "of least privilege.",
                "The system must support automated failover for all critical services within a "
                "recovery time objective (RTO) of 15 minutes.",
                "The system must implement real-time transaction monitoring for fraud detection "
                "and AML compliance.",
            ],
            "infrastructure_paragraphs": [
                "Coinbase's production environment is hosted entirely on Amazon Web Services (AWS) "
                "across multiple regions (US-East-1, US-West-2, EU-West-1) and availability zones "
                "for geographic redundancy and disaster recovery. The infrastructure is designed "
                "for high availability, scalability, and security, with all components deployed "
                "using infrastructure-as-code practices.",

                "The compute layer utilizes Amazon Elastic Container Service (ECS) on Fargate for "
                "containerized microservices, Amazon Elastic Kubernetes Service (EKS) for "
                "Kubernetes workloads, and Amazon EC2 for specialized compute requirements "
                "including hardware-accelerated cryptographic operations. Auto-scaling groups are "
                "configured across all production services with scaling policies based on CPU "
                "utilization, memory usage, request latency, and queue depth.",

                "The data layer consists of Amazon RDS (PostgreSQL) for relational data storage "
                "with Multi-AZ deployments and read replicas, Amazon DynamoDB for high-throughput "
                "key-value operations supporting the order matching engine, Amazon ElastiCache "
                "(Redis) for session management and application caching, and Amazon Redshift for "
                "analytics and compliance reporting. All databases are encrypted at rest using "
                "AWS Key Management Service (KMS) with customer-managed keys.",

                "Object storage utilizes Amazon S3 with server-side encryption, versioning, and "
                "cross-region replication for critical data. Amazon CloudFront is used as the "
                "content delivery network (CDN) for static assets and API edge caching. Amazon "
                "SQS and Amazon SNS provide messaging and event notification services.",

                "Network architecture implements a multi-layer defense-in-depth approach. The "
                "production VPC is segmented into public, private, and restricted subnets with "
                "network access control lists (NACLs) and security groups enforcing least-privilege "
                "network access. AWS Transit Gateway connects VPCs across regions. AWS WAF "
                "protects public-facing endpoints, and AWS Shield Advanced provides DDoS "
                "protection. All inter-service communication uses mutual TLS (mTLS) authentication.",
            ],
            "infrastructure_components": [
                "Amazon ECS on Fargate — containerized microservices (order processing, user "
                "management, compliance, notifications) with auto-scaling.",
                "Amazon EKS — Kubernetes orchestration for ML workloads, data pipelines, and "
                "internal tooling.",
                "Amazon RDS (PostgreSQL) — primary relational database with Multi-AZ deployment, "
                "automated backups, and point-in-time recovery.",
                "Amazon DynamoDB — high-throughput order book and transaction ledger with global "
                "tables for multi-region support.",
                "Amazon ElastiCache (Redis) — session management, rate limiting, and application "
                "caching with cluster mode enabled.",
                "Amazon S3 — object storage for compliance documents, audit logs, and customer "
                "KYC documentation with server-side encryption.",
                "Amazon CloudFront — CDN for web application and API edge caching with custom "
                "SSL certificates.",
                "Amazon SQS/SNS — asynchronous messaging for event-driven workflows and "
                "notification delivery.",
                "AWS WAF — web application firewall with managed rule groups and custom rules "
                "for OWASP Top 10 protection.",
                "AWS Shield Advanced — managed DDoS protection with 24/7 DDoS response team.",
                "AWS KMS — customer-managed encryption keys for database and storage encryption.",
                "Amazon CloudWatch — infrastructure monitoring, log aggregation, and alerting.",
                "AWS CloudTrail — API activity logging and governance compliance.",
                "HashiCorp Vault — secrets management and dynamic credential provisioning.",
                "Terraform — infrastructure-as-code for all cloud resource provisioning.",
                "GitHub Actions — CI/CD pipeline automation with security scanning integration.",
            ],
            "data_flow_paragraphs": [
                "User data flows through the Coinbase system through multiple channels and "
                "processing stages, each with specific security controls:",

                "<b>Authentication and Session Management:</b> Users authenticate via the web "
                "or mobile application using email/password credentials combined with mandatory "
                "multi-factor authentication (MFA). MFA options include hardware security keys "
                "(FIDO2/WebAuthn), authenticator apps (TOTP), and SMS (for legacy accounts with "
                "migration in progress). Upon successful authentication, a session token is "
                "generated with a configurable expiration period. Session tokens are stored in "
                "Redis with server-side session management. All authentication events are logged "
                "to the SIEM for monitoring.",

                "<b>Transaction Processing:</b> Cryptocurrency transaction requests are submitted "
                "through the API gateway, validated against business rules and compliance checks, "
                "and routed to the order matching engine. The matching engine processes orders in "
                "real-time with sub-millisecond latency. Settlement occurs on-chain for "
                "cryptocurrency transfers, with internal ledger updates for trades between Coinbase "
                "users. Fiat currency transactions are processed through established banking "
                "partners with real-time fraud monitoring.",

                "<b>Cryptographic Key Management:</b> Customer cryptocurrency assets are secured "
                "using a multi-tier custody architecture. Hot wallets for immediate liquidity use "
                "AWS CloudHSM for key generation and signing with multi-party computation (MPC) "
                "protocols. Cold storage for the majority of assets uses air-gapped hardware "
                "security modules (HSMs) stored in geographically distributed vaults with multi-"
                "signature requirements. All key operations require multi-party authorization.",

                "<b>Customer Data Handling:</b> Personally identifiable information (PII) "
                "including government-issued identification documents, social security numbers, "
                "bank account details, and tax identification numbers is encrypted at rest using "
                "AES-256 with KMS-managed keys and in transit using TLS 1.3. Access to PII is "
                "restricted to authorized personnel through role-based access controls with "
                "just-in-time access provisioning for support operations.",

                "<b>Compliance Data Processing:</b> Transaction data is continuously monitored "
                "by automated AML/KYC systems that apply rule-based and machine learning-based "
                "detection algorithms. Suspicious Activity Reports (SARs) are generated and filed "
                "with FinCEN as required. OFAC sanctions screening is performed in real-time on "
                "all transactions. Currency Transaction Reports (CTRs) are filed for transactions "
                "exceeding $10,000.",
            ],
            "personnel_paragraphs": [
                "Coinbase employs approximately 3,500 full-time employees as of the end of the "
                "audit period. The Company operates on a remote-first model with employees "
                "distributed across the United States and select international locations.",

                "The Security organization consists of 85 dedicated security engineers and "
                "analysts organized into the following functions: Application Security (15 "
                "engineers), Infrastructure Security (12 engineers), Security Operations Center "
                "— SOC (20 analysts operating 24/7), Governance, Risk & Compliance — GRC (18 "
                "professionals), Identity and Access Management (10 engineers), and Security "
                "Architecture (10 engineers).",

                "The Chief Information Security Officer (CISO) reports directly to the Chief "
                "Executive Officer (CEO) with a dotted-line reporting relationship to the Board "
                "of Directors' Audit Committee. The CISO presents quarterly security updates to "
                "the Board and provides ad hoc briefings on significant security events. The "
                "Deputy CISO manages day-to-day security operations.",

                "All employees undergo comprehensive background checks prior to their start date, "
                "including criminal history, employment verification, education verification, and "
                "credit checks for roles with financial system access. Background checks are "
                "conducted by a third-party screening provider in compliance with applicable "
                "state and federal laws.",

                "Mandatory security awareness training is provided to all employees upon hiring "
                "and quarterly thereafter. Training topics include phishing awareness, social "
                "engineering, password security, data classification and handling, incident "
                "reporting procedures, and regulatory compliance requirements. Completion rates "
                "are tracked and reported monthly, with a target of 100% compliance within 30 "
                "days of the training deadline. Employees who do not complete training within "
                "the deadline are subject to access restrictions.",
            ],
            "key_roles": [
                "<b>Chief Information Security Officer (CISO)</b> — Responsible for the overall "
                "security strategy, risk management, and compliance. Reports to the CEO and the "
                "Board Audit Committee.",
                "<b>Deputy CISO</b> — Manages day-to-day security operations, incident response, "
                "and the Security Operations Center.",
                "<b>VP of Security Engineering</b> — Leads application security, infrastructure "
                "security, and security architecture teams.",
                "<b>VP of Governance, Risk & Compliance</b> — Manages the GRC program including "
                "SOC audits, risk assessments, and regulatory compliance.",
                "<b>Director of Security Operations</b> — Oversees the 24/7 SOC, threat "
                "intelligence, and incident response functions.",
                "<b>Director of Identity & Access Management</b> — Manages identity lifecycle, "
                "access governance, and privileged access management.",
                "<b>Chief Compliance Officer (CCO)</b> — Oversees AML/KYC, sanctions compliance, "
                "and regulatory reporting. Reports to the CEO and the Board.",
                "<b>Data Protection Officer (DPO)</b> — Manages data privacy compliance including "
                "CCPA, GDPR (for EU operations), and data subject access requests.",
            ],
            "security_practices": [
                "Multi-factor authentication (MFA) required for all employee and customer accounts, "
                "with hardware security keys (FIDO2) mandated for all employees.",
                "AES-256 encryption at rest for all sensitive data using AWS KMS with "
                "customer-managed keys; TLS 1.3 for all data in transit.",
                "Hardware security modules (HSMs) for cryptographic key management with "
                "multi-party computation (MPC) for cryptocurrency signing operations.",
                "24/7 Security Operations Center (SOC) with SIEM-based monitoring (Splunk), "
                "user behavior analytics, and automated incident response playbooks.",
                "Annual third-party penetration testing by a Big 4 audit firm, with quarterly "
                "internal red team exercises.",
                "Bug bounty program through HackerOne with over 1,200 participating researchers "
                "and payouts totaling $1.5 million during the audit period.",
                "Quarterly access reviews for all systems with automated provisioning and "
                "deprovisioning through SCIM integration.",
                "Incident response plan tested via tabletop exercises biannually, with annual "
                "full-scale simulation exercises involving executive leadership.",
                "Business continuity and disaster recovery plans tested annually with documented "
                "RTO of 15 minutes and RPO of 5 minutes for critical trading systems.",
                "SOC 2 Type II and SOC 1 Type II audits conducted annually.",
                "ISO 27001 certified with annual surveillance audits.",
                "PCI-DSS compliant for fiat currency payment processing.",
                "NIST Cybersecurity Framework aligned security program.",
                "Automated security scanning in CI/CD pipeline including SAST, DAST, SCA, "
                "and container image scanning.",
                "Zero-trust network architecture with microsegmentation and mutual TLS "
                "for all inter-service communication.",
            ],
            "security_policy_details": [
                {
                    "title": "Access Management Policy",
                    "paragraphs": [
                        "The Access Management Policy governs the lifecycle of user access "
                        "from provisioning through deprovisioning. All access requests must be "
                        "submitted through the identity management system and approved by the "
                        "employee's manager and the system owner. Access is provisioned based "
                        "on predefined role templates that implement the principle of least "
                        "privilege. Temporary elevated access is managed through just-in-time "
                        "(JIT) provisioning with automatic expiration.",
                        "Quarterly access reviews are conducted by system owners for all "
                        "production systems. Reviews include verification of user access "
                        "against role requirements, identification of excessive privileges, "
                        "and removal of access for users who no longer require it. Access "
                        "review completion is tracked in the GRC platform and reported to "
                        "the CISO.",
                    ],
                },
                {
                    "title": "Encryption and Key Management Policy",
                    "paragraphs": [
                        "All sensitive data must be encrypted at rest using AES-256 and in "
                        "transit using TLS 1.2 or higher. Encryption keys are managed through "
                        "AWS KMS with customer-managed keys. Key rotation is performed annually "
                        "for data encryption keys and quarterly for authentication credentials. "
                        "Hardware security modules (HSMs) are used for cryptographic operations "
                        "related to cryptocurrency custody.",
                        "The Cryptographic Key Management Standard defines procedures for key "
                        "generation, distribution, storage, rotation, revocation, and destruction. "
                        "All cryptographic operations are logged and auditable. Multi-party "
                        "authorization is required for operations involving customer cryptocurrency "
                        "assets.",
                    ],
                },
                {
                    "title": "Vulnerability Management Policy",
                    "paragraphs": [
                        "Vulnerability scanning is performed continuously across all production "
                        "infrastructure using automated scanning tools. Vulnerabilities are "
                        "classified based on CVSS scores with the following remediation SLAs: "
                        "Critical (CVSS 9.0+): 72 hours, High (CVSS 7.0-8.9): 14 days, Medium "
                        "(CVSS 4.0-6.9): 30 days, Low (CVSS below 4.0): 90 days.",
                        "All software dependencies are monitored for known vulnerabilities using "
                        "software composition analysis (SCA) tools integrated into the CI/CD "
                        "pipeline. Deployments with critical or high vulnerabilities in "
                        "dependencies are blocked automatically. Exception requests require "
                        "formal risk acceptance signed by the CISO.",
                        "During the audit period, the vulnerability management program identified "
                        "and tracked 1,247 vulnerabilities across production infrastructure. Of "
                        "these, 23 were classified as Critical, 156 as High, 489 as Medium, and "
                        "579 as Low. All Critical vulnerabilities were remediated within the "
                        "72-hour SLA, and 98.7% of High vulnerabilities were remediated within "
                        "14 days. Three High vulnerabilities required extended remediation due "
                        "to complex dependency chains, and these were addressed through formal "
                        "risk acceptance with compensating controls.",
                    ],
                },
                {
                    "title": "Change Management Policy",
                    "paragraphs": [
                        "All changes to the production environment must follow the documented "
                        "change management process, which requires: (1) a change request ticket "
                        "with description, risk assessment, and rollback plan; (2) peer review "
                        "by at least one engineer not involved in the change; (3) automated "
                        "testing in the CI/CD pipeline including unit tests, integration tests, "
                        "SAST, DAST, and container image scanning; (4) deployment to a staging "
                        "environment for validation; and (5) approval by a designated change "
                        "approver before production deployment.",
                        "Emergency changes are permitted under defined circumstances (active "
                        "security incident, critical production outage) with post-hoc "
                        "documentation and approval required within 24 hours. During the audit "
                        "period, 4,712 standard changes and 23 emergency changes were deployed "
                        "to production. All emergency changes received post-hoc approval within "
                        "the required window.",
                        "The CI/CD pipeline enforces mandatory security gates: static application "
                        "security testing (SAST) using Semgrep, dynamic application security "
                        "testing (DAST) using OWASP ZAP, software composition analysis (SCA) "
                        "using Snyk, container image scanning using Trivy, and infrastructure-"
                        "as-code scanning using Checkov. Any finding classified as Critical or "
                        "High blocks the deployment automatically.",
                    ],
                },
                {
                    "title": "Incident Response Policy",
                    "paragraphs": [
                        "The Incident Response Policy defines the procedures for identifying, "
                        "classifying, containing, eradicating, and recovering from security "
                        "incidents. Incidents are classified into four severity levels: S1 "
                        "(Critical) — confirmed breach of customer data or assets with "
                        "notification to executive leadership within 15 minutes; S2 (High) "
                        "— potential breach or significant service degradation with notification "
                        "within 1 hour; S3 (Medium) — security event requiring investigation "
                        "with notification within 4 hours; S4 (Low) — security event with "
                        "no customer impact logged for trend analysis.",
                        "The incident commander model is used for all S1 and S2 incidents. An "
                        "incident commander is assigned from the Security Engineering team and "
                        "is responsible for coordinating response activities, managing "
                        "communications, and ensuring post-incident review is completed. During "
                        "the audit period, 2 incidents were classified as S2 (both related to "
                        "DDoS attacks that were mitigated within 15 minutes by AWS Shield "
                        "Advanced) and 47 incidents were classified as S3 or S4. No S1 incidents "
                        "occurred during the audit period.",
                        "Post-incident reviews are conducted within 5 business days for all S1 "
                        "and S2 incidents and within 10 business days for S3 incidents. The "
                        "review process produces a timeline, root cause analysis, impact "
                        "assessment, and action items. All action items are tracked in Jira with "
                        "assigned owners and target completion dates.",
                    ],
                },
                {
                    "title": "Data Loss Prevention Policy",
                    "paragraphs": [
                        "The Data Loss Prevention (DLP) Policy governs the detection and "
                        "prevention of unauthorized data exfiltration across all channels "
                        "including email, web, cloud storage, removable media, and printing. "
                        "DLP rules are configured to detect patterns matching PII (Social "
                        "Security numbers, government IDs, financial account numbers), "
                        "cryptocurrency private keys, internal credentials, and source code.",
                        "DLP violations are automatically logged and escalated to the Security "
                        "Operations Center for investigation. During the audit period, the DLP "
                        "system detected 312 potential violations, of which 289 were confirmed "
                        "false positives after investigation, 18 were policy violations that "
                        "were remediated through user education, and 5 were blocked outbound "
                        "transmissions that required further investigation. No confirmed data "
                        "exfiltration events occurred during the audit period.",
                    ],
                },
                {
                    "title": "Business Continuity and Disaster Recovery Policy",
                    "paragraphs": [
                        "The Business Continuity Policy establishes the framework for maintaining "
                        "critical business operations during and after a disruptive event. The "
                        "policy defines recovery time objectives (RTO) and recovery point "
                        "objectives (RPO) for all critical systems: Trading platform — RTO: 15 "
                        "minutes, RPO: 5 minutes; Customer-facing APIs — RTO: 30 minutes, RPO: "
                        "15 minutes; Internal systems — RTO: 4 hours, RPO: 1 hour; Compliance "
                        "reporting — RTO: 24 hours, RPO: 4 hours.",
                        "The Disaster Recovery Plan is tested annually through a full-scale "
                        "exercise that simulates regional failure of the primary AWS region. The "
                        "most recent test was conducted in October 2025 and achieved recovery "
                        "of all critical systems within defined RTOs. The test involved failover "
                        "of 47 microservices, 12 databases, and 8 message queues to the secondary "
                        "region with automated traffic routing via Route 53 health checks.",
                        "Database backups are performed continuously using PostgreSQL point-in-time "
                        "recovery (PITR) with automated snapshots every 6 hours. DynamoDB backups "
                        "use continuous backup with point-in-time recovery. All backup data is "
                        "encrypted and stored in a separate AWS region. Backup integrity is "
                        "verified monthly through automated restoration tests that validate "
                        "data consistency and application functionality.",
                    ],
                },
            ],
            "risk_management_paragraphs": [
                "Coinbase maintains a comprehensive risk management program that encompasses the "
                "identification, assessment, treatment, and monitoring of risks across all "
                "aspects of the business. The program is aligned with the NIST Cybersecurity "
                "Framework and ISO 27005 risk management standard.",

                "The risk management program includes the following components:",
            ],
            "risk_management_items": [
                "Annual enterprise risk assessment covering strategic, operational, financial, "
                "compliance, and technology risks. The assessment is facilitated by the GRC team "
                "with input from business stakeholders, engineering leadership, and the security "
                "team.",
                "Threat modeling for all new features, services, and significant system changes "
                "prior to deployment. Threat models are reviewed by the security architecture "
                "team and tracked in the risk register.",
                "Vendor risk assessment program for all third-party service providers with access "
                "to sensitive data or critical system components. Assessments include security "
                "questionnaires, SOC report reviews, and on-site assessments for high-risk vendors.",
                "Continuous vulnerability scanning and remediation tracking with defined SLAs "
                "based on CVSS severity scores. Vulnerability metrics are reported weekly to "
                "security leadership and monthly to the CISO.",
                "Risk register maintained in the GRC platform and reviewed quarterly by the "
                "executive leadership team. Each risk has an assigned owner, risk rating "
                "(inherent and residual), treatment plan, and target resolution date.",
                "Quarterly risk committee meetings chaired by the CISO with representation from "
                "engineering, product, compliance, and finance to review the risk landscape and "
                "prioritize risk treatment activities.",
                "Annual third-party risk assessment performed by an independent security firm "
                "to validate the effectiveness of the risk management program.",
            ],
            "subservice_orgs": [
                "<b>Amazon Web Services, Inc. (AWS)</b> — Cloud infrastructure provider including "
                "compute (EC2, ECS, EKS), storage (S3, EBS), databases (RDS, DynamoDB), networking "
                "(VPC, CloudFront, Transit Gateway), security services (KMS, CloudHSM, WAF, Shield), "
                "and monitoring (CloudWatch, CloudTrail). AWS maintains SOC 2 Type II, SOC 1 Type II, "
                "ISO 27001, PCI-DSS, and FedRAMP certifications.",
                "<b>Okta, Inc.</b> — Identity and access management provider including single sign-on "
                "(SSO), multi-factor authentication (MFA), directory services, and lifecycle management "
                "(SCIM provisioning). Okta maintains SOC 2 Type II, ISO 27001, and FedRAMP certifications.",
                "<b>Stripe, Inc.</b> — Fiat currency payment processing for customer deposits and "
                "withdrawals via ACH, wire transfer, and debit card. Stripe maintains PCI-DSS Level 1, "
                "SOC 2 Type II, and ISO 27001 certifications.",
                "<b>Splunk, Inc.</b> — Security information and event management (SIEM) platform for "
                "log aggregation, correlation, alerting, and security analytics. Splunk Cloud maintains "
                "SOC 2 Type II, ISO 27001, and FedRAMP certifications.",
                "<b>Datadog, Inc.</b> — Infrastructure monitoring, application performance monitoring "
                "(APM), and log management platform. Datadog maintains SOC 2 Type II and ISO 27001 "
                "certifications.",
                "<b>Zendesk, Inc.</b> — Customer support platform for ticketing, live chat, and "
                "knowledge base management. Zendesk maintains SOC 2 Type II and ISO 27001 certifications.",
                "<b>HackerOne, Inc.</b> — Bug bounty platform facilitating coordinated vulnerability "
                "disclosure from external security researchers.",
            ],
            "vendor_management_details": [
                "Coinbase maintains a formal vendor risk management program that requires all vendors "
                "with access to customer data or critical systems to undergo security assessment before "
                "onboarding and annually thereafter. Vendor assessments include: security questionnaire "
                "completion, review of SOC 2 Type II reports (or equivalent), review of penetration "
                "testing results, and evaluation of the vendor's security program maturity.",
                "Contracts with vendors include provisions for data protection requirements, breach "
                "notification obligations (within 24 hours), the right to audit, and termination "
                "clauses for material security failures. High-risk vendors (those with direct access "
                "to production systems or customer data) are subject to enhanced due diligence "
                "including on-site security assessments.",
            ],
            "incident_management_paragraphs": [
                "Coinbase maintains a comprehensive incident management program governed by the "
                "Incident Response Policy and supported by detailed runbooks for common incident "
                "types. The program follows the NIST SP 800-61 Computer Security Incident Handling "
                "Guide framework with customizations for cryptocurrency-specific threats including "
                "private key compromise, smart contract vulnerabilities, blockchain reorganization "
                "events, and market manipulation attempts.",

                "The incident response team consists of the Security Operations Center (SOC) as "
                "first responders, supported by the Security Engineering team for technical "
                "investigation, the Legal team for regulatory notification requirements, and the "
                "Communications team for external notifications. An incident commander is assigned "
                "for all incidents classified as Severity 1 or Severity 2. The incident commander "
                "has authority to escalate to the CISO, CEO, and Board as warranted by the severity "
                "and potential impact of the incident.",

                "Incidents are classified into four severity levels: Severity 1 (Critical) — "
                "confirmed breach of customer data or cryptocurrency assets, with mandatory "
                "notification to the CISO within 15 minutes and to the CEO within 30 minutes; "
                "Severity 2 (High) — potential breach or significant service degradation affecting "
                "more than 1% of users, with notification to the CISO within 1 hour; Severity 3 "
                "(Medium) — security event requiring investigation with limited or no customer "
                "impact, with notification to the Director of Security Operations within 4 hours; "
                "and Severity 4 (Low) — security event with no direct customer impact, logged for "
                "trend analysis and reviewed weekly.",

                "During the audit period, the incident management program processed the following "
                "events: 0 Severity 1 incidents, 2 Severity 2 incidents (both DDoS attacks "
                "mitigated within 15 minutes by AWS Shield Advanced), 47 Severity 3 incidents "
                "(including 12 phishing attempts, 8 unauthorized access attempts blocked by MFA, "
                "15 vulnerability exploitation attempts blocked by WAF, 7 suspicious API usage "
                "patterns, and 5 malware detections on employee endpoints), and 234 Severity 4 "
                "events. Mean time to detection (MTTD) was 4.2 minutes for automated detections "
                "and 2.3 hours for analyst-identified events. Mean time to response (MTTR) was "
                "12 minutes for Severity 2 incidents and 3.1 hours for Severity 3 incidents.",

                "Post-incident reviews (PIRs) are conducted within 5 business days for all "
                "Severity 1 and 2 incidents and within 10 business days for Severity 3 incidents. "
                "PIRs document the complete timeline from initial detection through resolution, "
                "root cause analysis using the '5 Whys' methodology, impact assessment including "
                "affected systems and users, lessons learned, and specific remediation actions "
                "with assigned owners and target completion dates. All PIR action items are "
                "tracked in Jira and reviewed weekly by the Director of Security Operations.",

                "Tabletop exercises are conducted biannually with scenarios covering cryptocurrency "
                "private key compromise, customer data breach, ransomware deployment, DDoS attack, "
                "insider threat, and supply chain compromise. A full-scale simulation exercise "
                "involving executive leadership, legal counsel, external incident response partners "
                "(CrowdStrike), and communications advisors is conducted annually. The most recent "
                "full-scale exercise was conducted in September 2025 and simulated a coordinated "
                "attack involving simultaneous DDoS, phishing, and attempted cryptocurrency theft. "
                "The exercise identified two areas for improvement in inter-team communication "
                "during the containment phase, both of which were addressed through updated "
                "runbooks and additional training completed by October 2025.",

                "Coinbase maintains a third-party incident response retainer with CrowdStrike "
                "for forensic investigation, malware analysis, and incident response augmentation. "
                "The retainer provides guaranteed 2-hour response time for critical incidents and "
                "includes pre-positioned forensic tools in the Coinbase environment. Additionally, "
                "Coinbase maintains a cyber insurance policy with coverage for breach response "
                "costs, regulatory defense, and business interruption.",
            ],
            "bcdr_paragraphs": [
                "Coinbase maintains business continuity (BC) and disaster recovery (DR) plans "
                "designed to ensure continued operation of critical services during adverse events "
                "including natural disasters, infrastructure failures, cyberattacks, and pandemic "
                "situations. The BC/DR program is governed by the Business Continuity Policy and "
                "tested annually through full-scale exercises.",

                "The BC/DR program defines recovery objectives for all critical systems organized "
                "into four tiers based on business criticality: Tier 1 (Trading Platform, Order "
                "Matching Engine, Custody Systems) — RTO: 15 minutes, RPO: 5 minutes; Tier 2 "
                "(Customer-Facing APIs, Authentication Services, Payment Processing) — RTO: 30 "
                "minutes, RPO: 15 minutes; Tier 3 (Customer Support, Analytics, Internal Tools) "
                "— RTO: 4 hours, RPO: 1 hour; Tier 4 (Compliance Reporting, Batch Processing, "
                "Data Warehousing) — RTO: 24 hours, RPO: 4 hours.",

                "Critical systems are deployed across multiple AWS availability zones within each "
                "region and across multiple AWS regions (US-East-1 primary, US-West-2 secondary) "
                "for geographic redundancy. The architecture employs active-active configuration "
                "for stateless services and active-passive with automated failover for stateful "
                "services. Traffic routing uses Amazon Route 53 with health checks that trigger "
                "automatic failover within 60 seconds of detecting a primary region failure.",

                "Database redundancy is achieved through multiple mechanisms: Amazon RDS PostgreSQL "
                "uses Multi-AZ deployment with synchronous replication to a standby instance in a "
                "different availability zone, and asynchronous cross-region replication to the "
                "secondary region. Amazon DynamoDB uses Global Tables for multi-region active-active "
                "replication. Point-in-time recovery is enabled for all databases with a 35-day "
                "retention window.",

                "Database backups are performed continuously using PostgreSQL point-in-time "
                "recovery (PITR) with automated snapshots every 6 hours. DynamoDB uses continuous "
                "backup with on-demand backup before major changes. Backup integrity is verified "
                "monthly through automated restoration testing that validates data consistency "
                "using checksums and application-level validation queries. All backup data is "
                "encrypted at rest using AWS KMS and stored in a separate AWS region from the "
                "primary production environment.",

                "The annual DR test conducted in October 2025 included the following scenarios: "
                "simulated failure of the primary AWS region (US-East-1) requiring full failover "
                "to US-West-2, including 47 microservices, 12 databases, 8 message queues, and "
                "3 caching clusters. All Tier 1 systems were recovered within 12 minutes (under "
                "the 15-minute RTO), and all Tier 2 systems were recovered within 22 minutes "
                "(under the 30-minute RTO). Data integrity validation confirmed zero data loss "
                "across all databases. The test identified one improvement: the need for pre-warmed "
                "auto-scaling groups in the secondary region, which was implemented by November 2025.",

                "In addition to technology recovery, the BC plan covers operational continuity "
                "including alternative work arrangements (Coinbase operates as remote-first), "
                "communication procedures using out-of-band channels, vendor notification "
                "procedures, and customer communication templates. The BC plan was last invoked "
                "operationally during a brief AWS regional disruption in March 2025, where "
                "automated failover handled the traffic rerouting without manual intervention "
                "and no customer impact was reported.",
            ],
            "data_classification_paragraphs": [
                "Coinbase classifies all information into four categories based on sensitivity "
                "and regulatory requirements:",

                "<b>Restricted:</b> Information whose unauthorized disclosure would cause severe "
                "harm. This includes cryptocurrency private keys, authentication credentials, "
                "encryption keys, and internal security configurations. Restricted data is "
                "accessible only to specifically authorized individuals with a documented "
                "business need. Access requires multi-party authorization and is logged with "
                "real-time alerting.",

                "<b>Confidential:</b> Information whose unauthorized disclosure would cause "
                "significant harm. This includes customer PII (SSN, government ID, bank account "
                "numbers), transaction data, internal financial data, and intellectual property. "
                "Confidential data is encrypted at rest and in transit, with access controlled "
                "by RBAC and monitored by DLP controls.",

                "<b>Internal:</b> Information intended for internal use only that would not cause "
                "significant harm if disclosed but is not intended for public distribution. This "
                "includes internal communications, project documentation, and aggregate business "
                "metrics. Internal data is accessible to all employees with standard authentication.",

                "<b>Public:</b> Information that has been approved for public distribution. This "
                "includes marketing materials, published blog posts, and public API documentation. "
                "No access restrictions apply beyond ensuring content accuracy.",
            ],
        },
        subservice_controls=[
            {
                "org": "Amazon Web Services (AWS)",
                "controls": [
                    "Physical security controls over data center facilities including biometric "
                    "access, video surveillance, and security personnel.",
                    "Environmental controls including fire suppression, climate control, and "
                    "redundant power supply.",
                    "Logical access controls over the hypervisor layer and physical host isolation.",
                    "Network controls including DDoS mitigation and peering point security.",
                    "Compliance maintenance for SOC 2 Type II, ISO 27001, and PCI-DSS.",
                ],
            },
            {
                "org": "Okta, Inc.",
                "controls": [
                    "Authentication service availability and performance SLAs.",
                    "MFA infrastructure security and reliability.",
                    "Directory synchronization integrity and confidentiality.",
                    "Audit logging of all authentication events.",
                    "Compliance maintenance for SOC 2 Type II and ISO 27001.",
                ],
            },
            {
                "org": "Stripe, Inc.",
                "controls": [
                    "PCI-DSS Level 1 compliance for payment data handling.",
                    "Tokenization of payment credentials and bank account information.",
                    "Transaction monitoring and fraud detection.",
                    "Secure settlement and reconciliation processes.",
                ],
            },
        ],
        operational_statistics=[
            {
                "title": "Security Incident Summary",
                "description": "Summary of security incidents processed during the audit period.",
                "headers": ["Severity", "Count", "Avg. MTTD", "Avg. MTTR", "Customer Impact"],
                "rows": [
                    ["S1 — Critical", "0", "N/A", "N/A", "None"],
                    ["S2 — High", "2", "< 1 min (automated)", "12 min", "No customer impact"],
                    ["S3 — Medium", "47", "2.3 hours", "3.1 hours", "Minimal"],
                    ["S4 — Low", "234", "4.2 min (automated)", "N/A (logged)", "None"],
                    ["Total", "283", "—", "—", "—"],
                ],
                "col_widths": [1.3 * inch, 0.7 * inch, 1.4 * inch, 1.3 * inch, 1.8 * inch],
            },
            {
                "title": "Vulnerability Management Metrics",
                "description": "Vulnerability scanning and remediation statistics for the audit period.",
                "headers": ["CVSS Severity", "Discovered", "Remediated", "Open (EoP)", "SLA Compliance"],
                "rows": [
                    ["Critical (9.0+)", "23", "23", "0", "100%"],
                    ["High (7.0-8.9)", "156", "154", "2", "98.7%"],
                    ["Medium (4.0-6.9)", "489", "471", "18", "96.3%"],
                    ["Low (< 4.0)", "579", "498", "81", "85.8%"],
                    ["Total", "1,247", "1,146", "101", "—"],
                ],
                "col_widths": [1.4 * inch, 1.2 * inch, 1.2 * inch, 1.2 * inch, 1.5 * inch],
            },
            {
                "title": "Change Management Metrics",
                "description": "Production changes deployed during the audit period.",
                "headers": ["Change Type", "Count", "Rollback Rate", "Avg. Review Time"],
                "rows": [
                    ["Standard", "4,712", "1.2%", "4.3 hours"],
                    ["Expedited", "89", "2.2%", "1.1 hours"],
                    ["Emergency", "23", "8.7%", "Post-hoc (< 24h)"],
                    ["Infrastructure", "342", "0.9%", "6.2 hours"],
                    ["Total", "5,166", "1.4%", "—"],
                ],
                "col_widths": [1.6 * inch, 1.2 * inch, 1.6 * inch, 2.1 * inch],
            },
            {
                "title": "Access Management Metrics",
                "description": "User access provisioning, deprovisioning, and review statistics.",
                "headers": ["Metric", "Q1", "Q2", "Q3", "Q4", "Annual"],
                "rows": [
                    ["New accounts provisioned", "187", "203", "156", "178", "724"],
                    ["Accounts deprovisioned", "45", "52", "38", "41", "176"],
                    ["Avg. deprovisioning time", "3.2h", "2.8h", "2.1h", "1.9h", "2.5h"],
                    ["Access reviews completed", "Yes", "Yes", "Yes", "Yes", "4/4"],
                    ["Excessive privileges found", "12", "8", "5", "3", "28"],
                    ["Privileges remediated", "12", "8", "5", "3", "28"],
                    ["MFA enforcement rate", "100%", "100%", "100%", "100%", "100%"],
                ],
                "col_widths": [1.8 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch, 1.1 * inch],
            },
            {
                "title": "System Availability Metrics",
                "description": "Production system uptime and performance during the audit period.",
                "headers": ["Service", "Uptime", "Incidents", "Max Downtime", "SLA Target"],
                "rows": [
                    ["Trading Platform", "99.98%", "1", "8 min", "99.95%"],
                    ["REST API", "99.97%", "2", "12 min", "99.95%"],
                    ["WebSocket Feed", "99.96%", "3", "18 min", "99.95%"],
                    ["Authentication", "99.99%", "0", "0 min", "99.99%"],
                    ["Custody/Wallets", "100.00%", "0", "0 min", "99.99%"],
                    ["Customer Portal", "99.95%", "4", "22 min", "99.9%"],
                    ["Mobile App", "99.97%", "2", "14 min", "99.9%"],
                ],
                "col_widths": [1.5 * inch, 1.0 * inch, 1.0 * inch, 1.3 * inch, 1.7 * inch],
            },
            {
                "title": "Security Training Compliance",
                "description": "Employee security awareness training completion rates by quarter.",
                "headers": ["Training Module", "Q1", "Q2", "Q3", "Q4"],
                "rows": [
                    ["Security Awareness (mandatory)", "100%", "100%", "100%", "100%"],
                    ["Phishing Simulation", "98.2%", "97.8%", "99.1%", "98.9%"],
                    ["Data Handling & Classification", "100%", "100%", "100%", "100%"],
                    ["Incident Reporting Procedures", "100%", "99.7%", "100%", "100%"],
                    ["Secure Development (engineering)", "100%", "100%", "100%", "100%"],
                    ["Regulatory Compliance (BSA/AML)", "100%", "100%", "100%", "100%"],
                    ["Simulated phishing click rate", "3.1%", "2.8%", "2.2%", "1.9%"],
                ],
                "col_widths": [2.6 * inch, 1.0 * inch, 1.0 * inch, 1.0 * inch, 1.0 * inch],
            },
            {
                "title": "Penetration Testing Summary",
                "description": "Results of third-party and internal penetration testing activities.",
                "headers": ["Test Type", "Frequency", "Last Conducted", "Critical", "High", "Medium", "Low"],
                "rows": [
                    ["External Pentest (Big 4)", "Annual", "Sep 2025", "0", "1", "4", "8"],
                    ["Internal Red Team", "Quarterly", "Dec 2025", "0", "0", "2", "5"],
                    ["Cloud Config Review", "Semi-annual", "Nov 2025", "0", "0", "1", "3"],
                    ["Mobile App Assessment", "Annual", "Aug 2025", "0", "0", "2", "6"],
                    ["API Security Review", "Semi-annual", "Oct 2025", "0", "1", "3", "7"],
                ],
                "col_widths": [1.5 * inch, 0.9 * inch, 0.9 * inch, 0.7 * inch, 0.7 * inch, 0.7 * inch, 0.7 * inch],
            },
        ],
        output_path=os.path.join(output_dir, filename),
    )


def generate_healthpulse_report(output_dir: str, lite: bool = False) -> str:
    filename = "healthpulse_soc2_lite.pdf" if lite else "healthpulse_soc2.pdf"
    return generate_soc2_report(
        company_name="HealthPulse, Inc.",
        industry="Healthcare Technology / AI Diagnostics",
        lite=lite,
        audit_period="January 1, 2025 - December 31, 2025",
        overall_opinion="qualified",
        controls_config={
            "CC1.1": {"passed": True},
            "CC1.2": {"passed": True},
            "CC1.3": {"passed": True},
            "CC1.4": {"passed": True},
            "CC1.5": {"passed": True},
            "CC2.1": {"passed": True},
            "CC2.2": {"passed": True},
            "CC2.3": {"passed": True},
            "CC3.1": {"passed": True},
            "CC3.2": {"passed": True},
            "CC3.3": {"passed": True},
            "CC3.4": {"passed": True},
            "CC4.1": {"passed": True},
            "CC4.2": {"passed": True},
            "CC5.1": {"passed": True},
            "CC5.2": {"passed": True},
            "CC5.3": {"passed": True},
            "CC6.1": {
                "passed": False,
                "exception": (
                    "Multi-factor authentication (MFA) was not enforced for all administrative "
                    "accounts during Q1 and Q2 of the audit period. Specifically, 12 of 34 "
                    "administrative accounts (35%) were configured with password-only "
                    "authentication for the first six months of the period. These accounts "
                    "included 4 database administrators, 3 cloud infrastructure engineers, "
                    "2 application administrators, and 3 DevOps engineers. MFA was "
                    "retroactively enforced for all accounts in July 2025."
                ),
                "risk_effect": (
                    "Administrative accounts without MFA are significantly more vulnerable to "
                    "credential-based attacks including phishing, credential stuffing, and "
                    "brute force. Given that HealthPulse processes protected health information "
                    "(PHI) for approximately 2.3 million patients, unauthorized access to "
                    "administrative accounts could result in a reportable HIPAA breach with "
                    "potential fines of up to $1.5 million per violation category."
                ),
                "mgmt_response": (
                    "Management acknowledges this finding. MFA has been enforced for all "
                    "accounts since July 2025 using Okta Verify. A technical control has been "
                    "implemented in our identity provider (Okta) to prevent the creation of "
                    "any new accounts without MFA. Additionally, a weekly automated compliance "
                    "scan verifies MFA enrollment across all accounts and reports violations "
                    "to the Security team for immediate remediation."
                ),
                "remediation_timeline": "Completed July 2025.",
                "remediation_status": "Remediated",
            },
            "CC6.2": {"passed": True},
            "CC6.3": {
                "passed": False,
                "exception": (
                    "Access reviews were not performed quarterly as documented in the access "
                    "management policy. Only one access review was completed during the audit "
                    "period (in Q3). The Q1, Q2, and Q4 reviews were not performed. "
                    "Furthermore, three former employees retained active application accounts "
                    "for an average of 45 days after their termination date. One former "
                    "engineer retained access to the production database containing PHI for "
                    "67 days post-termination, though VPN access was revoked within 24 hours."
                ),
                "risk_effect": (
                    "Failure to perform timely access reviews and deprovisioning increases "
                    "the risk of unauthorized access by former employees and accumulation of "
                    "excessive privileges by current employees. The production database "
                    "contains PHI for approximately 2.3 million patients. While network-level "
                    "access was revoked, the application-level access could have been exploited "
                    "if the former employee accessed the system through an alternative network path."
                ),
                "mgmt_response": (
                    "Management has implemented automated access review workflows in our "
                    "identity management system. HR termination events now trigger immediate "
                    "account deactivation via an automated SCIM integration with Okta. "
                    "Quarterly access reviews are now tracked with mandatory completion "
                    "deadlines and automated escalation to the VP of Engineering if not "
                    "completed within 5 business days of the deadline."
                ),
                "compensating_control": (
                    "VPN access was revoked for all terminated employees within 24 hours of "
                    "termination. While application-level accounts remained active, network-level "
                    "access was restricted, requiring VPN connectivity to reach the production "
                    "database. Additionally, all database queries are logged and no anomalous "
                    "access was detected from the terminated employees' accounts during the "
                    "period they remained active."
                ),
                "remediation_timeline": "Automated deprovisioning completed September 2025. "
                    "Quarterly reviews in effect starting Q4 2025.",
                "remediation_status": "Remediated",
            },
            "CC6.4": {"passed": True},
            "CC6.5": {"passed": True},
            "CC6.6": {"passed": True},
            "CC6.7": {"passed": True},
            "CC6.8": {"passed": True},
            "CC7.1": {"passed": True},
            "CC7.2": {"passed": True},
            "CC7.3": {"passed": True},
            "CC7.4": {
                "passed": False,
                "exception": (
                    "The incident response plan was documented and approved by management; "
                    "however, no tabletop exercises or simulated incident drills were conducted "
                    "during the audit period. The policy requires annual testing of the incident "
                    "response plan, but the last documented test was in September 2023 — over "
                    "two years prior. Additionally, the incident response team roster had not "
                    "been updated since March 2024 and included three employees who had since "
                    "left the organization."
                ),
                "risk_effect": (
                    "An untested incident response plan may not function effectively during "
                    "an actual security incident, potentially increasing response time, the "
                    "scope of a breach, and regulatory non-compliance. HIPAA requires covered "
                    "entities to maintain and test contingency plans. The outdated team roster "
                    "means that notification procedures would fail during a real incident, "
                    "further delaying response."
                ),
                "mgmt_response": (
                    "Management has scheduled quarterly tabletop exercises starting January "
                    "2026. The first exercise was completed on January 15, 2026 with full "
                    "participation from the updated incident response team. A retainer "
                    "agreement with CrowdStrike has been executed to provide third-party "
                    "incident response expertise during actual incidents. The team roster "
                    "is now linked to the HR system and updated automatically upon personnel "
                    "changes."
                ),
                "remediation_timeline": "First exercise completed January 2026. Quarterly "
                    "cadence established.",
                "remediation_status": "Remediation in progress",
            },
            "CC7.5": {"passed": True},
            "CC8.1": {"passed": True},
            "CC9.1": {"passed": True},
            "CC9.2": {"passed": True},
            "A1.1": {"passed": True},
            "A1.2": {"passed": True},
            "A1.3": {"passed": True},
            "C1.1": {"passed": True},
            "C1.2": {"passed": True},
        },
        system_description={
            "overview_paragraphs": [
                "HealthPulse, Inc. (\"HealthPulse\" or the \"Company\") provides an AI-powered "
                "clinical decision support platform that assists healthcare providers with "
                "diagnostic imaging analysis. Founded in 2019 and headquartered in Boston, "
                "Massachusetts, the platform uses deep learning models trained on medical imaging "
                "datasets to identify anomalies in X-rays, CT scans, and MRI images.",

                "HealthPulse integrates with electronic health record (EHR) systems via FHIR "
                "(Fast Healthcare Interoperability Resources) APIs and serves over 450 hospitals "
                "and clinics across the United States. The platform processes approximately "
                "50,000 diagnostic images daily and provides AI-generated findings to "
                "radiologists as a second-read decision support tool.",

                "The Company's AI models have been trained on over 15 million annotated medical "
                "images and have received FDA 510(k) clearance for detecting pulmonary nodules, "
                "pneumothorax, and intracranial hemorrhage. The models operate as clinical "
                "decision support tools and do not replace physician judgment.",

                "HealthPulse is a HIPAA Business Associate and maintains Business Associate "
                "Agreements (BAAs) with all covered entity customers. The Company processes "
                "protected health information (PHI) including patient demographics, medical "
                "record numbers, diagnostic images, and clinical notes.",
            ],
            "service_commitments": [
                "Maintain platform availability of 99.9% as measured monthly.",
                "Process diagnostic images within 60 seconds of receipt.",
                "Protect the confidentiality of PHI in compliance with HIPAA.",
                "Maintain FDA 510(k) clearance for AI diagnostic algorithms.",
                "Notify covered entities within 24 hours of a confirmed security incident.",
                "Maintain SOC 2 Type II certification on an annual basis.",
            ],
            "infrastructure_paragraphs": [
                "HealthPulse's production environment is hosted on Google Cloud Platform (GCP) "
                "within a HIPAA-compliant project configuration with a signed BAA from Google. "
                "All GCP services used are covered under Google's HIPAA BAA.",

                "Key components include Google Kubernetes Engine (GKE) for container orchestration, "
                "Cloud SQL (PostgreSQL) for structured data, Cloud Healthcare API for FHIR "
                "resources, Google Cloud Storage for medical image storage, and Vertex AI for ML "
                "model serving. The application backend is built in Python using FastAPI, with "
                "TensorFlow and PyTorch for the ML inference pipeline. Infrastructure is managed "
                "via Terraform with deployments through Cloud Build.",
            ],
            "data_flow_paragraphs": [
                "Protected health information (PHI) flows through the system as follows:",
                "(1) Medical images are received from hospital PACS systems via DICOM protocol "
                "over a VPN tunnel or DICOM-web over TLS 1.2.",
                "(2) Images pass through a HIPAA-compliant de-identification engine that removes "
                "or masks all 18 HIPAA identifiers before processing by AI models.",
                "(3) AI inference results are generated by the ML pipeline and stored in the "
                "FHIR-compliant clinical data store.",
                "(4) Results are transmitted back to the ordering provider's EHR system via "
                "FHIR API with HL7 FHIR R4 compliance.",
                "(5) All PHI is encrypted at rest using Google-managed encryption keys (AES-256) "
                "and in transit using TLS 1.2+.",
                "(6) Comprehensive audit logs of all PHI access are maintained for seven years "
                "per HIPAA requirements.",
            ],
            "personnel_paragraphs": [
                "HealthPulse employs 180 full-time employees. The engineering team of 85 includes "
                "a dedicated Security & Compliance team of 6 members led by the VP of Security, "
                "who reports to the CTO.",
                "The Company employs a part-time HIPAA Privacy Officer and a part-time HIPAA "
                "Security Officer. All employees with access to PHI undergo HIPAA training upon "
                "hiring and annually thereafter. Background checks are performed for all employees.",
            ],
            "security_practices": [
                "Multi-factor authentication (MFA) enforced for all accounts (as of July 2025).",
                "AES-256 encryption at rest via Google-managed encryption; TLS 1.2+ in transit.",
                "HIPAA Business Associate Agreements (BAAs) with all subprocessors.",
                "De-identification pipeline for medical images before AI processing.",
                "SIEM monitoring via Google Chronicle with automated alerting.",
                "Annual third-party penetration testing.",
                "HIPAA-compliant audit logging with 7-year retention.",
                "Incident response plan documented (testing cadence under improvement).",
                "Business continuity plan with RTO of 4 hours and RPO of 1 hour.",
            ],
            "subservice_orgs": [
                "<b>Google Cloud Platform (GCP)</b> — Cloud infrastructure, Kubernetes, storage, "
                "and ML serving with HIPAA BAA.",
                "<b>Okta, Inc.</b> — Identity management and multi-factor authentication.",
                "<b>Snowflake, Inc.</b> — Analytics data warehouse for de-identified aggregate metrics.",
                "<b>PagerDuty, Inc.</b> — Incident alerting and on-call management.",
            ],
            "incident_management_paragraphs": [
                "HealthPulse maintains an incident response plan that follows the NIST SP 800-61 "
                "framework. The plan covers identification, containment, eradication, recovery, "
                "and lessons learned phases. The incident response team is led by the VP of "
                "Security with support from engineering, legal, and communications.",
                "Note: As identified in Finding 3 (CC7.4), the incident response plan was not "
                "tested during the audit period. Management has committed to quarterly tabletop "
                "exercises starting January 2026.",
            ],
            "bcdr_paragraphs": [
                "HealthPulse maintains business continuity and disaster recovery plans with an "
                "RTO of 4 hours and RPO of 1 hour for the diagnostic imaging platform. The plans "
                "cover GKE cluster failover, Cloud SQL high-availability configuration, and "
                "medical image storage redundancy.",
                "Annual DR testing was conducted in November 2025 with successful recovery of "
                "all critical systems within the defined objectives.",
            ],
            "data_classification_paragraphs": [
                "HealthPulse classifies data into four categories: Public, Internal, Confidential, "
                "and Restricted (PHI). PHI is subject to the strictest handling requirements "
                "including encryption at rest and in transit, access logging, minimum necessary "
                "access principle, and 7-year retention of access logs per HIPAA requirements.",
                "The de-identification pipeline ensures that AI models operate on de-identified "
                "data that does not contain any of the 18 HIPAA identifiers, reducing the risk "
                "associated with ML model processing and storage.",
            ],
        },
        operational_statistics=[
            {
                "title": "Security Incident Summary",
                "description": "Summary of security incidents processed during the audit period.",
                "headers": ["Severity", "Count", "Avg. MTTD", "Avg. MTTR", "PHI Impact"],
                "rows": [
                    ["S1 — Critical", "0", "N/A", "N/A", "None"],
                    ["S2 — High", "1", "8 min", "45 min", "No PHI exposure"],
                    ["S3 — Medium", "12", "3.4 hours", "5.2 hours", "None confirmed"],
                    ["S4 — Low", "67", "Automated", "N/A (logged)", "None"],
                    ["Total", "80", "—", "—", "—"],
                ],
                "col_widths": [1.3 * inch, 0.7 * inch, 1.4 * inch, 1.3 * inch, 1.8 * inch],
            },
            {
                "title": "Vulnerability Management Metrics",
                "description": "Vulnerability scanning and remediation statistics for the audit period.",
                "headers": ["CVSS Severity", "Discovered", "Remediated", "Open (EoP)", "SLA Compliance"],
                "rows": [
                    ["Critical (9.0+)", "4", "4", "0", "100%"],
                    ["High (7.0-8.9)", "28", "26", "2", "92.9%"],
                    ["Medium (4.0-6.9)", "89", "78", "11", "87.6%"],
                    ["Low (< 4.0)", "156", "112", "44", "71.8%"],
                    ["Total", "277", "220", "57", "—"],
                ],
                "col_widths": [1.4 * inch, 1.2 * inch, 1.2 * inch, 1.2 * inch, 1.5 * inch],
            },
            {
                "title": "Access Management Metrics",
                "description": "User access lifecycle statistics during the audit period.",
                "headers": ["Metric", "Q1", "Q2", "Q3", "Q4", "Annual"],
                "rows": [
                    ["New accounts provisioned", "22", "18", "15", "19", "74"],
                    ["Accounts deprovisioned", "5", "8", "6", "4", "23"],
                    ["Avg. deprovisioning time", "52h", "38h", "6h", "2h", "24.5h"],
                    ["Access reviews completed", "No", "No", "Yes", "No*", "1/4"],
                    ["PHI access accounts", "34", "36", "32", "35", "—"],
                    ["MFA enforcement rate", "65%", "65%", "100%", "100%", "—"],
                ],
                "col_widths": [1.8 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch, 1.1 * inch],
            },
            {
                "title": "System Availability Metrics",
                "description": "Production system uptime during the audit period.",
                "headers": ["Service", "Uptime", "Incidents", "Max Downtime", "SLA Target"],
                "rows": [
                    ["Diagnostic API", "99.92%", "3", "28 min", "99.9%"],
                    ["FHIR Interface", "99.95%", "2", "18 min", "99.9%"],
                    ["ML Inference", "99.88%", "4", "42 min", "99.9%"],
                    ["Provider Portal", "99.94%", "2", "22 min", "99.9%"],
                    ["Image Storage", "99.99%", "0", "0 min", "99.9%"],
                ],
                "col_widths": [1.5 * inch, 1.0 * inch, 1.0 * inch, 1.3 * inch, 1.7 * inch],
            },
            {
                "title": "HIPAA Compliance Metrics",
                "description": "HIPAA-specific compliance activities during the audit period.",
                "headers": ["Activity", "Requirement", "Actual", "Status"],
                "rows": [
                    ["Risk assessment", "Annual", "Completed Aug 2025", "Compliant"],
                    ["HIPAA training", "Annual", "100% completion", "Compliant"],
                    ["BAA inventory review", "Annual", "Completed Jun 2025", "Compliant"],
                    ["PHI access audit", "Quarterly", "4/4 completed", "Compliant"],
                    ["Incident response test", "Annual", "Not completed*", "Non-compliant"],
                    ["Breach notification drill", "Annual", "Not completed*", "Non-compliant"],
                    ["Policy review", "Annual", "Completed Mar 2025", "Compliant"],
                ],
                "col_widths": [1.8 * inch, 1.3 * inch, 1.7 * inch, 1.7 * inch],
            },
        ],
        output_path=os.path.join(output_dir, filename),
    )


# ── CLI entry point ────────────────────────────────────────────────────

if __name__ == "__main__":
    out_dir = str(Path(__file__).parent)

    print("Generating Coinbase SOC-2 (full)...")
    p1 = generate_coinbase_report(out_dir)
    print(f"  -> {p1}")

    print("Generating Coinbase SOC-2 (lite)...")
    p1l = generate_coinbase_report(out_dir, lite=True)
    print(f"  -> {p1l}")

    print("Generating HealthPulse SOC-2 (full)...")
    p2 = generate_healthpulse_report(out_dir)
    print(f"  -> {p2}")

    print("Generating HealthPulse SOC-2 (lite)...")
    p2l = generate_healthpulse_report(out_dir, lite=True)
    print(f"  -> {p2l}")

    print("Done.")
