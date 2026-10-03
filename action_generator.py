def generate_action(evidence):
    """
    Generate a technician action from confirmed evidence.

    No LLM is used here.
    Actions must be grounded in evidence.
    """

    actions = []

    for result in evidence.get("current", []):
        metadata = result["metadata"]
        text = result["text"]

        actions.append({
            "type": "VERIFY",
            "asset": metadata.get("asset_id"),
            "source": metadata.get("source"),
            "page": metadata.get("page"),
            "instruction": (
                f"Verify that the configuration described in "
                f"{metadata.get('title')} "
                f"(version {metadata.get('version')}) "
                f"matches the current asset."
            ),
        })

        actions.append({
            "type": "RECORD",
            "asset": metadata.get("asset_id"),
            "source": metadata.get("source"),
            "page": metadata.get("page"),
            "instruction": (
                f"Record the configuration described by the "
                f"current evidence: {text}"
            ),
        })

    return {
        "status": "READY",
        "actions": actions,
    }


def print_action(action):
    print()
    print("=" * 70)
    print("TECHNICIAN ACTION")
    print("=" * 70)

    print(f"Status: {action['status']}")

    for index, item in enumerate(
        action["actions"],
        start=1,
    ):
        print()
        print(f"{index}. [{item['type']}]")
        print(f"   Asset: {item['asset']}")
        print(f"   Instruction: {item['instruction']}")
        print(
            f"   Evidence: "
            f"{item['source']}, "
            f"page {item['page']}"
        )


if __name__ == "__main__":
    # Minimal standalone test
    evidence = {
        "current": [
            {
                "text": (
                    "Pump P-481 pressure sensor "
                    "was replaced. The new pressure "
                    "sensor is E21."
                ),
                "metadata": {
                    "asset_id": "P-481",
                    "title": "Service Bulletin SB-104",
                    "version": "1.0",
                    "source": "SB-104.pdf",
                    "page": 1,
                },
            }
        ]
    }

    action = generate_action(evidence)
    print_action(action)
