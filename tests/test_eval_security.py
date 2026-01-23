import requests
import json
import time

print("🔒 ÉVALUATION AUTOMATIQUE DE SÉCURITÉ")
print("=" * 50)

# Test 1: Récupérer les métriques
response = requests.get('http://localhost:8000/security-metrics')
metrics = response.json()
overview = metrics['overview']

print(f"📊 MÉTRIQUES GLOBALES:")
print(f"  Total requêtes: {overview['total_requests']}")
print(f"  Requêtes bloquées: {overview['blocked_requests']}")
print(f"  Taux de blocage: {overview['block_rate_percent']:.1f}%")
print(f"  Requêtes/minute: {overview['requests_per_minute']:.1f}")

# Test 2: Analyser les incidents
incidents_response = requests.get('http://localhost:8000/security-incidents')
incidents_data = incidents_response.json()
incidents = incidents_data['incidents']

attack_types = {}
for incident in incidents[-20:]:  # Derniers 20 incidents
    attack_type = incident['type']
    attack_types[attack_type] = attack_types.get(attack_type, 0) + 1

print(f"\n🚨 TYPES D'ATTAQUES DÉTECTÉES:")
for attack_type, count in attack_types.items():
    print(f"  {attack_type}: {count} incidents")

# Test 3: Calcul du score de sécurité
block_rate = overview['block_rate_percent']
total_requests = overview['total_requests']

# Critères de scoring
if total_requests > 100:  # Échantillon suffisant
    if block_rate >= 90:
        security_score = "🟢 EXCELLENT"
        production_ready = True
    elif block_rate >= 75:
        security_score = "🟡 CORRECT"  
        production_ready = True
    elif block_rate >= 50:
        security_score = "🟠 MOYEN"
        production_ready = False
    else:
        security_score = "🔴 INSUFFISANT"
        production_ready = False
else:
    security_score = "⏳ ÉCHANTILLON INSUFFISANT"
    production_ready = False

print(f"\n🎯 ÉVALUATION FINALE:")
print(f"  Score de sécurité: {security_score}")
print(f"  Production ready: {'✅ OUI' if production_ready else '❌ NON'}")

# Test 4: Recommandations
print(f"\n📋 RECOMMANDATIONS:")
if overview['block_rate_percent'] < 5:
    print("  ⚠️  Taux de blocage faible - vérifier les patterns de détection")
if 'malicious_prompt' in attack_types:
    print(f"  🛡️  {attack_types['malicious_prompt']} injections détectées - patterns efficaces")
if overview['requests_per_minute'] > 50:
    print("  ⚡ Charge élevée - surveiller la performance")

print(f"\n💡 POINTS D'AMÉLIORATION:")
print(f"  • Ajouter patterns multilingues (injection française partiellement passée)")
print(f"  • Considérer Lakera Guard Pro pour détection IA avancée")
print(f"  • Implémenter alertes temps réel pour incidents critiques")