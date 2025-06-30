import fitz  # PyMuPDF

doc = fitz.open("results/sample_structured_lang.pdf")
page = doc[0]

print("🔍 Text spans on page 1:")
for block in page.get_text("dict")["blocks"]:
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            print(f"- Text: {span['text']!r}")
            print(f"  Font: {span['font']}, Size: {span['size']}")
            print(f"  BBox: {span['bbox']}")
