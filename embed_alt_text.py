#!/usr/bin/env python3
import os
import json
import pikepdf
from pikepdf import Pdf, Rectangle, Name

def embed_alt_text_in_pdf(pdf_path, visuals_folder, output_path):
    with Pdf.open(pdf_path, allow_overwriting_input=True) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            # Look for alt-text JSON files matching this page
            for alt_file in sorted(os.listdir(visuals_folder)):
                if not alt_file.startswith(f"page-{page_num:03}_"):
                    continue
                alt_path = os.path.join(visuals_folder, alt_file)
                try:
                    with open(alt_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception as e:
                    print(f"❌ Failed to read {alt_file}: {e}")
                    continue

                alt_text = data.get("alt_text", "").strip()
                bbox = data.get("bbox", None)

                if not alt_text:
                    print(f"⚠️ Empty alt-text in {alt_file}, skipping...")
                    continue

                # Add AI-generated prefix if missing
                if not alt_text.lower().startswith("this description is ai-generated"):
                    alt_text = f"This description is AI-generated. {alt_text}"

                if not bbox:
                    print(f"⚠️ No bbox in {alt_file}, skipping annotation...")
                    continue

                try:
                    rect = Rectangle(bbox)
                    annot_dict = pdf.make_indirect({
                        Name.Type: Name.Annot,
                        Name.Subtype: Name('Text'),
                        Name.Contents: alt_text,
                        Name.Rect: rect,
                        Name.Name: Name('Comment'),
                        Name.F: 0,
                    })
                    page_obj = page.obj
                    annots = page_obj.get('/Annots', pdf.make_array())
                    annots.append(annot_dict)
                    page_obj['/Annots'] = annots

                    print(f"✅ Added annotation for {alt_file}: {alt_text[:50]}...")
                except Exception as e:
                    print(f"❌ Failed to embed alt-text for {alt_file}: {e}")

        pdf.save(output_path)
        print(f"\n🎉 Alt-text embedded PDF saved to: {output_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Embed AI-generated alt-text into PDF images."
    )
    parser.add_argument(
        "pdf_path",
        help="Path to input PDF file"
    )
    parser.add_argument(
        "--visuals",
        default="visuals",
        help="Folder containing JSON alt-text files"
    )
    parser.add_argument(
        "--output",
        default="results/alt_text_embedded.pdf",
        help="Output PDF path"
    )
    args = parser.parse_args()

    embed_alt_text_in_pdf(args.pdf_path, args.visuals, args.output)
