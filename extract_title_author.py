import os
import fitz  # PyMuPDF
from pathlib import Path
from ai_interface import get_title_author

VISUALS_DIR = Path("./visuals") # A default path if not running in a session

def get_ai_suggestions(pdf_path, session_visuals_dir=VISUALS_DIR):
    """
    Analyzes a PDF's first page and returns AI-generated suggestions for title and author.
    
    Args:
        pdf_path (str or Path): The path to the input PDF.
        session_visuals_dir (Path): The directory to save the first page image.

    Returns:
        dict: A dictionary like {"article_title": "AI Title", "author": "AI Author"}
    """
    doc = None
    try:
        session_visuals_dir.mkdir(exist_ok=True)
        doc = fitz.open(pdf_path)
        first_page = doc.load_page(0)

        # Extract image bytes for the vision model
        pix = first_page.get_pixmap(dpi=150)
        image_bytes = pix.tobytes("png")

        # Extract text
        text = first_page.get_text()

        if not text.strip() and not image_bytes:
            print(f"❌ No text or image content found for AI analysis in {Path(pdf_path).name}.")
            return {"article_title": "Untitled", "author": "Unknown"}

        # Call the AI interface
        ai_response = get_title_author(text=text, image_bytes=image_bytes)
        return ai_response

    except Exception as e:
        print(f"❌ Error during AI suggestion extraction for {Path(pdf_path).name}: {e}")
        return {"article_title": "Untitled", "author": "Unknown"}
    finally:
        if doc:
            doc.close()
