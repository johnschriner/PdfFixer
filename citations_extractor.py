#!/usr/bin/env python3

import os
import json
import fitz  # PyMuPDF
import glob

INPUT_PDF = "input/samplepdfwithimageandchartlist.pdf"
STRUCTURED_JSON_DIR = "structured_output"
OUTPUT_JSON = "results/citations_and_footnotes.json"

def extract_bboxes(pdf, page_num, items, field_name):
    page = pdf.load_page(page_num)
    enriched_items = []
    for item in items:
        text = item.get("marker") or item.get("text")
        if not text:
            continue
        # Search the page for this marker or text
        bbox = None
        rects = page.search_for(text)
        if rects:
            bbox = [rects[0].x0, rects[0].y0, rects[0].x1, rects[0].y1]
        enriched_items.append({
            **item,
            "bbox": bbox
        })
    return enriched_items

def main():
    # Open PDF once
    pdf = fitz.open(INPUT_PDF)

    all_citations = []
    all_footnotes = []

    json_files = sorted(glob.glob(os.path.join(STRUCTURED_JSON_DIR, "*.json")))
    if not json_files:
        print(f"No structured JSONs found in {STRUCTURED_JSON_DIR}")
        return

    for json_file in json_files:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        page_num = int(os.path.basename(json_file).split("_")[1].split(".")[0]) - 1
        citations = data.get("citations", [])
        footnotes = data.get("footnotes", [])

        enriched_citations = extract_bboxes(pdf, page_num, citations, "citations")
        enriched_footnotes = extract_bboxes(pdf, page_num, footnotes, "footnotes")

        all_citations.extend(enriched_citations)
        all_footnotes.extend(enriched_footnotes)

    output_data = {
        "citations": all_citations,
        "footnotes": all_footnotes
    }

    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)
    print(f"✅ Extracted and enriched citations & footnotes saved to {OUTPUT_JSON}")

if __name__ == "__main__":
    main()
