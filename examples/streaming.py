"""Streaming chat completion."""

from ciralgo import Client

client = Client()

print("Streaming...\n")
for chunk in client.chat.completions.create(
    model="openai/gpt-4o-mini",
    messages=[{"role": "user", "content": "Write a 6-line haiku about compliance."}],
    stream=True,
):
    choices = chunk.get("choices", [])
    if not choices:
        continue
    delta = choices[0].get("delta", {}).get("content", "")
    if delta:
        print(delta, end="", flush=True)
print("\n\n[done]")
