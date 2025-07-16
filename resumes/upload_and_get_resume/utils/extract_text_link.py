import os
import fitz  
import json
from docx import Document

# Extract from PDF
def extract_from_pdf(file_path):
    """
    Extracts Text and links from the resume provided if in PDF format
    """
    doc = fitz.open(file_path)
    full_text = []
    links = []

    for page in doc:
        text = page.get_text()
        full_text.append(text)

        link_info = page.get_links()
        words = page.get_text("words")
        for link in link_info:
            if "uri" in link:
                rect = link["from"]
                linked_words = [
                    word[4] for word in words if fitz.Rect(word[:4]).intersects(rect)
                ]
                link_text = " ".join(linked_words).strip()
                if link_text:
                    links.append((link_text, link["uri"]))

    return {"text": "\n".join(full_text), "hyperlinks": links}

# Extract from Docx
def extract_from_docx(file_path):
    """
    Extracts Text and links from the resume provided if in docx format
    """
    doc = Document(file_path)
    text_parts = []
    links = []

    for para in doc.paragraphs:
        text_parts.append(para.text)

    rels = doc.part.rels
    for rel in rels:
        if (
            rels[rel].reltype
            == "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
        ):
            link_url = rels[rel].target_ref

            links.append(("Linked text (not reliably extracted)", link_url))

    return {"text": "\n".join(text_parts), "hyperlinks": links}

# Extract Text and links
def extract_text_and_links(file_path):
    """
    Extract Text and Links from the resume provided 
    """
    if not os.path.exists(file_path):
        return {"error": "File does not exist."}

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        result =  extract_from_pdf(file_path)
    elif ext == ".docx":
        result = extract_from_docx(file_path)
    else:
        return {"error": f"Unsupported file type: {ext}"}
    resume_text = result.get("text", "No text found")
    links = []

    for text, url in result.get("hyperlinks", []):
        links.append({
            "text": text,
            "url": url
        })
    links_json = json.dumps(links, indent=4)
    return resume_text,links_json




