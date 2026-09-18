"""Foundation Model API client (chat) for AI features."""
from openai import OpenAI
from .config import get_host, get_token, LLM_MODEL


def _client() -> OpenAI:
    host = get_host().rstrip("/")
    return OpenAI(api_key=get_token(), base_url=f"{host}/serving-endpoints")


def chat(messages, max_tokens=900, temperature=0.3, model=None):
    resp = _client().chat.completions.create(
        model=model or LLM_MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return resp.choices[0].message.content
