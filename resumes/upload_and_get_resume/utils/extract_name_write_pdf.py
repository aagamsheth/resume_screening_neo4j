from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from datetime import datetime

# Write Response to PDF
def write_response_to_pdf(response_text, output_path, candidate_name="Unknown"):
    """
    Write the response text to a PDF file with proper formatting.
    
    Args:
        response_text (str): The response text from the resume analysis
        output_path (str): Path where the PDF should be saved
        candidate_name (str): Name of the candidate for the PDF title
    """
    try:
        # Create the PDF document
        doc = SimpleDocTemplate(output_path, pagesize=A4, 
                              rightMargin=72, leftMargin=72, 
                              topMargin=72, bottomMargin=18)
        
        # Get sample style sheet and create custom styles
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            textColor=HexColor('#2c3e50'),
            alignment=1,  # Center alignment
            fontName='Helvetica-Bold'
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            spaceBefore=16,
            textColor=HexColor('#34495e'),
            fontName='Helvetica-Bold'
        )
        
        subheading_style = ParagraphStyle(
            'CustomSubHeading',
            parent=styles['Heading3'],
            fontSize=12,
            spaceAfter=8,
            spaceBefore=12,
            textColor=HexColor('#7f8c8d'),
            fontName='Helvetica-Bold'
        )
        
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=6,
            spaceBefore=3,
            leftIndent=12,
            fontName='Helvetica'
        )
        
        # Story array to hold the content
        story = []
        
        # Add title
        title = f"Resume Analysis Report - {candidate_name}"
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 12))
        
        # Add generation timestamp
        timestamp = f"Generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}"
        story.append(Paragraph(timestamp, styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Process the response text
        lines = response_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                story.append(Spacer(1, 6))
                continue
            
            # Detect headings based on markdown-style formatting
            if line.startswith('**') and line.endswith('**'):
                # Main heading
                heading_text = line.replace('**', '').strip()
                story.append(Paragraph(heading_text, heading_style))
            elif line.startswith('*') and line.endswith('*') and not line.startswith('**'):
                # Sub-heading
                subheading_text = line.replace('*', '').strip()
                story.append(Paragraph(subheading_text, subheading_style))
            elif line.startswith('#'):
                # Handle markdown headers
                level = len(line) - len(line.lstrip('#'))
                header_text = line.lstrip('#').strip()
                if level <= 2:
                    story.append(Paragraph(header_text, heading_style))
                else:
                    story.append(Paragraph(header_text, subheading_style))
            elif line.startswith('-') or line.startswith('•'):
                # Bullet points
                bullet_text = line.lstrip('-•').strip()
                story.append(Paragraph(f"• {bullet_text}", body_style))
            elif ':' in line and len(line.split(':')[0]) < 50:
                # Key-value pairs (like "Experience: 5 years")
                parts = line.split(':', 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    formatted_line = f"<b>{key}:</b> {value}"
                    story.append(Paragraph(formatted_line, body_style))
                else:
                    story.append(Paragraph(line, body_style))
            else:
                # Regular paragraph
                # Clean up the text and handle basic formatting
                clean_line = line.replace('**', '<b>').replace('**', '</b>')
                clean_line = clean_line.replace('*', '<i>').replace('*', '</i>')
                story.append(Paragraph(clean_line, body_style))
        
        # Build the PDF
        doc.build(story)
        print(f"\n[SUCCESS] PDF report generated: {output_path}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to generate PDF: {str(e)}")
        return False

# Extract Candidate Name
def extract_candidate_name(details_text):
    """
    Extract candidate name from resume details text.
    
    Args:
        details_text (str): The extracted resume text
        
    Returns:
        str: Candidate name or "Unknown Candidate"
    """
    try:
        # Common patterns to find names in resume text
        lines = details_text.split('\n')[:10]  # Check first 10 lines
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Skip common headers/labels
            skip_words = ['resume', 'cv', 'curriculum', 'vitae', 'profile', 'contact', 'email', 'phone', 'address']
            if any(word in line.lower() for word in skip_words):
                continue
            
            # Look for name patterns (2-4 words, each starting with capital)
            words = line.split()
            if 2 <= len(words) <= 4:
                if all(word[0].isupper() and word.isalpha() for word in words):
                    return ' '.join(words)
        
        return "Unknown Candidate"
        
    except Exception as e:
        print(f"[WARNING] Could not extract candidate name: {str(e)}")
        return "Unknown Candidate"