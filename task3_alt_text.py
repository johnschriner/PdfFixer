import os
import fitz
import base64
import json
from ai_interface import generate_alt_text
from pathlib import Path
import shutil

def run_alt_text_task(input_dir, visuals_dir, structured_output_dir, log_queue=None, send_progress_func=None):
    """
    Processes all PDFs in input_dir to generate alt text for images.
    Reports progress via the provided log_queue or send_progress_func.
    
    Args:
        input_dir (Path): Directory containing input PDF files.
        visuals_dir (Path): Directory to save extracted image files.
        structured_output_dir (Path): Directory to save JSON reports.
        log_queue (Queue, optional): A queue object to put log messages into (for multiprocessing).
                                     Defaults to None.
        send_progress_func (callable, optional): A function to send progress messages,
                                                 e.g., a SocketIO emit function. Defaults to None.
    """
    def log_message(message, level='info'):
        if log_queue:
            log_queue.put(message)
        elif send_progress_func:
            send_progress_func(message)
        else:
            print(message) # Fallback to print if no logging mechanism is provided

    log_message("🖼️ Starting Alt Text Generation Task...")
    
    pdf_files = [f for f in os.listdir(input_dir) if f.lower().endswith(".pdf")]
    if not pdf_files:
        log_message("No PDFs found for alt-text generation.")
        return

    # Ensure output directories exist
    visuals_dir.mkdir(parents=True, exist_ok=True)
    structured_output_dir.mkdir(parents=True, exist_ok=True)

    for filename in pdf_files:
        input_pdf_path = os.path.join(input_dir, filename)
        pdf_base_name = Path(filename).stem
        doc = None
        
        log_message(f"Processing alt-text for: {filename}")

        try:
            doc = fitz.open(input_pdf_path)
            images_found = []
            
            for page_num in range(doc.page_count):
                page = doc.load_page(page_num)
                image_list = page.get_images(full=True) # Get all images on the page

                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    
                    # --- ENHANCEMENT: Filter out insignificant images based on size ---
                    # Get image dimensions (if available, requires more advanced PyMuPDF usage or PIL)
                    # For a simpler check, we can assume very small images are decorative.
                    # A more robust check would involve loading the image with PIL and checking actual dimensions.
                    # For now, we'll use a heuristic: if the image data is very small, it's likely insignificant.
                    # A better approach would be to check actual pixel dimensions if PyMuPDF provides them easily,
                    # or to use a library like Pillow (PIL) to load and check.
                    # As PyMuPDF's extract_image doesn't directly give width/height, we'll use byte size as a rough proxy.
                    # A typical small icon might be a few KB, a significant image much larger.
                    if len(image_bytes) < 2048: # Arbitrary threshold, adjust as needed (e.g., 2KB)
                        log_message(f"  - Skipping small image (approx {len(image_bytes)/1024:.1f}KB) on page {page_num + 1}, img {img_index + 1}.", level='info')
                        continue

                    image_filename = f"{pdf_base_name}_page{page_num+1}_img{img_index+1}.{image_ext}"
                    image_path = visuals_dir / image_filename
                    
                    with open(image_path, "wb") as f:
                        f.write(image_bytes)
                    
                    log_message(f"  - Extracted image: {image_filename} from page {page_num + 1}")

                    # --- MODIFICATION: Remove page_text from generate_alt_text call ---
                    # This ensures the AI focuses solely on the image content.
                    alt_text = generate_alt_text(image_bytes)
                    
                    # Only add to images_found if alt_text is not empty
                    if alt_text.strip():
                        images_found.append({
                            "page": page_num + 1,
                            "image_filename": image_filename,
                            "alt_text": alt_text
                        })
                        log_message(f"    -> Generated alt text: '{alt_text[:50]}...'")
                    else:
                        log_message(f"    -> Skipped alt text generation for image {image_filename}: AI returned empty or insignificant.", level='info')


            if images_found:
                report_data = {
                    "file": filename,
                    "images": images_found
                }
                json_report_filename = f"{pdf_base_name}_alt_text_report.json"
                final_json_report_path = structured_output_dir / json_report_filename

                with open(final_json_report_path, "w", encoding="utf-8") as json_file:
                    json.dump(report_data, json_file, indent=2)
                log_message(f"✅ Generated JSON report: {final_json_report_path}")

            else: # No significant images found or alt-text generated
                log_message(f"  - No significant images found or alt-text generated for {filename}.")
            
        except Exception as e:
            log_message(f"❌ An error occurred while processing {filename}: {e}", level='error')
        finally:
            if doc:
                doc.close()

