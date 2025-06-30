import pikepdf
import sys

INPUT_PDF = sys.argv[1]
OUTPUT_PDF = sys.argv[2]

with pikepdf.open(INPUT_PDF) as pdf:
    pdf.Root[pikepdf.Name("/Lang")] = pikepdf.String("en-US")
    pdf.save(OUTPUT_PDF)

print(f"✅ Language tag set in PDF catalog. Saved to {OUTPUT_PDF}")
