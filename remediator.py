
import fitz  # PyMuPDF
import logging
import json
import requests

logging.basicConfig(level=logging.INFO)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2-vision"

def extract_existing_metadata(doc):
    meta = doc.metadata
    return {
        "title": meta.get("title", "").strip(),
        "author": meta.get("author", "").strip(),
        "keywords": meta.get("keywords", "").strip()
    }

def is_metadata_valid(meta_field):
    invalid_values = ["", "unknown", "none", "null"]
    return meta_field.strip().lower() not in invalid_values

def infer_title_author(text):
    prompt = (
        "The following is the beginning of a scholarly article. Identify the title and author with high confidence.\n\n"
        f"{text[:3000]}\n\n"
        "Respond in JSON like this:\n"
        "{\n"
        "  \"title\": \"...\",\n"
        "  \"author\": \"...\"\n"
        "}"
    )
    response = requests.post(OLLAMA_URL, json={
        "model": MODEL,
        "prompt": prompt,
        "stream": False
    })
    result = json.loads(response.json()['response'])
    return result.get("title", ""), result.get("author", "")

def infer_keywords(text):
    prompt = (
        "Analyze the following article and return exactly three broad subject keywords that describe its content, separated by commas.\n\n"
        f"{text[:3000]}\n\n"
        "Respond like this:\n"
        "International Law, Human Rights, Climate Change"
    )
    response = requests.post(OLLAMA_URL, json={
        "model": MODEL,
        "prompt": prompt,
        "stream": False
    })
    return response.json()["response"].strip()

def remediate_pdf(input_pdf_path, output_pdf_path):
    logging.info(f"🔍 Opening PDF: {input_pdf_path}")
    doc = fitz.open(input_pdf_path)

    text = ""
    for page in doc:
        page_text = page.get_text()
        if not page_text.strip():
            logging.info(f"🧠 OCR on page {page.number + 1}")
            page_text = page.get_text("text", flags=0)
        text += page_text + "\n"

    existing_meta = extract_existing_metadata(doc)
    logging.info(f"📄 Existing metadata: {existing_meta}")

    new_metadata = {}

    if is_metadata_valid(existing_meta["title"]):
        new_metadata["title"] = existing_meta["title"]
        logging.info("✅ Title is valid and preserved.")
    else:
        new_metadata["title"], _ = infer_title_author(text)
        logging.info(f"🧠 Inferred title: {new_metadata['title']}")

    if is_metadata_valid(existing_meta["author"]):
        new_metadata["author"] = existing_meta["author"]
        logging.info("✅ Author is valid and preserved.")
    else:
        _, new_metadata["author"] = infer_title_author(text)
        logging.info(f"🧠 Inferred author: {new_metadata['author']}")

    if is_metadata_valid(existing_meta["keywords"]):
        new_metadata["keywords"] = existing_meta["keywords"]
        logging.info("✅ Keywords are valid and preserved.")
    else:
        new_metadata["keywords"] = infer_keywords(text)
        logging.info(f"🧠 Inferred keywords: {new_metadata['keywords']}")

    doc.set_metadata({
        "title": new_metadata["title"],
        "author": new_metadata["author"],
        "keywords": new_metadata["keywords"]
    })

    doc.save(output_pdf_path, deflate=True, clean=True)
    logging.info("✅ Remediation complete and saved.")

    return (
        new_metadata.get("title", ""),
        new_metadata.get("author", ""),
        new_metadata.get("keywords", "")
    )
