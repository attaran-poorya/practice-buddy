"""Tiny OpenAI-compatible chat client. Gemini, Groq and Ollama all speak this API,
so switching providers is just a base URL + key + model name."""
import base64
import io
import json
import os
import re

import requests

PROVIDERS = {
    # free tier, has vision (needed for reading the sheet music photo)
    "gemini": dict(base="https://generativelanguage.googleapis.com/v1beta/openai",
                   key_env="GEMINI_API_KEY", model="gemini-2.5-flash",
                   vision_model="gemini-2.5-flash"),
    # free tier, very fast; text model + a vision-capable Llama
    "groq": dict(base="https://api.groq.com/openai/v1", key_env="GROQ_API_KEY",
                 model="llama-3.3-70b-versatile",
                 vision_model="meta-llama/llama-4-scout-17b-16e-instruct"),
    # any other OpenAI-compatible endpoint: set LLM_BASE_URL, LLM_API_KEY, LLM_MODEL
    "custom": dict(base="", key_env="LLM_API_KEY", model="", vision_model=""),
    # fully local, no key: `ollama pull qwen2.5:7b` (and qwen2.5vl:7b for photos)
    "ollama": dict(base="http://localhost:11434/v1", key_env=None,
                   model="qwen2.5:7b", vision_model="qwen2.5vl:7b"),
}


def load_dotenv(path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")):
    if not os.path.exists(path):
        return
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))


class LLM:
    def __init__(self, provider="gemini"):
        load_dotenv()
        p = PROVIDERS[provider]
        self.provider = provider
        self.base = os.environ.get("LLM_BASE_URL", p["base"]).rstrip("/")
        self.model = os.environ.get("LLM_MODEL", p["model"])
        self.vision_model = os.environ.get("LLM_VISION_MODEL", p["vision_model"] or self.model)
        self.key = os.environ.get(p["key_env"]) if p["key_env"] else None
        if p["key_env"] and not self.key:
            raise RuntimeError(
                f"{p['key_env']} is not set. Put it in violin_coach/.env "
                f"(see .env.example) or use --llm ollama / --no-llm.")

    def chat(self, messages, model=None, json_mode=False, temperature=0.3):
        body = dict(model=model or self.model, messages=messages,
                    temperature=temperature)
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"
        try:
            r = requests.post(f"{self.base}/chat/completions", json=body,
                              headers=headers, timeout=(15, 180))
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"cannot reach {self.base} ({type(e).__name__})") from None
        if r.status_code != 200:
            raise RuntimeError(f"LLM error {r.status_code}: {r.text[:500]}")
        return r.json()["choices"][0]["message"]["content"]

    def vision(self, prompt, image):
        """image: PIL.Image"""
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=90)
        url = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
        msg = [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": url}},
        ]}]
        return self.chat(msg, model=self.vision_model, temperature=0.1)


def extract_json(text):
    """Small models sometimes wrap JSON in prose or code fences."""
    try:
        return json.loads(text)
    except ValueError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise
        return json.loads(m.group(0))
