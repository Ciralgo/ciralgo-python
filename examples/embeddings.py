"""Batch embeddings."""

from ciralgo import Client

client = Client()

result = client.embeddings.create(
    model="openai/text-embedding-3-small",
    input=[
        "EU AI Act Article 15: accuracy, robustness, cybersecurity.",
        "EU AI Act Article 14: human oversight requirements.",
        "EU AI Act Article 12: record-keeping for high-risk AI.",
    ],
)

for i, item in enumerate(result["data"]):
    print(f"vector {i} dimension: {len(item['embedding'])}")
