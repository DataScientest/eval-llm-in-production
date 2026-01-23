# src/test_complex_extraction.py
from extract_contact_info_str_output import extract_contact_info
import json

def test_complex_cases():
    """Test structured output with more complex cases."""
    
    test_cases = [
        "Pour toute question, contactez Dr. Marie-Claire Dupont à m.dupont@hospital.fr ou au +33-1-42-86-75-30",
        "Jean-Baptiste de la Fontaine (jb.fontaine@company.org) - Tel: 07.89.12.34.56",
        "Mme Sophie MARTIN, responsable RH (sophie.martin@entreprise.com, 06 12 34 56 78)",
        "Contact: Pierre Durand - Email: pierre@startup.io - Mobile: 0612345678",
        "Appelez M. Alexandre Petit au numéro 01 23 45 67 89 ou écrivez à a.petit@corp.fr"
    ]
    
    print("=== Test d'extraction avec structured output ===\n")
    
    for i, test_text in enumerate(test_cases, 1):
        print(f"Test {i}:")
        print(f"Texte: {test_text}")
        
        try:
            result = extract_contact_info(test_text)
            print(f"Résultat: {json.dumps(result, indent=2, ensure_ascii=False)}")
            
            # Validate structure
            if isinstance(result, dict) and all(key in result for key in ["nom", "email", "telephone"]):
                print("✅ Structure valide")
            else:
                print("❌ Structure invalide")
                
        except Exception as e:
            print(f"❌ Erreur: {e}")
        
        print("-" * 50)

if __name__ == "__main__":
    test_complex_cases()
