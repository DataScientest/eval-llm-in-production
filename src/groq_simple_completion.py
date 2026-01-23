import os
import requests
from dotenv import load_dotenv

load_dotenv()

def generate_with_groq(prompt, model="llama3-8b-8192"):
    """Generate text using Groq models.
    
    Args:
        prompt (str): The input prompt for text generation
        model (str): Groq model name (default: llama3-8b-8192)
    
    Returns:
        str: Generated text response
    """
    headers = {
        "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 500
    }

    url = "https://api.groq.com/openai/v1/chat/completions"
    
    response = requests.post(
        url,
        headers=headers,
        json=payload
    )
    
    response_json = response.json()
    return response_json["choices"][0]["message"]["content"]

# Example usage
if __name__ == "__main__":
    user_prompt = "Explain quantum computing in simple terms."
    result = generate_with_groq(user_prompt, model="moonshotai/kimi-k2-instruct")
    print(result)
