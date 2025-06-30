#!/usr/bin/env python3
import os
import argparse
import fitz
import json
import base64
from PIL import Image
import io
from ai_interface import get_structured_summary  # uses your local Ollama AI

def extract_structured_data(pdf_path, output_folder):
    os.makedirs(output_folder, exist_ok=True)
    doc = fitz.open(pdf_path)

    print(f"📄 Extracting structured data from {pdf_path} ({len(doc)} pages)")

    for page_num, page in enumerate(doc, start=1):
        print(f"📝 Processing Page {page_num}/{len(doc)}")

        # Render image of the page
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        image_b64 = base64.b64encode(img_bytes).decode("utf-8")

        # Extract OCR text from the page (basic text as fallback)
        text = page.get_text("text")

        try:
            structured_data = get_structured_summary(text, image_b64)
            if not structured_data:
                print(f"⚠️ Empty response for page {page_num}, skipping...")
                continue

            output_file = os.path.join(output_folder, f"page_{page_num:03}.json")
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(structured_data, f, indent=2, ensure_ascii=False)
            print(f"✅ Saved structured data to {output_file}")

        except Exception as e:
            print(f"❌ Failed to process page {page_num}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract structured metadata from PDF using AI.")
    parser.add_argument("pdf_path", help="Input PDF file path")
    parser.add_argument("--output", default="structured_output", help="Output folder for JSON files")
    args = parser.parse_args()

    extract_structured_data(args.pdf_path, args.output)
