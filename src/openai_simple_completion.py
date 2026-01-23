import openai
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize OpenAI client
client = openai.OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

# Generate text using GPT-4o
def generate_with_gpt4o(prompt):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=500
    )
    return response.choices[0].message.content

# Example usage
if __name__ == "__main__":
    user_prompt = "Explain quantum computing in simple terms."
    result = generate_with_gpt4o(user_prompt)
    print(result)
