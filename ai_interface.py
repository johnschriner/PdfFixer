import base64
import json
import requests

MODEL_NAME = "llama3.2-vision"
OLLAMA_URL = "http://localhost:11434/api/generate"

# Full prompt with instructions and expected output format
prompt_template = """You are a highly accurate academic document parser. Your task is to extract structured data from a page of a scholarly article. The input includes both the OCR text and a rendered image of the page. Use layout and context to interpret headings, citations, and footnotes correctly.

Page text:
{text}

Output a JSON object with the following keys:
- "article_title": (string or null) Only on page 1.
- "author": (string or null) Only on page 1.
- "headings": list of strings (do not include entire paragraphs; only true section headings).
- "figures": list of brief captions or descriptions of figures (can be empty).
- "tables": list of brief descriptions of tables (can be empty).
- "lists": list of items that appear as bullet points or numbered lists (can be empty).
- "citations": list of objects markers (e.g., [1], superscript ¹, *, etc.) outputted like: { "marker": "[2]", "text": "Full footnote text near the bottom of the page with the matching marker." }
- "suggested_tags": list of 2–5 broad topic tags (e.g. "Marxism", "Linguistic historiography")
- "start_new_section": true/false — whether this page starts a new major section.
- "notes": optional string to indicate page features or caveats (e.g. "No citations detected", "Page contains multiple footnotes").

If a superscript or marker like ¹, *, or [2] appears in the main text and a corresponding line appears at the bottom of the page, treat this as a citation pair.

Rules:
- Do not hallucinate data. If a field is not present, leave it empty or null.
- Citation markers must be preserved exactly as they appear in the text (e.g. “[3]” or superscripted numbers).
- If citation marker and full citation cannot be reliably paired, include them separately in `notes`.

Respond with only valid JSON matching this structure. Do not include explanation or extra text.""".strip()


def get_structured_summary(text, image_path):
    with open(image_path, "rb") as img_file:
        image_bytes = img_file.read()

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt_template.replace("{text}", text),
        "images": [base64.b64encode(image_bytes).decode("utf-8")],
        "stream": False
    }

    response = requests.post(OLLAMA_URL, json=payload)
    content = response.text.strip()

    try:
        return json.loads(content)
    except Exception:
        raise Exception("Unexpected response format from model API:\n" + content)

def get_visuals_summary(image_path, page_text=None):
    """
    Given an image of a visual (image/chart/table) and optional page OCR text,
    send both to the AI model to get bounding box info, classification, and alt-text.
    """
    from ollama import Client
    import base64

    client = Client(host="http://localhost:11434")

    # Read and encode image to base64
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    prompt = (
        "You are analyzing a visual element extracted from a PDF. "
        "Use the provided image and page text to:"
        "1) Determine if it is a photo, chart, table, or other."
        "2) Provide the bounding box in PDF page coordinates if possible."
        "3) Write objective alt-text starting with 'This description is AI-generated.'. "
        "4) Return a JSON like: {\"type\": \"chart\", \"bbox\": [x0,y0,x1,y1], \"alt_text\": \"This description is AI-generated...\"}"
    )

    if page_text:
        prompt += f"\n\nPage Text:\n{page_text}"

    response = client.chat(
        model="llama3.2-vision",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}}
                ],
            }
        ],
        options={"temperature": 0.2},
    )

    # Return raw model response
    return response["message"]["content"]

