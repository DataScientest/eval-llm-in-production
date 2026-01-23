# src/extract_contact_info_correction.py
import requests
import json

def extract_contact_info(text):
    """Extract contact information using the local LLM API with structured output."""
    
    url = "http://localhost:8000/generate"
    
    # Define system prompt for role specification
    system_prompt = "Tu es un assistant spécialisé dans l'extraction précise de données. Extrais uniquement les informations demandées au format JSON spécifié."
    
    # Simplified prompt since JSON schema will enforce structure
    prompt = f"Extrais les informations de contact (nom, email, téléphone) du texte suivant: {text}"
    
    # Define JSON schema for structured output
    contact_schema = {
        "type": "json_schema",
        "json_schema": {
            "name": "contact_extraction",
            "schema": {
                "type": "object",
                "properties": {
                    "nom": {
                        "type": "string",
                        "description": "Le nom complet de la personne"
                    },
                    "email": {
                        "type": "string",
                        "description": "L'adresse email de la personne"
                    },
                    "telephone": {
                        "type": "string",
                        "description": "Le numéro de téléphone de la personne"
                    }
                },
                "required": ["nom", "email", "telephone"],
                "additionalProperties": False
            },
            "strict": True
        }
    }
    
    # Set parameters - low temperature for deterministic extraction
    payload = {
        "prompt": prompt,
        "system_prompt": system_prompt,
        "model": "groq-kimi-primary",
        "temperature": 0.1,  # Low temperature for consistent data extraction
        "max_tokens": 150,
        "response_format": contact_schema  # Enable structured output
    }
    
    # Make the API call
    response = requests.post(url, json=payload)
    response_data = response.json()
    
    # Parse the response string as JSON
    try:
        extracted_info = json.loads(response_data['response'])
        return extracted_info
    except json.JSONDecodeError:
        # Return a structured error if parsing fails
        return {"error": "Failed to parse response as JSON", "raw_response": response_data['response']}

if __name__ == "__main__":
    # Test with example text
    test_text = "Contactez notre chef de projet Marc Dubois au 06-12-34-56-78 ou marc.dubois@entreprise.com"
    result = extract_contact_info(test_text)
    
    print("Texte d'entrée:", test_text)
    print("\nRésultat de l'extraction:")
    print(json.dumps(result, indent=2))
    
    # Expected output:
    # {"nom": "Marc Dubois", "email": "marc.dubois@entreprise.com", "telephone": "06-12-34-56-78"}