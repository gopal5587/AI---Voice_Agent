"""Generate the synthetic policy PDFs (and one deliberately corrupted PDF) in data/raw/docs."""
from pathlib import Path

from fpdf import FPDF

DOCS = Path(__file__).resolve().parents[2] / "data" / "raw" / "docs"

POLICIES = {
    "credit_policy_v1.pdf": (
        "Kosha Capital - Business Loan Credit Policy",
        "Version 1.0 | Effective from 01-01-2025 | Status: superseded",
        [
            ("Business Vintage", "The business must have been operating for a minimum of 3 years."),
            ("Credit Score", "The applicant must have a CIBIL score of 685 or above."),
            ("Turnover", "Minimum annual turnover of Rs. 10 lakh."),
        ],
    ),
    "credit_policy_v2.pdf": (
        "Kosha Capital - Business Loan Credit Policy",
        "Version 2.0 | Effective from 01-07-2026 | Status: current",
        [
            ("Business Vintage", "The business must have been operating for a minimum of 2 years."),
            ("Credit Score", "The applicant must have a CIBIL score of 700 or above."),
            ("Turnover", "Minimum annual turnover of Rs. 12 lakh."),
            ("Women Entrepreneurs", "Businesses majority-owned by women receive a 0.25% interest rate concession, subject to eligibility."),
            ("Excluded Industries", "Loans are not offered to businesses in speculative real estate, gambling, tobacco manufacturing or cryptocurrency trading."),
            ("Decision", "All approvals are subject to credit assessment. Agents and automated assistants must never guarantee approval."),
        ],
    ),
}


def build(name: str, title: str, meta: str, sections: list[tuple[str, str]]) -> None:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 15)
    pdf.multi_cell(0, 9, title, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "I", 10)
    pdf.multi_cell(0, 6, meta, new_x="LMARGIN", new_y="NEXT")
    for heading, body in sections:
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 12)
        pdf.multi_cell(0, 7, heading, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, body, new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(-20)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 6, "Kosha Capital (DEMO) - Confidential - Page 1")
    pdf.output(str(DOCS / name))


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    for name, (title, meta, sections) in POLICIES.items():
        build(name, title, meta, sections)
    (DOCS / "brochure_corrupted.pdf").write_bytes(b"%PDF-1.4\n1 0 obj << /Type /Catalog >>\n%%truncated-download")
    print(f"PDFs written to {DOCS}")


if __name__ == "__main__":
    main()
