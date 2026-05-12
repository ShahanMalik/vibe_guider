import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from tenacity import retry,stop_after_attempt,wait_exponential

# Load .env from backend directory
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError(
        "OPENAI_API_KEY not found. "
        "Please set it in .env file or OPENAI_API_KEY environment variable."
    )

client = OpenAI(api_key=api_key)

MODEL=os.getenv(
 "OPENAI_MODEL",
 "gpt-4o-mini-2024-07-18"
)

@retry(
 stop=stop_after_attempt(3),
 wait=wait_exponential()
)
def _ask_llm_non_stream(prompt):

    r=client.chat.completions.create(
        model=MODEL,
        messages=[
          {
            "role":"system",
            "content":"You are an expert AI assistant with deep knowledge across all domains including technology, science, business, history, math, coding, and more. Always give clear, accurate, well-structured, and helpful answers. Adapt your tone and depth to what the user is asking."
          },
          {
            "role":"user",
            "content":prompt
          }
        ],
        temperature=.3
    )

    return r.choices[0].message.content


def ask_llm(prompt, stream_writer=None):
    """
    Ask the LLM and optionally stream incremental text chunks via stream_writer.
    stream_writer receives plain text chunks as they arrive.
    """
    if stream_writer is None:
        return _ask_llm_non_stream(prompt)

    stream = client.chat.completions.create(
        model=MODEL,
        messages=[
          {
            "role":"system",
            "content":"You are an expert AI assistant with deep knowledge across all domains including technology, science, business, history, math, coding, and more. Always give clear, accurate, well-structured, and helpful answers. Adapt your tone and depth to what the user is asking."
          },
          {
            "role":"user",
            "content":prompt
          }
        ],
        temperature=.3,
        stream=True
    )

    parts = []
    for chunk in stream:
        delta = ""
        if chunk.choices and chunk.choices[0].delta:
            delta = chunk.choices[0].delta.content or ""
        if delta:
            parts.append(delta)
            stream_writer(delta)

    return "".join(parts)