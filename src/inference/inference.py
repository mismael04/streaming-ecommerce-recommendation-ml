import json
from pathlib import Path

import joblib
import numpy as np


def model_fn(model_dir):
    """
    SageMaker model loading hook. 
    Loads the recommendation artifacts from disk.
    """
    model_path = Path(model_dir) / "recommender.joblib"
    
    print(f"Loading model from: {model_path}", flush=True)

    if not model_path.exists():
        raise FileNotFoundError(f"Model artifact not found at: {model_path}")

    artifact = joblib.load(model_path)
    print("Model artifact loaded successfully.", flush=True)

    return artifact


def generate_recommendations(user_id, artifact, k=10):
    user_to_index = artifact["user_to_index"]
    product_to_index = artifact["product_to_index"]
    products = artifact["products"]
    user_factors = artifact["user_factors"]
    components = artifact["components"]
    seen_products = artifact["seen_products"]

    if user_id not in user_to_index:
        return []

    user_index = user_to_index[user_id]

    # Reconstruct user-product preference scores via matrix multiplication
    scores = user_factors[user_index] @ components
    scores = scores.copy()

    for product_id in seen_products.get(user_id, set()):
        product_index = product_to_index.get(product_id)
        if product_index is not None:
            scores[product_index] = -np.inf

    top_indices = np.argsort(scores)[::-1][:k]

    recommendations = []
    for index in top_indices:
        recommendations.append({
            "product_id": products[index],
            "score": round(float(scores[index]), 4),
        })

    return recommendations


def input_fn(request_body, request_content_type):
    if request_content_type != "application/json":
        raise ValueError(f"Unsupported content type: {request_content_type}")

    if isinstance(request_body, bytes):
        request_body = request_body.decode("utf-8")

    data = json.loads(request_body)

    if "user_id" not in data:
        raise ValueError("Request must contain 'user_id'.")

    return data


def predict_fn(input_data, model):
    user_id = input_data["user_id"]
    k = int(input_data.get("k", 10))
    k = max(1, min(k, 50))

    recommendations = generate_recommendations(
        user_id=user_id,
        artifact=model,
        k=k,
    )

    return {
        "user_id": user_id,
        "recommendations": recommendations,
    }


def output_fn(prediction, accept):
    if accept != "application/json":
        raise ValueError(f"Unsupported accept type: {accept}")

    return json.dumps(prediction), "application/json"