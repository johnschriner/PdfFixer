import os
import json
import base64
import requests
import re

VISUALS_FOLDER = "visuals"
MODEL_NAME = "llama3.2-vision"
OLLAMA_API_URL = "http://localhost:11434/api/generate"

HEADERS = {"Content-Type": "application/json"}

PROMPT = (
    "You are an accessibility assistant. Generate a concise, objective alt-text description of the image. "
    "Focus on what is visible, without interpretation or stylistic commentary. "
    "Only respond with a JSON object like this:\n"
    "{\n  \"alt_text\": \"...\"\n}"
)

def extract_json_block(text):
    """Extract the first valid JSON object in a block of text."""
    try:
        match = re.search(r"\{[\s\S]*?\}", text)
        if match:
            return json.loads(match.group())
    except json.JSONDecodeError:
        pass
    return None

def generate_alt_text(image_path):
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "model": MODEL_NAME,
        "prompt": PROMPT,
        "images": [image_b64],
        "stream": False,
    }

    response = requests.post(OLLAMA_API_URL, headers=HEADERS, json=payload)
    content = response.json().get("response", "")

    return extract_json_block(content)

if __name__ == "__main__":
    for filename in os.listdir(VISUALS_FOLDER):
        if filename.lower().endswith(".png"):
            image_path = os.path.join(VISUALS_FOLDER, filename)
            print(f"🖼 Generating alt-text for {filename}...")

            result = generate_alt_text(image_path)
            if result and "alt_text" in result:
                output_path = os.path.splitext(image_path)[0] + ".json"
                with open(output_path, "w") as f:
                    json.dump(result, f, indent=2)
                print(f"✅ Saved alt-text to {output_path}")
            else:
                print(f"❌ Failed to extract alt-text for {filename}")
