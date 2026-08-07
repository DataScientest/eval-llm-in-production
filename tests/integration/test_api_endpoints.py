import requests
import json

# Configuration
BASE_URL = "http://localhost:8000"

def print_response(response):
    """Helper function to print formatted JSON response."""
    print(f"Status Code: {response.status_code}")
    try:
        # Pretty-print the JSON response
        data = response.json()
        print(f"Response JSON: {json.dumps(data, indent=2)}")
        # Check for the new 'cost' field
        if 'cost' in data and data['cost'] is not None:
            print(f"LLM call cost: ${data['cost']:.6f}")
    except (json.JSONDecodeError, KeyError):
        print(f"Response Text: {response.text}")
    print("-" * 30)

def test_generate_smart_router():
    """Test the /generate endpoint with the default model."""
    print("--- Testing /generate with groq-kimi-primary ---")
    payload = {
        "prompt": "What is the capital of France? And what is the most famous monument?",
        "model": "groq-kimi-primary"  # Updated to use available model
    }
    try:
        response = requests.post(f"{BASE_URL}/generate", json=payload, timeout=60)
        print_response(response)
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        print("-" * 30)

def test_generate_specific_model():
    """Test the /generate endpoint with a specific model from the router."""
    print("--- Testing /generate with gemini-secondary model ---")
    payload = {
        "prompt": "Explain the theory of relativity in one simple sentence.",
        "model": "gemini-secondary"
    }
    try:
        response = requests.post(f"{BASE_URL}/generate", json=payload, timeout=60)
        print_response(response)
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        print("-" * 30)

def test_list_models():
    """Test the /models endpoint to see all available models."""
    print("--- Testing /models endpoint ---")
    try:
        response = requests.get(f"{BASE_URL}/models", timeout=30)
        print_response(response)
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        print("-" * 30)

if __name__ == "__main__":
    print("Starting API tests...")
    print("Please ensure Docker containers are running with 'docker-compose up -d'\n")
    test_generate_smart_router()
    test_generate_specific_model()
    test_list_models()
    print("API tests completed.")
    print("Check the MLflow UI at http://localhost:5000 to see the traced prompts.")
