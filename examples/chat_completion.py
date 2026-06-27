"""Synchronous chat completion through the Ciralgo proxy."""

from ciralgo import Client

client = Client()  # reads CIRALGO_API_KEY from env

response = client.chat.completions.create(
    model="openai/gpt-4o-mini",
    messages=[
        {"role": "system", "content": "You are a concise EU AI Act assistant."},
        {"role": "user", "content": "List the three highest-risk applications under EU AI Act Article 5."},
    ],
    max_tokens=300,
    tags={"project": "ai-act-demo", "env": "dev"},
)

print(response["choices"][0]["message"]["content"])
print(f"\nUsage: {response['usage']}")
