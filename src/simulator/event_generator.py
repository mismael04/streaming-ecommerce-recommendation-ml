import json
import random
import time
from datetime import datetime, timezone

import boto3

REGION = "us-east-1"
STREAM_NAME = "recommendation-streaming-platform-dev-events"

NUM_USERS = 3_000
NUM_EVENTS = 80_000

# Keep batches below the maximum PutRecords batch size and
# throttle the producer so one Kinesis shard is not overwhelmed.
BATCH_SIZE = 100
BATCH_DELAY_SECONDS = 0.25

USERS = [f"user_{i:04d}" for i in range(1, NUM_USERS + 1)]

CATEGORIES = [
    "headphones",
    "speakers",
    "laptops",
    "phones",
    "gaming",
    "books",
    "tablets",
    "cameras",
    "smart_home",
    "accessories",
]

BASE_PRICES = {
    "headphones": 149.99,
    "speakers": 129.99,
    "laptops": 999.99,
    "phones": 799.99,
    "gaming": 199.99,
    "books": 24.99,
    "tablets": 399.99,
    "cameras": 699.99,
    "smart_home": 99.99,
    "accessories": 49.99,
}

PRODUCTS = []

for i in range(1, 76):
    category = CATEGORIES[(i - 1) % len(CATEGORIES)]

    price = BASE_PRICES[category] * random.uniform(0.7, 1.4)

    PRODUCTS.append(
        {
            "id": f"product_{i:03d}",
            "category": category,
            "price": round(price, 2),
        }
    )

# Give each user two preferred categories.
# These preferences are intentionally hidden from the generated
# events. The model should eventually infer them from user behavior.
USER_PREFERENCES = {
    user: random.sample(CATEGORIES, 2)
    for user in USERS
}

EVENT_TYPES = [
    "view",
    "view",
    "view",
    "view",
    "add_to_cart",
    "add_to_cart",
    "purchase",
]

kinesis = boto3.client("kinesis", region_name=REGION)


def choose_product(user_id):
    """
    Select a product based on the user's hidden preferences.

    Approximately 80% of interactions come from preferred
    categories, while 20% come from any category.
    """
    preferred_categories = USER_PREFERENCES[user_id]

    if random.random() < 0.80:
        category = random.choice(preferred_categories)

        category_products = [
            product
            for product in PRODUCTS
            if product["category"] == category
        ]

        return random.choice(category_products)

    return random.choice(PRODUCTS)


def generate_event():
    """Generate a single synthetic user interaction."""

    user = random.choice(USERS)
    product = choose_product(user)
    event_type = random.choice(EVENT_TYPES)

    return {
        "event_id": f"{user}_{random.getrandbits(64)}",
        "user_id": user,
        "product_id": product["id"],
        "category": product["category"],
        "event_type": event_type,
        "price": product["price"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def send_batch(events):
    """
    Send a batch of events to Kinesis.

    Kinesis PutRecords can partially fail, so only failed records
    are retried. Exponential backoff helps when the shard is
    temporarily throttling the producer.
    """

    retry_records = [
        {
            "Data": (json.dumps(event) + "\n").encode("utf-8"),
            "PartitionKey": event["user_id"],
        }
        for event in events
    ]

    max_retries = 6

    for attempt in range(max_retries + 1):
        response = kinesis.put_records(
            StreamName=STREAM_NAME,
            Records=retry_records,
        )

        failed_count = response["FailedRecordCount"]

        if failed_count == 0:
            return

        retry_records = [
            record
            for record, result in zip(
                retry_records,
                response["Records"],
            )
            if "ErrorCode" in result
        ]

        if attempt == max_retries:
            raise RuntimeError(
                f"{len(retry_records)} records failed after "
                f"{max_retries} retries."
            )

        delay = min(2**attempt, 10)

        print(
            f"Warning: {failed_count} records throttled. "
            f"Retrying in {delay}s..."
        )

        time.sleep(delay)


def main():
    print(
        f"Generating {NUM_EVENTS:,} additional events "
        f"for {NUM_USERS:,} users..."
    )
    print(f"Batch size: {BATCH_SIZE}")
    print(f"Batch delay: {BATCH_DELAY_SECONDS}s")
    print(f"Products: {len(PRODUCTS)}")
    print(f"Categories: {len(CATEGORIES)}")
    print("Starting Kinesis ingestion...")

    batch = []

    for i in range(NUM_EVENTS):
        event = generate_event()
        batch.append(event)

        if len(batch) == BATCH_SIZE:
            send_batch(batch)
            batch.clear()

            # Keep the producer below the sustained write capacity
            # of the single Kinesis shard.
            time.sleep(BATCH_DELAY_SECONDS)

        if (i + 1) % 5_000 == 0:
            print(
                f"Sent {i + 1:,}/{NUM_EVENTS:,} "
                f"additional events"
            )

    # Send any remaining events.
    if batch:
        send_batch(batch)

    print("Additional event generation complete.")


if __name__ == "__main__":
    main()