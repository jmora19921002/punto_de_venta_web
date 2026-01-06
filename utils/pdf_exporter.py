"""Small helper to export table-like data to PDF using fpdf2.

Usage: export_table_to_pdf(title, columns, rows, output_path)
columns: list of (header, width) where width is approximate in mm
rows: iterable of sequences matching columns length
"""
from typing import List, Iterable, Sequence

def export_table_to_pdf(title: str, columns: List[tuple], rows: Iterable[Sequence], output_path: str):
    try:
        from fpdf import FPDF
    except Exception as e:
        raise RuntimeError("fpdf no disponible: instale fpdf2 (pip install fpdf2)")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, title, ln=True, align='C')
    pdf.ln(4)

    # Header
    pdf.set_font('Arial', 'B', 10)
    for header, width in columns:
        pdf.cell(width, 8, str(header), 1, 0, 'C')
    pdf.ln()

    # Rows
    pdf.set_font('Arial', '', 9)
    for row in rows:
        for i, cell in enumerate(row):
            _, width = columns[i]
            text = str(cell) if cell is not None else ''
            # try to fit
            pdf.multi_cell(width, 6, text, 1, 'L', ln=3 if False else 0)
        pdf.ln()

    pdf.output(output_path)
