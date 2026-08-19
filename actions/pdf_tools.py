"""
JARVIS PDF Tools
Handles PDF creation, manipulation, and extraction
"""

from typing import Optional, List
from pathlib import Path


def create_pdf_from_text(
    text: str,
    title: str,
    output_path: Optional[str] = None
) -> str:
    """Create a PDF from text content."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.enums import TA_CENTER
        
        if not output_path:
            output_path = f"{title.replace(' ', '_')}.pdf"
        
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Add title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor='#000080',
            spaceAfter=30,
            alignment=TA_CENTER,
        )
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 0.3 * inch))
        
        # Add content
        for line in text.split('\n'):
            if line.strip():
                story.append(Paragraph(line, styles['Normal']))
        
        doc.build(story)
        return f"PDF created: {output_path}"
    except ImportError:
        return "Error: reportlab not installed. Run: pip install reportlab"
    except Exception as e:
        return f"Error creating PDF: {e}"


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from a PDF file."""
    try:
        import PyPDF2
        
        text = []
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text.append(page.extract_text())
        
        return '\n'.join(text)
    except ImportError:
        return "Error: PyPDF2 not installed. Run: pip install PyPDF2"
    except Exception as e:
        return f"Error extracting text: {e}"


def merge_pdfs(
    pdf_paths: List[str],
    output_path: str
) -> str:
    """Merge multiple PDF files into one."""
    try:
        import PyPDF2
        
        merger = PyPDF2.PdfMerger()
        
        for pdf_path in pdf_paths:
            merger.append(pdf_path)
        
        merger.write(output_path)
        merger.close()
        
        return f"PDFs merged: {output_path}"
    except ImportError:
        return "Error: PyPDF2 not installed"
    except Exception as e:
        return f"Error merging PDFs: {e}"


def split_pdf(
    pdf_path: str,
    output_dir: str,
    start_page: int = 0,
    end_page: Optional[int] = None
) -> str:
    """Split a PDF into separate files."""
    try:
        import PyPDF2
        
        Path(output_dir).mkdir(exist_ok=True)
        
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            total_pages = len(reader.pages)
            
            if end_page is None:
                end_page = total_pages
            
            for page_num in range(start_page, min(end_page, total_pages)):
                writer = PyPDF2.PdfWriter()
                writer.add_page(reader.pages[page_num])
                
                output_file = Path(output_dir) / f"page_{page_num + 1}.pdf"
                with open(output_file, 'wb') as out:
                    writer.write(out)
        
        return f"PDF split into pages at {output_dir}"
    except ImportError:
        return "Error: PyPDF2 not installed"
    except Exception as e:
        return f"Error splitting PDF: {e}"


def add_watermark(
    pdf_path: str,
    watermark_text: str,
    output_path: str
) -> str:
    """Add a watermark to a PDF."""
    try:
        from PyPDF2 import PdfWriter
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        from io import BytesIO
        
        # Create watermark
        watermark_buffer = BytesIO()
        c = canvas.Canvas(watermark_buffer, pagesize=letter)
        c.setFont("Helvetica", 60)
        c.setFillAlpha(0.3)
        c.rotate(45)
        c.drawString(200, 100, watermark_text)
        c.save()
        watermark_buffer.seek(0)
        
        # Apply to PDF
        from PyPDF2 import PdfReader
        with open(pdf_path, 'rb') as f:
            reader = PdfReader(f)
            writer = PdfWriter()
            
            watermark_reader = PdfReader(watermark_buffer)
            watermark_page = watermark_reader.pages[0]
            
            for page in reader.pages:
                page.merge_page(watermark_page)
                writer.add_page(page)
            
            with open(output_path, 'wb') as out:
                writer.write(out)
        
        return f"Watermark added: {output_path}"
    except ImportError:
        return "Error: Required packages not installed"
    except Exception as e:
        return f"Error adding watermark: {e}"
