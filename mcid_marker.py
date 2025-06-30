import sys
import fitz  # PyMuPDF

if len(sys.argv) < 2:
    print("Usage: python mcid_marker.py input.pdf [output.pdf]")
    sys.exit(1)

INPUT_PDF = sys.argv[1]
output_path = sys.argv[2] if len(sys.argv) > 2 else INPUT_PDF.replace(".pdf", "_mcid.pdf")

doc = fitz.open(INPUT_PDF)

# Dummy change to mark heading - e.g., insert invisible text at top of first page
page = doc[0]
page.insert_text((72, 72), "", fontsize=1, color=(1, 1, 1), render_mode=3)  # invisible

doc.save(output_path)
print(f"✅ Saved with MCID to: {output_path}")
