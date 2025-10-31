import os
import json
import fitz  # Using PyMuPDF instead of PyPDF2
from pathlib import Path
from extract_title_author import get_ai_suggestions as extract_title_author # Renamed for clarity
from embed_metadata import embed_metadata

INPUT_DIR = "./input"
OUTPUT_DIR = "./output"
STRUCTURED_OUTPUT_DIR = "./structured_output"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(STRUCTURED_OUTPUT_DIR, exist_ok=True)

# --- ENHANCEMENT: A more robust list of placeholder titles to ignore ---
GENERIC_TITLES = {
    "unknown",
    "untitled",
    "microsoft word document",
    "",
}

def process_title_author():
    pdf_files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(".pdf")]
    print(f"📄 Found {len(pdf_files)} PDF(s) to process for title and author.\n")

    for filename in pdf_files:
        input_pdf_path = os.path.join(INPUT_DIR, filename)
        output_pdf_path = os.path.join(OUTPUT_DIR, filename)
        metadata_json_path = os.path.join(STRUCTURED_OUTPUT_DIR, f"{Path(filename).stem}.json")

        print(f"🔍 Processing: {filename}")
        
        should_run_ai = True
        title_author_data = {}

        try:
            # --- ENHANCEMENT: Use fitz (PyMuPDF) for consistency and speed ---
            with fitz.open(input_pdf_path) as doc:
                meta = doc.metadata
                existing_title = meta.get("title", "").strip()
                existing_author = meta.get("author", "").strip()

                # Check if existing metadata is generic or empty
                if existing_title and existing_title.lower() not in GENERIC_TITLES:
                    title_author_data = {
                        "article_title": existing_title,
                        "author": existing_author
                    }
                    should_run_ai = False
        
        except Exception as e:
            print(f"⚠️ Could not read metadata from {filename}: {e}. Will proceed with AI.")

        if should_run_ai:
            print("🤖 Metadata missing or generic, using AI detection...")
            # Pass structured_output_dir for AI suggestions to save visuals if needed
            title_author_data = extract_title_author(input_pdf_path, Path(STRUCTURED_OUTPUT_DIR))

        # Save structured output in all cases
        with open(metadata_json_path, "w", encoding="utf-8") as f:
            json.dump(title_author_data, f, indent=2)
        print(f"💾 Title/author info saved to: {metadata_json_path}")

        # Embed metadata if fields are present
        if title_author_data.get("article_title"):
            try:
                embed_metadata(
                    input_pdf_path=input_pdf_path,
                    output_pdf_path=output_pdf_path,
                    pdf_base_name=Path(filename).stem, # Pass base name
                    output_dir_for_logs=Path(STRUCTURED_OUTPUT_DIR), # Pass output dir for logs
                    title=title_author_data.get("article_title"),
                    author=title_author_data.get("author") # Handles case where author might be None
                )
                print(f"✅ Embedded title/author into new file in output directory.\n")
            except Exception as e:
                print(f"❌ Failed to embed title/author into {filename}: {e}\n")
        else:
            print(f"⚠️ Skipped embedding for {filename}: no valid title found.\n")

if __name__ == "__main__":
    process_title_author()
