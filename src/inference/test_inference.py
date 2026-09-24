import json
from pathlib import Path

from inference import (
    load_model,
    input_fn,
    output_fn,
    predict_fn,
)


def main():
    project_root = (
        Path(__file__)
        .resolve()
        .parents[2]
    )

    model_dir = project_root / "models"

    print("Loading model...")

    model = load_model(model_dir)

    print("Model loaded successfully.")

    # Simulate an API request.
    request = {
        "user_id": "user_0001",
        "k": 10,
    }

    request_body = json.dumps(request)

    print("\nRequest:")
    print(request_body)

    # Deserialize request.
    input_data = input_fn(
        request_body,
        "application/json",
    )

    # Generate recommendations.
    prediction = predict_fn(
        input_data,
        model,
    )

    # Serialize response.
    response_body, content_type = output_fn(
        prediction,
        "application/json",
    )

    print("\nResponse:")
    print(response_body)

    print(
        f"\nContent type: {content_type}"
    )


if __name__ == "__main__":
    main()