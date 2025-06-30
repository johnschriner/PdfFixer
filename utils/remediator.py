
import requests
import os

LOCAL_AI_ENDPOINT = "http://localhost:11434/process_chunk"

def remediate_chunk(chunk_path):
    with open(chunk_path, 'rb') as f:
        response = requests.post(LOCAL_AI_ENDPOINT, files={'file': f})
    if response.status_code != 200:
        raise Exception("AI remediation failed: " + response.text)

    # Save fixed file to a new path
    fixed_path = chunk_path.replace('.pdf', '_fixed.pdf')
    with open(fixed_path, 'wb') as out:
        out.write(response.content)
    return fixed_path
