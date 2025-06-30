#!/usr/bin/env python3
import sys
import os
import json
import fitz  # PyMuPDF
import pikepdf

def build_structure(pdf_path, structured_data_folder, alt_text_folder, output_path):
    # Load original PDF
    pdf_in = pikepdf.open(pdf_path)
    doc = fitz.open(pdf_path)

    # Set PDF/UA Marked flag
    pdf_in.root['/MarkInfo'] = pikepdf.Dictionary(Marked=True)
    pdf_in.root['/ViewerPreferences'] = pikepdf.Dictionary(DisplayDocTitle=True)

    # Build basic StructTreeRoot
    struct_tree = pikepdf.Dictionary(Type=pikepdf.Name('/StructTreeRoot'), K=[])
    role_map = pikepdf.Dictionary(H1=pikepdf.Name('/H1'), P=pikepdf.Name('/P'), Figure=pikepdf.Name('/Figure'))
    struct_tree['/RoleMap'] = role_map

    # Build structure kids
    kids = []

    for page_num in range(len(doc)):
        page_struct = pikepdf.Dictionary(Type=pikepdf.Name('/StructElem'),
                                         S=pikepdf.Name('/Document'),
                                         P=pikepdf.Name('/StructTreeRoot'),
                                         Pg=pdf_in.pages[page_num],
                                         K=[])

        structured_json_path = os.path.join(structured_data_folder, f"page_{page_num+1:03}.json")
        if os.path.exists(structured_json_path):
            with open(structured_json_path, 'r', encoding='utf-8') as f:
                structured_data = json.load(f)
                # Add headings
                for heading in structured_data.get('headings', []):
                    heading_elem = pikepdf.Dictionary(Type=pikepdf.Name('/StructElem'),
                                                      S=pikepdf.Name('/H1'),
                                                      Pg=pdf_in.pages[page_num],
                                                      K=heading['heading'])
                    page_struct['/K'].append(heading_elem)
                # Add citations as paragraphs
                for citation in structured_data.get('citations', []):
                    para_elem = pikepdf.Dictionary(Type=pikepdf.Name('/StructElem'),
                                                   S=pikepdf.Name('/P'),
                                                   Pg=pdf_in.pages[page_num],
                                                   K=citation)
                    page_struct['/K'].append(para_elem)

        # Add figures with alt-text
        alt_text_jsons = [f for f in os.listdir(alt_text_folder) if f.startswith(f"page-{page_num+1:03}") and f.endswith(".json")]
        for alt_file in alt_text_jsons:
            with open(os.path.join(alt_text_folder, alt_file), 'r', encoding='utf-8') as f:
                alt_data = json.load(f)
                alt_text = alt_data.get("alt_text", "No alt-text available")
                figure_elem = pikepdf.Dictionary(Type=pikepdf.Name('/StructElem'),
                                                 S=pikepdf.Name('/Figure'),
                                                 Pg=pdf_in.pages[page_num],
                                                 Alt=alt_text)
                page_struct['/K'].append(figure_elem)

        kids.append(page_struct)

    struct_tree['/K'] = kids
    pdf_in.root['/StructTreeRoot'] = struct_tree
    pdf_in.save(output_path)
    print(f"🎉 Structured PDF saved with headings and alt-text: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python tagger.py input.pdf structured_data_folder alt_text_folder output.pdf")
        sys.exit(1)

    build_structure(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
