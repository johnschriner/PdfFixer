
import fitz
import os

def split_pdf(path, output_dir):
    doc = fitz.open(path)
    paths = []
    for i in range(len(doc)):
        chunk = fitz.open()
        chunk.insert_pdf(doc, from_page=i, to_page=i)
        output_path = os.path.join(output_dir, f'chunk_{i}.pdf')
        chunk.save(output_path)
        chunk.close()
        paths.append(output_path)
    return paths
