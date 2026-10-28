
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import boto3
from botocore.config import Config


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

STREAM_NAME = "recommendation-streaming-platform-dev-events"

TOTAL_EVENTS = 10_000_000
CHUNK_SIZE = 10_000
BATCH_SIZE = 100
MAX_WORKERS = 8

# Initial attempt plus up to this many retries.
MAX_RECORD_RETRIES = 10
RETRY_BASE_SECONDS = 0.25

NUM_USERS = 10_000
NUM_PRODUCTS = 75

CATEGORIES = [
    f"category_{index:02d}"
    for index in range(1, 11)
]

EVENT_TYPES = [
    "view",
    "add_to_cart",
    "remove_from_cart",
    "purchase",
]

EVENT_WEIGHTS = [0.70, 0.12, 0.05, 0.13]


# ---------------------------------------------------------
# Synthetic users and product catalog
# ---------------------------------------------------------

USERS = [
    f"user_{index:04d}"
    for index in range(1, NUM_USERS + 1)
]

PRODUCTS = []

for index in range(1, NUM_PRODUCTS + 1):
    category = CATEGORIES[(index - 1) % len(CATEGORIES)]

    PRODUCTS.append({
        "product_id": f"product_{index:04d}",
        "category": category,
        "price": round(random.uniform(10.0, 500.0), 2),
    })

PRODUCTS_BY_CATEGORY = {
    category: [
        product
        for product in PRODUCTS
        if product["category"] == category
    ]
    for category in CATEGORIES
}

# Give each user a preferred category to create
# a little structure in the synthetic interactions.
USER_PREFERENCES = {
    user_id: random.choice(CATEGORIES)
    for user_id in USERS
}


# ---------------------------------------------------------
# Kinesis client
# ---------------------------------------------------------

kinesis = boto3.client(
    "kinesis",
    config=Config(
        retries={
            "mode": "standard",
            "max_attempts": 10,
        },
        connect_timeout=10,
        read_timeout=60,
    ),
)


# ---------------------------------------------------------
# Generate one event
# ---------------------------------------------------------

def generate_event(rng):
    user_id = rng.choice(USERS)
    preferred_category = USER_PREFERENCES[user_id]

    # Most interactions use the user's preferred category.
    if rng.random() < 0.65:
        product = rng.choice(
            PRODUCTS_BY_CATEGORY[preferred_category]
        )
    else:
        product = rng.choice(PRODUCTS)

    event_time = (
        datetime.now(timezone.utc)
        - timedelta(
            seconds=rng.randint(0, 30 * 24 * 60 * 60)
        )
    )

    return {
        "user_id": user_id,
        "product_id": product["product_id"],
        "event_type": rng.choices(
            EVENT_TYPES,
            weights=EVENT_WEIGHTS,
            k=1,
        )[0],
        "category": product["category"],
        "price": product["price"],
        "timestamp": event_time.isoformat(
            timespec="seconds"
        ).replace("+00:00", "Z"),
    }


# ---------------------------------------------------------
# Convert an event into a Kinesis record
# ---------------------------------------------------------

def to_kinesis_record(event):
    return {
        "Data": json.dumps(
            event,
            separators=(",", ":"),
        ).encode("utf-8"),
        "PartitionKey": event["user_id"],
    }


# ---------------------------------------------------------
# Send one batch, retrying only failed records
# ---------------------------------------------------------

def send_batch(records):
    pending = records
    attempt = 0

    while pending:
        response = kinesis.put_records(
            StreamName=STREAM_NAME,
            Records=pending,
        )

        results = response.get("Records", [])

        if len(results) != len(pending):
            raise RuntimeError(
                "Kinesis returned a different number of "
                "results than records submitted."
            )

        failed_records = []
        failure_details = []

        for record, result in zip(pending, results):
            if result.get("ErrorCode"):
                failed_records.append(record)
                failure_details.append({
                    "code": result.get("ErrorCode"),
                    "message": result.get("ErrorMessage"),
                })

        if not failed_records:
            # All records in this batch were acknowledged.
            return len(records)

        if attempt >= MAX_RECORD_RETRIES:
            raise RuntimeError(
                f"Kinesis could not accept "
                f"{len(failed_records)} record(s) after "
                f"{MAX_RECORD_RETRIES} retries. "
                f"Example errors: {failure_details[:3]}"
            )

        attempt += 1
        pending = failed_records

        # Exponential backoff with a maximum delay.
        delay = min(
            RETRY_BASE_SECONDS * (2 ** (attempt - 1)),
            10.0,
        )

        # Add jitter so concurrent workers do not all retry
        # at precisely the same time.
        time.sleep(delay + random.uniform(0, delay * 0.25))

    return len(records)


# ---------------------------------------------------------
# Generate and send the complete dataset
# ---------------------------------------------------------

def main():
    rng = random.Random()

    print("Starting synthetic event ingestion.")
    print(f"Kinesis stream: {STREAM_NAME}")
    print(f"Target events: {TOTAL_EVENTS:,}")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"Concurrent workers: {MAX_WORKERS}")
    print()

    total_acknowledged = 0

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        for chunk_start in range(
            0,
            TOTAL_EVENTS,
            CHUNK_SIZE,
        ):
            chunk_count = min(
                CHUNK_SIZE,
                TOTAL_EVENTS - chunk_start,
            )

            events = [
                generate_event(rng)
                for _ in range(chunk_count)
            ]

            records = [
                to_kinesis_record(event)
                for event in events
            ]

            batches = [
                records[index:index + BATCH_SIZE]
                for index in range(
                    0,
                    len(records),
                    BATCH_SIZE,
                )
            ]

            futures = [
                executor.submit(send_batch, batch)
                for batch in batches
            ]

            chunk_acknowledged = 0

            for future in as_completed(futures):
                # Raises immediately if a batch exhausts retries.
                chunk_acknowledged += future.result()

            total_acknowledged += chunk_acknowledged

            print(
                f"Progress: {total_acknowledged:,} / "
                f"{TOTAL_EVENTS:,} records acknowledged "
                f"({total_acknowledged / TOTAL_EVENTS:.1%})"
            )

            if chunk_acknowledged != chunk_count:
                raise RuntimeError(
                    f"Chunk count mismatch: expected "
                    f"{chunk_count:,}, acknowledged "
                    f"{chunk_acknowledged:,}."
                )

    if total_acknowledged != TOTAL_EVENTS:
        raise RuntimeError(
            f"Ingestion incomplete: expected "
            f"{TOTAL_EVENTS:,}, acknowledged "
            f"{total_acknowledged:,}."
        )

    print()
    print("Producer finished successfully.")
    print(f"Records acknowledged by Kinesis: {total_acknowledged:,}")
    print(
        "Important: wait for Firehose to flush its remaining "
        "buffer before validating the final S3 count."
    )


if __name__ == "__main__":
    main()
