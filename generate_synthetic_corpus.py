import csv
import json
import random
import shutil
from datetime import date, timedelta
from pathlib import Path


RANDOM_SEED = 481
ASSET_COUNT = 250

OUTPUT_DIR = Path("synthetic_source")
UNSTRUCTURED_DIR = OUTPUT_DIR / "unstructured"
STRUCTURED_DIR = OUTPUT_DIR / "structured"


SENSOR_MODELS = [
    "E17",
    "E21",
    "E24",
    "E31",
    "E42",
    "E55",
]

TEMPERATURE_SENSORS = [
    "T10",
    "T12",
    "T18",
    "T22",
    "T31",
]

PUMP_MODELS = [
    "AX-100",
    "AX-200",
    "BX-310",
    "CX-420",
    "DX-500",
]

LOCATIONS = [
    "North Plant",
    "South Plant",
    "East Plant",
    "West Plant",
    "Central Plant",
]

ACCESS_SCOPES = [
    "engineering",
    "field_service",
    "operations",
]

FAILURE_MODES = [
    "intermittent pressure readings",
    "pressure sensor communication loss",
    "high temperature warning",
    "unstable discharge pressure",
    "sensor calibration drift",
]

TROUBLESHOOTING_ACTIONS = [
    "inspect the sensor connector",
    "verify the cable continuity",
    "check the pressure line for blockage",
    "inspect the sensor mounting bracket",
    "verify the controller input signal",
]


def write_json(path, data):
    """Writes one JSON document with UTF-8 encoding."""
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def write_csv(path, rows, fieldnames):
    """Writes structured operational data to CSV."""
    with open(path, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(rows)


def make_asset_ids():
    """
    Keeps P-481 as a known demo asset and generates 249 more assets.

    Example:
    P-481
    P-1001
    P-1002
    ...
    """
    asset_ids = ["P-481"]

    for index in range(1, ASSET_COUNT):
        asset_ids.append(f"P-{1000 + index}")

    return asset_ids


def random_date(start_year, end_year):
    """Returns a deterministic random ISO date."""
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)

    delta_days = (end - start).days

    return (
        start + timedelta(
            days=random.randint(0, delta_days)
        )
    ).isoformat()


def build_assets(asset_ids):
    """Creates the Lakehouse assets table source."""
    rows = []

    for index, asset_id in enumerate(asset_ids, start=1):
        model = random.choice(PUMP_MODELS)
        location = random.choice(LOCATIONS)

        rows.append({
            "asset_id": asset_id,
            "asset_name": f"Industrial Pump {asset_id}",
            "asset_type": "pump",
            "model": model,
            "location": location,
            "commissioned_date": random_date(2018, 2024),
            "operational_status": random.choice([
                "active",
                "active",
                "active",
                "maintenance",
            ]),
            "owner_scope": random.choice(ACCESS_SCOPES),
        })

    return rows


def build_unstructured_documents(asset_ids):
    """
    Creates exactly 1,000 unstructured enterprise documents:

    - 250 superseded manuals;
    - 250 current service bulletins;
    - 250 troubleshooting notes;
    - 250 work instructions.

    The first two groups create authoritative document chains:
    old manual -> current service bulletin.
    """
    documents = []

    for index, asset_id in enumerate(asset_ids, start=1):
        old_sensor = random.choice(SENSOR_MODELS)

        new_sensor = random.choice(
            [
                sensor
                for sensor in SENSOR_MODELS
                if sensor != old_sensor
            ]
        )

        temperature_sensor = random.choice(
            TEMPERATURE_SENSORS
        )

        manual_id = f"doc-{asset_id.lower()}-manual-v1"
        bulletin_id = f"doc-sb-{1000 + index}"
        troubleshooting_id = (
            f"doc-{asset_id.lower()}-troubleshooting"
        )
        work_instruction_id = (
            f"doc-{asset_id.lower()}-work-instruction"
        )

        access_scope = random.choice(ACCESS_SCOPES)
        failure_mode = random.choice(FAILURE_MODES)
        action = random.choice(TROUBLESHOOTING_ACTIONS)

        # 1. Superseded manual
        manual = {
            "id": manual_id,
            "title": f"Pump {asset_id} Service Manual",
            "document_type": "service_manual",
            "version": "1.0",
            "effective_date": random_date(2022, 2024),
            "status": "superseded",
            "asset_id": asset_id,
            "supersedes": None,
            "source": f"{asset_id.lower()}_manual_v1.pdf",
            "page": random.randint(20, 120),
            "section": "Pressure Sensor Configuration",
            "access_scope": access_scope,
            "summary": (
                f"Legacy configuration manual for pump {asset_id}. "
                f"It specifies pressure sensor {old_sensor}."
            ),
            "text": (
                f"Pump {asset_id} uses pressure sensor {old_sensor}. "
                f"The temperature sensor is {temperature_sensor}. "
                f"This manual describes the legacy configuration."
            ),
        }

        # 2. Current bulletin superseding the old manual
        bulletin = {
            "id": bulletin_id,
            "title": f"Service Bulletin SB-{1000 + index}",
            "document_type": "service_bulletin",
            "version": "1.0",
            "effective_date": random_date(2025, 2026),
            "status": "current",
            "asset_id": asset_id,
            "supersedes": manual_id,
            "source": f"SB-{1000 + index}.pdf",
            "page": 1,
            "section": "Pressure Sensor Replacement",
            "access_scope": access_scope,
            "summary": (
                f"Current service bulletin for pump {asset_id}. "
                f"Pressure sensor {old_sensor} was replaced by "
                f"{new_sensor}. The bulletin supersedes the legacy manual."
            ),
            "text": (
                f"For pump {asset_id}, pressure sensor {old_sensor} "
                f"was replaced with pressure sensor {new_sensor}. "
                f"This bulletin supersedes document {manual_id}."
            ),
        }

        # 3. Troubleshooting note
        troubleshooting = {
            "id": troubleshooting_id,
            "title": f"Troubleshooting Note for Pump {asset_id}",
            "document_type": "troubleshooting_note",
            "version": "1.0",
            "effective_date": random_date(2025, 2026),
            "status": "current",
            "asset_id": asset_id,
            "supersedes": None,
            "source": f"{asset_id.lower()}_troubleshooting.md",
            "page": 1,
            "section": "Diagnostic Guidance",
            "access_scope": "field_service",
            "summary": (
                f"Troubleshooting guidance for {failure_mode} "
                f"on pump {asset_id}."
            ),
            "text": (
                f"If pump {asset_id} shows {failure_mode}, "
                f"{action}. Record the observation in the work order "
                f"before replacing any component."
            ),
        }

        # 4. Work instruction
        work_instruction = {
            "id": work_instruction_id,
            "title": (
                f"Work Instruction: Pressure Sensor Inspection "
                f"for {asset_id}"
            ),
            "document_type": "work_instruction",
            "version": "1.0",
            "effective_date": random_date(2025, 2026),
            "status": "current",
            "asset_id": asset_id,
            "supersedes": None,
            "source": f"{asset_id.lower()}_sensor_inspection.pdf",
            "page": 1,
            "section": "Inspection Procedure",
            "access_scope": "field_service",
            "summary": (
                f"Inspection procedure for the current pressure sensor "
                f"configuration of pump {asset_id}."
            ),
            "text": (
                f"Before inspecting the pressure sensor on pump {asset_id}, "
                f"isolate the equipment according to site safety procedure. "
                f"Inspect the connector, cable, and mounting bracket. "
                f"Document all findings in the work order."
            ),
        }

        documents.extend([
            manual,
            bulletin,
            troubleshooting,
            work_instruction,
        ])

    return documents


def build_maintenance_records(asset_ids):
    """
    Creates structured maintenance/service history.

    Four records per asset = 1,000 records.
    """
    rows = []

    for asset_id in asset_ids:
        for sequence in range(1, 5):
            event_type = random.choice([
                "inspection",
                "preventive_maintenance",
                "sensor_replacement",
                "calibration",
            ])

            rows.append({
                "record_id": (
                    f"maint-{asset_id.lower()}-{sequence:02d}"
                ),
                "asset_id": asset_id,
                "event_date": random_date(2024, 2026),
                "event_type": event_type,
                "technician_id": f"TECH-{random.randint(100, 199)}",
                "work_order_id": (
                    f"WO-{random.randint(10000, 99999)}"
                ),
                "outcome": random.choice([
                    "completed",
                    "completed",
                    "follow_up_required",
                ]),
                "notes": (
                    f"Synthetic {event_type} record for asset {asset_id}."
                ),
            })

    return rows


def build_work_orders(asset_ids):
    """
    Creates two structured work orders per asset = 500 rows.
    """
    rows = []

    for asset_id in asset_ids:
        for sequence in range(1, 3):
            rows.append({
                "work_order_id": (
                    f"WO-{asset_id.lower()}-{sequence:02d}"
                ),
                "asset_id": asset_id,
                "created_date": random_date(2024, 2026),
                "priority": random.choice([
                    "low",
                    "medium",
                    "high",
                ]),
                "status": random.choice([
                    "closed",
                    "closed",
                    "open",
                ]),
                "category": random.choice([
                    "inspection",
                    "sensor",
                    "pressure",
                    "preventive_maintenance",
                ]),
                "assigned_team": random.choice([
                    "field_service",
                    "maintenance",
                    "engineering",
                ]),
            })

    return rows


def build_incidents(asset_ids):
    """
    Creates one structured incident per asset = 250 rows.
    """
    rows = []

    for asset_id in asset_ids:
        rows.append({
            "incident_id": f"INC-{asset_id.lower()}",
            "asset_id": asset_id,
            "reported_date": random_date(2024, 2026),
            "severity": random.choice([
                "low",
                "medium",
                "high",
            ]),
            "failure_mode": random.choice(FAILURE_MODES),
            "resolution_status": random.choice([
                "resolved",
                "resolved",
                "under_review",
            ]),
            "reported_by_scope": random.choice(
                ACCESS_SCOPES
            ),
        })

    return rows


def main():
    random.seed(RANDOM_SEED)

    # Safe recreation: the generator owns only synthetic_source/.
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)

    UNSTRUCTURED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    STRUCTURED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    asset_ids = make_asset_ids()

    assets = build_assets(asset_ids)
    documents = build_unstructured_documents(asset_ids)
    maintenance_records = build_maintenance_records(
        asset_ids
    )
    work_orders = build_work_orders(asset_ids)
    incidents = build_incidents(asset_ids)

    # One JSON file per unstructured document.
    for document in documents:
        document_path = (
            UNSTRUCTURED_DIR / f"{document['id']}.json"
        )

        write_json(document_path, document)

    # Structured operational tables.
    write_csv(
        STRUCTURED_DIR / "assets.csv",
        assets,
        [
            "asset_id",
            "asset_name",
            "asset_type",
            "model",
            "location",
            "commissioned_date",
            "operational_status",
            "owner_scope",
        ],
    )

    write_csv(
        STRUCTURED_DIR / "maintenance_records.csv",
        maintenance_records,
        [
            "record_id",
            "asset_id",
            "event_date",
            "event_type",
            "technician_id",
            "work_order_id",
            "outcome",
            "notes",
        ],
    )

    write_csv(
        STRUCTURED_DIR / "work_orders.csv",
        work_orders,
        [
            "work_order_id",
            "asset_id",
            "created_date",
            "priority",
            "status",
            "category",
            "assigned_team",
        ],
    )

    write_csv(
        STRUCTURED_DIR / "incidents.csv",
        incidents,
        [
            "incident_id",
            "asset_id",
            "reported_date",
            "severity",
            "failure_mode",
            "resolution_status",
            "reported_by_scope",
        ],
    )

    manifest = {
        "generator": "generate_synthetic_corpus.py",
        "random_seed": RANDOM_SEED,
        "assets": len(assets),
        "unstructured_documents": len(documents),
        "structured_tables": {
            "assets": len(assets),
            "maintenance_records": len(
                maintenance_records
            ),
            "work_orders": len(work_orders),
            "incidents": len(incidents),
        },
        "unstructured_document_types": {
            "service_manual": ASSET_COUNT,
            "service_bulletin": ASSET_COUNT,
            "troubleshooting_note": ASSET_COUNT,
            "work_instruction": ASSET_COUNT,
        },
    }

    write_json(
        OUTPUT_DIR / "manifest.json",
        manifest,
    )

    print("=" * 70)
    print("SYNTHETIC AEGIS ENTERPRISE CORPUS CREATED")
    print("=" * 70)
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Assets: {len(assets)}")
    print(
        f"Unstructured documents: {len(documents)}"
    )
    print(
        f"Maintenance records: {len(maintenance_records)}"
    )
    print(f"Work orders: {len(work_orders)}")
    print(f"Incidents: {len(incidents)}")
    print()
    print("Unstructured source:")
    print(f"  {UNSTRUCTURED_DIR}")
    print("Structured source:")
    print(f"  {STRUCTURED_DIR}")
    print()
    print("Next step: create a local Lakehouse-style ingestion pipeline")
    print("that transforms these sources into normalized documents,")
    print("chunks, summaries, embeddings, and operational tables.")


if __name__ == "__main__":
    main()