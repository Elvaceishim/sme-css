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
    clean_memo = memo.replace("₦", "NGN ").replace("—", "-").replace("\u2019", "'")

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
    
    pdf.multi_cell(0, 10, clean_memo)
    
    pdf.output(output_path)
    return output_path