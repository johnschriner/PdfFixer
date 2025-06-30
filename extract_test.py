import os
import sys
import fitz  # PyMuPDF
from ai_interface import get_structured_summary
import json
import time

if len(sys.argv) < 2:
    print("Usage: python extract_structured_data.py <path_to_pdf>")
    sys.exit(1)

input_pdf_path = sys.argv[1]

if not os.path.exists(input_pdf_path):
    raise FileNotFoundError(f"File not found: {input_pdf_path}")

doc = fitz.open(input_pdf_path)
output_folder = "structured_output"
os.makedirs(output_folder, exist_ok=True)

for page_number in range(len(doc)):
    page = doc.load_page(page_number)
    text = page.get_text()
    image_path = f"rendered_pages/page_{page_number+1:03}.png"
    page.get_pixmap(dpi=150).save(image_path)

    print(f"\n🧾 Processing Page {page_number+1}/{len(doc)}")
    start_time = time.time()
    try:
        print(f"📄 Text length: {len(text)} characters")
        print(f"🖼️ Image size: {os.path.getsize(image_path)/1024:.1f} KB")
        structured_data = get_structured_summary(text, image_path)
        output_path = os.path.join(output_folder, f"page_{page_number+1:03}.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(structured_data, f, indent=2, ensure_ascii=False)
        print(f"💾 Saved structured output to: {output_path}")
    except Exception as e:
        print(f"❌ Error processing page {page_number+1}: {e}")
    finally:
        duration = time.time() - start_time
        print(f"⏱️ Page {page_number+1} took {duration:.2f} seconds.")
