import fitz
import pikepdf
import json
import os
import sys

from ai_interface import get_structured_summary  # Uses your existing AI call

def extract_first_page_text_and_image(pdf_path):
    doc = fitz.open(pdf_path)
    first_page = doc.load_page(0)
    text = first_page.get_text()

    image_path = "results/first_page.png"
    pix = first_page.get_pixmap()
    pix.save(image_path)
    return text, image_path

def read_pdf_metadata(pdf_path):
    with pikepdf.open(pdf_path) as pdf:
        info = pdf.docinfo
        title = str(info.get("/Title", "")).strip() or None
        author = str(info.get("/Author", "")).strip() or None
    return title, author

def extract_title_author(pdf_path, output_json):
    # Step 1: Read metadata
    meta_title, meta_author = read_pdf_metadata(pdf_path)

    # Check if metadata seems invalid
    generic_titles = ["untitled", "unknown", ""]
    metadata_valid = meta_title and meta_title.lower() not in generic_titles

    if metadata_valid:
        print(f"✅ Using metadata title: {meta_title}")
        final_title, final_author = meta_title, meta_author
        ai_title, ai_author = None, None
    else:
        print(f"⚠️ Metadata missing/invalid, using AI detection...")
        text, image_path = extract_first_page_text_and_image(pdf_path)

        # AI call: returns JSON like {"article_title": "...", "author": "..."}
        ai_response = get_structured_summary(text, image_path)
        ai_title, ai_author = (
            ai_response.get("article_title"),
            ai_response.get("author")
        )
        final_title, final_author = ai_title, ai_author

    result = {
        "metadata_title": meta_title,
        "metadata_author": meta_author,
        "ai_detected_title": ai_title,
        "ai_detected_author": ai_author,
        "final_title": final_title,
        "final_author": final_author
    }

    os.makedirs(os.path.dirname(output_json), exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"🎉 Title/author info saved to: {output_json}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 extract_title_author.py input.pdf output.json")
        sys.exit(1)
    extract_title_author(sys.argv[1], sys.argv[2])
