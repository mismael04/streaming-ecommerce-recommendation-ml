import json
import boto3


def test_recommendation_endpoint():
    endpoint_name = "recommendation-streaming-platform-dev-recommender"
    region = "us-east-1"

    # Initialize the SageMaker runtime client
    client = boto3.client("sagemaker-runtime", region_name=region)

    # Sample payload matching your inference schema
    payload = {
        "user_id": "user_0001",
        "k": 5
    }

    print(f"Invoking SageMaker endpoint: '{endpoint_name}'...")
    print(f"Sending payload: {json.dumps(payload, indent=2)}\n")

    try:
        response = client.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType="application/json",
            Accept="application/json",
            Body=json.dumps(payload)
        )

        result = json.loads(response["Body"].read().decode("utf-8"))
        
        print("Success! Response received from SageMaker:")
        print(json.dumps(result, indent=2))

    except Exception as e:
        print(f"Error invoking endpoint: {e}")


if __name__ == "__main__":
    test_recommendation_endpoint()