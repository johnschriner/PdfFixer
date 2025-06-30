import os
from PyPDF2 import PdfReader, PdfWriter

def split_pdf(filepath, output_dir):
    reader = PdfReader(filepath)
    base_filename = os.path.splitext(os.path.basename(filepath))[0]
    output_paths = []
    for i, page in enumerate(reader.pages):
        writer = PdfWriter()
        writer.add_page(page)
        chunk_path = os.path.join(output_dir, f"{base_filename}_chunk_{i+1}.pdf")
        with open(chunk_path, "wb") as f:
            writer.write(f)
        output_paths.append(chunk_path)
    return output_paths
