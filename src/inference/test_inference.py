
import json
from pathlib import Path

from inference import model_fn, input_fn, predict_fn, output_fn


def main():
    # Resolve the project root and model artifacts directory.
    project_root = Path(__file__).resolve().parents[2]
    model_dir = project_root / "models"

    # Load the trained recommender model.
    artifact = model_fn(str(model_dir))

    # Simulate a SageMaker JSON request.
    request_body = json.dumps({
        "user_id": "user_0001",
        "k": 5
    }).encode("utf-8")

    # Parse the incoming request.
    input_data = input_fn(
        request_body,
        "application/json"
    )

    # Generate recommendations.
    prediction = predict_fn(input_data, artifact)

    # Format the response as JSON.
    response = output_fn(
        prediction,
        "application/json"
    )

    print("Inference test successful.")
    print("Response:")
    print(json.dumps(json.loads(response), indent=2))


if __name__ == "__main__":
    main()
