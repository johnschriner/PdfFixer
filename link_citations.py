#!/usr/bin/env python3
import json
import sys
import os
import fitz  # PyMuPDF

def link_citations(pdf_path, citations_json, output_pdf):
    # Load citations and footnotes mapping
    with open(citations_json, "r", encoding="utf-8") as f:
        citations_data = json.load(f)

    # Open the PDF
    doc = fitz.open(pdf_path)

    for page_num, page_data in citations_data.items():
        page_index = int(page_num) - 1
        page = doc[page_index]
        print(f"🔗 Linking citations on page {page_num}...")

        # Embed in-text citations
        for citation in page_data.get("citations", []):
            text = citation["text"]
            bbox = fitz.Rect(*citation["bbox"])

            # Add an annotation to act as a clickable reference
            ref_annot = page.add_link({
                "kind": fitz.LINK_GOTO,        # link type
                "from": bbox,                  # clickable area
                "page": citation["footnote_page"] - 1,  # destination page (0-based)
                "zoom": 0                      # keep current zoom
            })
            print(f"✅ Linked citation {text} → footnote on page {citation['footnote_page']}")

        # Embed footnotes
        for footnote in page_data.get("footnotes", []):
            text = footnote["text"]
            bbox = fitz.Rect(*footnote["bbox"])

            # Add a note annotation on footnote for screen readers
            page.add_text_annot(bbox, f"Footnote: {text}")
            print(f"📝 Tagged footnote: {text}")

    # Save the updated PDF
    doc.save(output_pdf, deflate=True)
    print(f"🎉 Citations linked and PDF saved to {output_pdf}")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(f"Usage: python3 {sys.argv[0]} input.pdf citations.json output.pdf")
        sys.exit(1)

    input_pdf = sys.argv[1]
    citations_json = sys.argv[2]
    output_pdf = sys.argv[3]

    link_citations(input_pdf, citations_json, output_pdf)
