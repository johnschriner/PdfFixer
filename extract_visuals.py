#!/usr/bin/env python3
import fitz
import os
import argparse
import json
from ai_interface import get_visuals_summary  # Your existing AI call that takes text+image and returns structured JSON

def extract_visual_elements(pdf_path, output_folder):
    os.makedirs(output_folder, exist_ok=True)
    doc = fitz.open(pdf_path)

    for page_num, page in enumerate(doc, start=1):
        print(f"🔎 Processing Page {page_num}...")
        images = list(page.get_images(full=True))
        page_width, page_height = page.rect.width, page.rect.height

        if images:
            print(f"✅ Found {len(images)} image(s) with PyMuPDF...")
            for i, img in enumerate(images):
                xref = img[0]
                bbox = None

                # Try to find bbox using page text blocks
                for block in page.get_text("dict")["blocks"]:
                    if block.get("type") == 1 and isinstance(block.get("image"), dict) and block["image"].get("xref") == xref:
                        bbox = fitz.Rect(block["bbox"])
                        break

                # Crop image and save
                pix = fitz.Pixmap(doc, xref)
                img_filename = os.path.join(output_folder, f"page-{page_num:03}_image-{i:02}.png")
                pix.save(img_filename)

                if bbox:
                    bbox_coords = [bbox.x0, bbox.y0, bbox.x1, bbox.y1]
                    print(f"✅ Saved {img_filename} with bbox: {bbox}")
                else:
                    bbox_coords = None
                    print(f"⚠️ Saved {img_filename} (no bbox found)")

                # Save placeholder alt-text JSON (AI will overwrite or update later)
                alt_text = "This description is AI-generated. Alt-text not yet generated."
                out_json = {
                    "bbox": bbox_coords,
                    "alt_text": alt_text
                }
                json_filename = img_filename.replace(".png", ".json")
                with open(json_filename, "w", encoding="utf-8") as f:
                    json.dump(out_json, f, indent=2)

        else:
            print(f"⚠️ No direct images found on Page {page_num}, running AI fallback...")

            # Render full page image for AI analysis
            rendered_image = f"visuals/page-{page_num:03}_rendered.png"
            page.get_pixmap().save(rendered_image)

            # Extract page text for context
            text = page.get_text("text")

            # Ask AI for visuals summary (bbox + alt-text)
            ai_response = get_visuals_summary(text, rendered_image)

            if ai_response:
                for i, visual in enumerate(ai_response):
                    bbox_norm = visual["bbox"]
                    alt_text = visual["alt_text"].strip()

                    # Convert normalized bbox → absolute coordinates
                    abs_bbox = fitz.Rect(
                        bbox_norm[0] * page_width,
                        bbox_norm[1] * page_height,
                        bbox_norm[2] * page_width,
                        bbox_norm[3] * page_height
                    )

                    # Crop and save visual image
                    pix = page.get_pixmap(clip=abs_bbox)
                    img_filename = os.path.join(output_folder, f"page-{page_num:03}_ai-{i:02}.png")
                    pix.save(img_filename)

                    # Save bbox + alt-text
                    out_json = {
                        "bbox": [abs_bbox.x0, abs_bbox.y0, abs_bbox.x1, abs_bbox.y1],
                        "alt_text": alt_text
                    }
                    json_filename = img_filename.replace(".png", ".json")
                    with open(json_filename, "w", encoding="utf-8") as f:
                        json.dump(out_json, f, indent=2)

                    print(f"✅ Saved AI-detected visual: {json_filename}")
            else:
                print(f"❌ AI fallback did not find visuals on Page {page_num}")

    print("🎉 Visual extraction complete!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract visuals and alt-text from PDF")
    parser.add_argument("pdf_path", help="Input PDF file path")
    parser.add_argument("--output", default="visuals", help="Output folder for visuals and metadata")
    args = parser.parse_args()
    extract_visual_elements(args.pdf_path, args.output)
