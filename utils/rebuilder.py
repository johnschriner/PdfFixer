
import fitz

def rebuild_pdf(paths, output_path):
    output = fitz.open()
    for path in paths:
        part = fitz.open(path)
        output.insert_pdf(part)
        part.close()
    output.save(output_path)
    output.close()
