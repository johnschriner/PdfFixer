import os
import json
import re
import base64
from pathlib import Path
import requests

# -------------------- Configuration --------------------

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_URL = f"{OLLAMA_HOST}/api/generate"

# Prefer text model when page text exists; fall back to vision for image-only pages
TEXT_MODEL = os.getenv("PDFFIXER_TEXT_MODEL", "llama3.2")
VISION_MODEL = os.getenv("PDFFIXER_VISION_MODEL", "llama3.2-vision")

# -------------------- Subject helpers --------------------

def load_subject_list(csv_path="subject_list.csv"):
    path = Path(csv_path)
    if not path.exists():
        return []
    items = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        val = line.strip()
        if val and not val.startswith("#"):
            items.append(val)
    return items

def format_prompt(text, subject_list=None):
    """
    Build a prompt for either choosing a subject from a controlled list,
    or generating freeform subjects when no list is provided.
    """
    text = (text or "").strip()
    if subject_list:
        # Constrained selection: pick exactly ONE subject from the list
        list_blob = "\n".join(f"- {s}" for s in subject_list)
        prompt = (
            "You are a librarian. Choose exactly ONE subject from the list that best fits the article. "
            "Return ONLY the chosen subject as plain text, nothing else.\n\n"
            f"Subject list:\n{list_blob}\n\n"
            "Article text:\n" + text[:3000]
        )
    else:
        # Freeform generation (used by 'Custom Subjects (freeform)' in the UI)
        prompt = (
            "You are a librarian. Generate 3–5 concise subject tags for the article, comma-separated. "
            "Do not include explanations or numbering—return only the comma-separated list.\n\n"
            "Article text:\n" + text[:3000]
        )
    return prompt

# -------------------- Core Ollama call --------------------

def _post_ollama(payload):
    """
    Call Ollama /api/generate robustly.
    Works for both non-stream (JSON) and (defensively) NDJSON streaming.
    """
    headers = {"Content-Type": "application/json"}
    resp = requests.post(OLLAMA_URL, headers=headers, json=payload, timeout=180)
    resp.raise_for_status()

    ctype = resp.headers.get("Content-Type", "")
    # Non-streaming path: Ollama returns a single JSON object with a 'response' field
    if "application/json" in ctype and "x-ndjson" not in ctype:
        try:
            data = resp.json()
            return (data.get("response") or "").strip()
        except Exception:
            pass  # fall through to line-wise parsing as a safety net

    # Defensive fallback: parse line-delimited JSON chunks and join 'response'
    text_out = []
    for line in resp.iter_lines():
        if not line:
            continue
        try:
            obj = json.loads(line)
            piece = obj.get("response", "")
            if piece:
                text_out.append(piece)
        except Exception:
            # If the server sent plain text, just collect it
            try:
                s = line.decode("utf-8", errors="ignore")
            except Exception:
                s = str(line)
            text_out.append(s)
    return "".join(text_out).strip()

def make_chat_completion(system_prompt, user_prompt, image_bytes=None, model_name=None):
    """
    Small wrapper around Ollama's /api/generate.
    If image_bytes is provided, this assumes the model supports vision.
    """
    model = model_name or TEXT_MODEL
    payload = {
        "model": model,
        "prompt": user_prompt or "",
        "system": system_prompt or "",
        "stream": False,
    }
    if image_bytes:
        payload["images"] = [base64.b64encode(image_bytes).decode("utf-8")]
    print(f"DEBUG: Calling Ollama model '{model}' for prompt length {len(payload['prompt'])}.")
    try:
        return _post_ollama(payload)
    except requests.exceptions.RequestException as e:
        print(f"❌ Error communicating with Ollama: {e}")
        return ""

# -------------------- Metadata extraction --------------------

def _clean_llm_json_response(raw_response_string):
    """
    Clean a raw LLM response into a JSON object string.
    Handles ``` fences, stray backslashes, smart quotes, and control chars.
    """
    cleaned = (raw_response_string or "").replace("```json", "").replace("```", "").strip()

    # Isolate the first {...} block
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        print(f"Warning: Could not find valid JSON object boundaries in raw response: {raw_response_string}")
        return ""

    cleaned = cleaned[start : end + 1]
    cleaned = re.sub(r"\\_", "_", cleaned)
    cleaned = re.sub(r'\\([^\\\"/bfnrtu])', r"\1", cleaned)
    cleaned = cleaned.replace("\\\\", "\\")

    cleaned = cleaned.replace("\xa0", " ")
    cleaned = cleaned.replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", cleaned)
    return cleaned

def _clean_title_symbols(title):
    if not title:
        return title
    # Strip doodads, excessive whitespace
    t = re.sub(r"[•·⋅◦•]+", " ", title).strip()
    t = re.sub(r"\s+", " ", t)
    return t

def _format_single_author(name_part):
    """Format 'First Middle Last' or 'Last, First Middle' → 'Last, First M.'"""
    if not name_part:
        return ""
    # Remove footnote markers
    cleaned = re.sub(
        r'[\*\†‡§¶#\u00B2\u00B3\u00B9\u2070-\u2079\u207A-\u207E\u207F]|\b\d+\b(?=\s*$|\s*\.)',
        "",
        name_part,
    ).strip()

    if "," in cleaned:  # "Last, First Middle"
        last, right = [p.strip() for p in cleaned.split(",", 1)]
        tokens = [t for t in right.split() if t]
        if not tokens:
            return last
        first, *middles = tokens
        inits = " ".join(f"{m[0].upper()}." for m in middles if m and m[0].isalpha())
        return f"{last}, {first}" + (f" {inits}" if inits else "")

    # "First Middle Last"
    parts = cleaned.split()
    if len(parts) == 1:
        return parts[0]
    first, last = parts[0], parts[-1]
    middles = parts[1:-1]
    inits = " ".join(f"{m[0].upper()}." for m in middles if m and m[0].isalpha())
    return f"{last}, {first}" + (f" {inits}" if inits else "")

def format_author_lastname_firstname(authors_field):
    """
    Normalize an author field. Handles single author; if multiple separated by
    ';', '&', 'and', or commas, keeps original order but normalizes each.
    """
    if not authors_field:
        return "Unknown"
    # split on " and ", "&", and semicolons, but be gentle with commas inside single names
    parts = re.split(r"\s+and\s+|&|;", authors_field)
    if len(parts) == 1:
        # Could still be "Last, First" or a single name
        return _format_single_author(parts[0].strip())
    return "; ".join(_format_single_author(p.strip()) for p in parts if p.strip())

def get_title_author(text, image_bytes=None):
    """
    Decide the right model (text or vision), call it, and return a dict.
    ALWAYS returns a dict: {'article_title': str, 'author': str}
    """
    text = (text or "").strip()
    use_vision = not bool(text)

    system_prompt = (
        "You are an expert academic paper metadata extractor. "
        "Return ONLY a single JSON object with two keys: 'article_title' (string) and 'author' (string). "
        "If unknown, use 'Untitled' and 'Unknown'. Escape inner quotes. No extra text."
    )

    if use_vision:
        user_prompt = "Extract the article title and author from this scanned first page image."
        raw = make_chat_completion(system_prompt, user_prompt, image_bytes=image_bytes, model_name=VISION_MODEL)
    else:
        # text path: do NOT send images—forces pure text model on GPU
        user_prompt = f"Extract title and author from this page text:\n\n{text[:2000]}"
        raw = make_chat_completion(system_prompt, user_prompt, image_bytes=None, model_name=TEXT_MODEL)

    # Parse
    try:
        s = _clean_llm_json_response(raw)
        print(f"DEBUG (get_title_author): Attempting to parse JSON string: '{s}'")
        data = json.loads(s) if s else {}
    except Exception as e:
        print(f"❌ JSON parse failed in get_title_author: {e}\nRaw: {raw}")
        data = {}

    article_title = _clean_title_symbols(data.get("article_title") or "") or "Untitled"
    author = format_author_lastname_firstname(data.get("author") or "") or "Unknown"
    return {"article_title": article_title, "author": author}

# -------------------- Subjects & Alt text --------------------

def generate_subjects(text, subject_list=None):
    """
    If subject_list is provided, choose exactly one from the list.
    Otherwise, generate a small comma-separated list of tags.
    """
    prompt = format_prompt(text or "", subject_list=subject_list)
    model = TEXT_MODEL
    response = make_chat_completion("", prompt, model_name=model)

    if subject_list:
        cand = (response or "").strip()
        if cand in subject_list:
            return [cand]
        print(f"⚠️ AI response '{cand}' not found in subject list. Returning empty.")
        return []
    else:
        subjects = [s.strip() for s in (response or "").split(",") if s.strip()]
        return subjects

def generate_alt_text(image_bytes, page_text=None):
    system_prompt = (
        "You are an accessibility expert. Generate concise, descriptive alt text for the image. "
        "Three sentences max. Consider the provided page text if present."
    )
    user_prompt = "Generate alt text for this image."
    if page_text:
        user_prompt += f"\n\nContext from page: {page_text[:1000]}"
    model = VISION_MODEL
    resp = make_chat_completion(system_prompt, user_prompt, image_bytes=image_bytes, model_name=model)
    return (resp or "").strip()

# -------------------- Optional: citations/layout --------------------

def extract_citations(text):
    system_prompt = (
        "You are a legal citation extraction expert. "
        "Identify and extract all footnotes or endnotes from the provided text. "
        "Return JSON: {'footnotes': [{'citation_number': <int>, 'citation_text': <str>}]} . "
        "If none, return {'footnotes': []}. No extra text."
    )
    user_prompt = f"Extract footnotes from the following text:\n\n{(text or '')}"
    raw = make_chat_completion(system_prompt, user_prompt, model_name=TEXT_MODEL)
    try:
        s = _clean_llm_json_response(raw)
        print(f"DEBUG (citations): Attempting to parse JSON string: '{s}'")
        data = json.loads(s) if s else {}
        if isinstance(data, dict) and "footnotes" in data:
            return data
    except Exception as e:
        print(f"❌ Citation parse failed: {e}\nRaw: {raw}")
    return {"footnotes": []}

def analyze_page_structure(image_bytes):
    system_prompt = (
        "You are a document layout analysis expert. Describe the layout of this page. "
        "Identify major elements like headings, paragraphs, images, and lists. "
        "This will be used to create accessibility tags."
    )
    resp = make_chat_completion(system_prompt, "", image_bytes=image_bytes, model_name=VISION_MODEL)
    return (resp or "").strip()

__all__ = [
    "generate_subjects",
    "load_subject_list",
    "get_title_author",
    "make_chat_completion",
    "generate_alt_text",
    "extract_citations",
    "analyze_page_structure",
    "format_author_lastname_firstname",
]
