import requests
import json
import re

prompt = """
You are an expert video clip selector. Review the following video transcript and extract as many highly engaging clips as possible. 
Every single good hook you find should be extracted. The clips must be between 50 and 90 seconds long.
They must comply with these campaign rules:
RULES: Find the most universally engaging and viral hooks. Look for high emotion, interesting facts, or strong opinions.

Transcript:
[0.00 - 10.00] Did you know that the universe is expanding?
[10.00 - 20.00] Yes, it is expanding faster than the speed of light.
[20.00 - 60.00] This means that eventually, all other galaxies will be invisible to us.
[60.00 - 120.00] We will be completely alone in the darkness of space.

Output ONLY valid JSON. No markdown backticks, no explanations. The output must be a list of dictionaries with this exact schema:
[
  {{
    "title": "A short, catchy, and viral title for this specific clip",
    "start_time": float,
    "end_time": float,
    "hook_reasoning": "string explaining why this is engaging",
    "cta_overlay_text": "short text under 20 chars",
    "requires_captions": boolean
  }}
]
"""

try:
    response = requests.post("http://localhost:11434/api/generate", json={
        "model": "llama3",
        "prompt": prompt,
        "stream": False
    })
    
    if response.status_code == 200:
        text = response.json().get('response', '').strip()
        print("RAW RESPONSE:")
        print(text)
        print("---")
        
        # Robust fallback parsing mechanism
        if "```json" in text:
            match = re.search(r"```json\s*(.*?)\s*```", text, re.S)
            if match:
                text = match.group(1)
        elif "```" in text:
            match = re.search(r"```\s*(.*?)\s*```", text, re.S)
            if match:
                text = match.group(1)
        
        start_idx = text.find('[')
        end_idx = text.rfind(']')
        if start_idx != -1 and end_idx != -1:
            text = text[start_idx:end_idx+1]
            
        print("PARSED JSON STRING:")
        print(text)
        clips = json.loads(text)
        print("SUCCESSFULLY LOADED JSON. Titles:")
        for c in clips:
            print(f"- {c.get('title')}")
    else:
        print(f"Error: HTTP {response.status_code}")
except Exception as e:
    print(f"Failed: {e}")
