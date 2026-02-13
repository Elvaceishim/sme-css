from fpdf import FPDF

class SMEReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'SME AI Credit Analysis Report', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def generate_pdf_report(score, memo, output_path="SME_Report.pdf"):
    # Clean up the markdown text for the PDF
    # Convert asterisks to nothing, handle headers, etc.
    final_memo = clean_markdown(memo)
    
    # Ensure standard ascii characters where possible to prevent encoding errors
    final_memo = final_memo.encode('latin-1', 'replace').decode('latin-1')

    pdf = SMEReport()
    pdf.add_page()
    
    # 1. Summary Section
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Executive Summary', 0, 1)
    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 10, f'Calculated Credit Score: {score}/100', 0, 1)
    
    pdf.line(10, 45, 200, 45)
    pdf.ln(10)
    
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Underwriter Analysis', 0, 1)
    pdf.set_font('Arial', '', 11)
    
    # Use multi_cell for the body
    pdf.multi_cell(0, 6, final_memo)
    
    pdf.output(output_path)
    return output_path


def clean_markdown(text):
    """
    Strip markdown formatting for clean plain-text PDF output.
    """
    import re
    
    # Remove bold/italic (**text** -> text)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    
    # Handle Headers (### Header -> HEADER)
    def upper_header(match):
        return "\n" + match.group(2).upper() + "\n"
    text = re.sub(r'^(#+)\s+(.*)$', upper_header, text, flags=re.MULTILINE)
    
    # Handle Lists
    # Replace "* " or "- " at start of line with bullet character
    text = re.sub(r'^[\*\-]\s+', '• ', text, flags=re.MULTILINE)
    
    # Clean up specialized chars
    text = text.replace("₦", "NGN ")
    text = text.replace("—", "-")
    text = text.replace("\u2019", "'")
    
    # Remove multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()