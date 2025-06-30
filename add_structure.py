import sys
import json
import os
from difflib import SequenceMatcher
from pikepdf import Pdf, Name, Dictionary, Array
import fitz  # PyMuPDF

def similar(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def extract_pdf_metadata(filepath):
    doc = fitz.open(filepath)
    metadata = doc.metadata
    doc.close()
    return metadata.get("title", ""), metadata.get("author", "")

def should_update_metadata(old, new, threshold=0.9):
    if not old:
        return True
    return similar(old, new) < threshold

if len(sys.argv) != 3:
    print("Usage: python add_structure.py input.pdf output.pdf")
    sys.exit(1)

input_pdf = sys.argv[1]
output_pdf = sys.argv[2]

# Set structured elements folder
structured_dir = "structured_output"
if not os.path.exists(structured_dir):
    print(f"❌ Structured output folder not found: {structured_dir}")
    sys.exit(1)

# Load and sort page-wise JSONs
json_files = sorted(
    [f for f in os.listdir(structured_dir) if f.endswith(".json")],
    key=lambda x: int(x.split("_")[1].split(".")[0])
)

kids = []

for f in json_files:
    page_path = os.path.join(structured_dir, f)
    try:
        with open(page_path, "r", encoding="utf-8") as jf:
            data = json.load(jf)
            print(f"🔹 Processing {f}...")

            # Process text blocks like H1, H2, P, Reference
            for block in data.get("content", []):
                tag = block.get("tag")
                mcid = block.get("mcid")
                if mcid is not None and tag in ["H1", "H2", "P", "Reference"]:
                    kids.append(Dictionary({
                        "/Type": Name("/StructElem"),
                        "/S": Name(f"/{tag}"),
                        "/K": mcid
                    }))
                    print(f"  ➤ Added {tag} with MCID {mcid}")

            # Process figure blocks with alt-text
            for fig in data.get("figures", []):
                mcid = fig.get("mcid")
                alt_text = fig.get("alt_text", "This description is AI-generated alt-text.")
                if mcid is not None:
                    # Ensure the alt text starts with required prefix
                    if not alt_text.startswith("This description is AI-generated"):
                        alt_text = "This description is AI-generated. " + alt_text
                    kids.append(Dictionary({
                        "/Type": Name("/StructElem"),
                        "/S": Name("/Figure"),
                        "/Alt": alt_text,
                        "/K": mcid
                    }))
                    print(f"  ➤ Added Figure with MCID {mcid} and alt-text.")

    except Exception as e:
        print(f"⚠️ Skipped {f} due to error: {e}")

# Build RoleMap dictionary (string keys only)
rolemap = Dictionary({
    "/H1": Name("/H"),
    "/H2": Name("/H"),
    "/P": Name("/P"),
    "/Reference": Name("/Reference"),
    "/Figure": Name("/Figure")
})

# Open the PDF and add the structure tree
with Pdf.open(input_pdf) as pdf:
    root = pdf.Root

    # Extract and update metadata
    original_title, original_author = extract_pdf_metadata(input_pdf)
    try:
        with open(os.path.join(structured_dir, "page_001.json"), "r", encoding="utf-8") as f:
            page1_data = json.load(f)
        ai_title = page1_data.get("article_title", "").strip()
        ai_author = page1_data.get("author", "").strip()
    except Exception as e:
        print("⚠️ Could not read AI-derived metadata:", e)
        ai_title, ai_author = "", ""

    final_title = ai_title if should_update_metadata(original_title, ai_title) else original_title
    final_author = ai_author if should_update_metadata(original_author, ai_author) else original_author

    print(f"📄 Metadata Decision:")
    print(f"  Original Title:  {original_title}")
    print(f"  AI Title:        {ai_title}")
    print(f"  ➤ Using Title:   {final_title}")
    print(f"  Original Author: {original_author}")
    print(f"  AI Author:       {ai_author}")
    print(f"  ➤ Using Author:  {final_author}")

    pdf.docinfo["/Title"] = final_title
    pdf.docinfo["/Author"] = final_author

    # Set structural tags and rolemap
    root["/MarkInfo"] = Dictionary({"/Marked": True})
    root["/StructTreeRoot"] = Dictionary({
        "/Type": Name("/StructTreeRoot"),
        "/K": Array(kids),
        "/RoleMap": rolemap,
        "/ParentTreeNextKey": 1
    })

    pdf.save(output_pdf)

print(f"✅ PDF structure and metadata added successfully: {output_pdf}")
