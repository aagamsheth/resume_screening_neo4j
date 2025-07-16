import os
import fitz  
import json
from docx import Document
import io
import requests
from urllib.parse import urlparse

# Download dropBox File
def download_dropbox_file(url):
    """
    Convert a Dropbox shared link to a direct download link and return content
    """
    if not url.startswith("https://www.dropbox.com"):
        raise ValueError("Only Dropbox shared links are supported.")

    dl_url = url.replace("?dl=0", "?dl=1").replace("?rlkey=", "?raw=1&rlkey=")
    response = requests.get(dl_url)
    if response.status_code != 200:
        raise Exception(f"Failed to download file from Dropbox: {response.status_code}")
    return response.content

# Extract from PDF Bytes
def extract_from_pdf_bytes(file_bytes):
    """
    Extrats all the texts and links from Provided Resume present in the dropbox.
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
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

# Extract from DOCX Bytes
def extract_from_docx_bytes(file_bytes):
    """
    Extracts all the texts and links provided in the doc file present in the dropbox
    """
    doc = Document(io.BytesIO(file_bytes))
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
def extract_text_and_links(url):
    """
    Exttracts all the texts and Links present in the resume present in the dropbox.
    """
    try:

        file_bytes = download_dropbox_file(url)
        clean_path = urlparse(url).path  # removes query string
        ext = os.path.splitext(clean_path)[1].lower()

        if ext == ".pdf":
            result = extract_from_pdf_bytes(file_bytes)
        elif ext == ".docx":
            result = extract_from_docx_bytes(file_bytes)
        else:
            return {"error": f"Unsupported file type: {ext}"}

        resume_text = result.get("text", "No text found")
        links = [
            {"text": text, "url": url}
            for text, url in result.get("hyperlinks", [])
        ]
        links_json = json.dumps(links, indent=4)
        return resume_text, links_json

    except Exception as e:
        return {"error": str(e)}


