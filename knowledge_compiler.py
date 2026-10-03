import json
from pathlib import Path

DOCUMENTS_DIR = Path("documents")
OUTPUT_FILE = Path("knowledge_graph.json")


def load_documents():
    documents = []

    for path in DOCUMENTS_DIR.glob("*.json"):
        with open(path, "r", encoding="utf-8") as file:
            documents.append(json.load(file))

    return documents


def compile_knowledge(documents):
    assets = {}
    documents_by_id = {}

    for document in documents:
        document_id = document["id"]
        asset_id = document["asset_id"]

        documents_by_id[document_id] = {
            "id": document_id,
            "title": document["title"],
            "version": document["version"],
            "status": document["status"],
            "effective_date": document["effective_date"],
            "source": document["source"],
        }

        if asset_id not in assets:
            assets[asset_id] = {
                "asset_id": asset_id,
                "documents": [],
                "relationships": [],
            }

        assets[asset_id]["documents"].append(document_id)

        # Extract explicit supersession relationship
        supersedes = document.get("supersedes")

        if supersedes:
            assets[asset_id]["relationships"].append({
                "from": document_id,
                "type": "supersedes",
                "to": supersedes,
            })

    return {
        "assets": assets,
        "documents": documents_by_id,
    }


def main():
    documents = load_documents()

    knowledge = compile_knowledge(documents)

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            knowledge,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print("=" * 70)
    print("KNOWLEDGE COMPILER")
    print("=" * 70)

    print(f"Documents: {len(documents)}")
    print(f"Assets: {len(knowledge['assets'])}")

    for asset_id, asset in knowledge["assets"].items():
        print()
        print(f"Asset: {asset_id}")
        print(f"Documents: {asset['documents']}")

        for relationship in asset["relationships"]:
            print(
                f"Relationship: "
                f"{relationship['from']} "
                f"--{relationship['type']}--> "
                f"{relationship['to']}"
            )

    print()
    print(f"Knowledge graph saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
