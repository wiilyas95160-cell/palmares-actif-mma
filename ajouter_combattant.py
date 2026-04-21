import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import json
import os

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'
}

def est_actif(url_adversaire):
    try:
        reponse = requests.get(url_adversaire, headers=HEADERS)
        soup = BeautifulSoup(reponse.text, 'html.parser')
        module_pro = soup.select_one('.fight_history')
        if not module_pro: return False
        lignes = module_pro.select('tr:not(.table_head)')
        if not lignes: return False
        
        # --- 1. Critère de TEMPS (A combattu dans la dernière année) ---
        date_texte = lignes[0].find('span', class_='sub_line').text
        annee_dernier_combat = int(date_texte.split('/')[-1].strip())
        annee_actuelle = datetime.now().year
        actif_recellement = (annee_actuelle - annee_dernier_combat) <= 1
        
        # --- 2. Critère d'ORGANISATION (STRICTEMENT UFC) ---
        evenement_tag = lignes[0].find_all('td')[2].find('a')
        if evenement_tag:
            nom_event = evenement_tag.text.upper()
            # On cherche UNIQUEMENT le mot "UFC"
            est_ufc = "UFC" in nom_event
        else:
            est_ufc = False
            
        return actif_recellement and est_ufc
        
    except Exception as e:
        return False
    
def calculer_palmares(url_cible):
    reponse = requests.get(url_cible, headers=HEADERS)
    soup = BeautifulSoup(reponse.text, 'html.parser')
    module_pro = soup.select_one('.fight_history')
    lignes_combats = module_pro.select('tr:not(.table_head)') if module_pro else []
    
    victoires, defaites, nuls, nc = 0, 0, 0, 0
    for ligne in lignes_combats:
        liens = ligne.find_all('a')
        if len(liens) > 0:
            lien_profil = "https://www.sherdog.com" + liens[0]['href']
            resultat = ligne.find('td').text.strip().lower()
            if est_actif(lien_profil):
                if "win" in resultat: victoires += 1
                elif "loss" in resultat: defaites += 1
                elif "draw" in resultat: nuls += 1
                elif "nc" in resultat: nc += 1
            time.sleep(0.2)
            
    return {"V": victoires, "D": defaites, "N": nuls, "NC": nc, "Total_Analyzes": len(lignes_combats)}

if __name__ == '__main__':
    print("===========================================")
    print(" 💉 AJOUT CHIRURGICAL D'UN COMBATTANT")
    print("===========================================")
    
    if not os.path.exists('database.json'):
        print("Erreur : Le fichier database.json est introuvable.")
        exit()

    with open('database.json', 'r', encoding='utf-8') as fichier:
        db = json.load(fichier)

    # 1. Collecte des informations
    nom = input("\n👉 1. Nom exact du combattant : ").strip()
    url = input("👉 2. Collez son URL Sherdog exacte : ").strip()
    
    print("\n👉 3. Choisissez la catégorie :")
    categories_dispos = list(db.keys())
    for i, cat in enumerate(categories_dispos):
        print(f"   [{i}] {cat}")
    
    choix_cat = int(input("Numéro de la catégorie : "))
    categorie_cible = categories_dispos[choix_cat]

    print("\n👉 4. À quel rang l'insérer ?")
    print("   (Tapez 0 pour Champion, 1 pour #1, 2 pour #2, etc.)")
    rang = int(input("Rang : "))

    # 2. Lancement du calcul
    print(f"\n📡 Calcul du palmarès actif pour {nom} en cours (Patientez ~30s)...")
    stats = calculer_palmares(url)
    
    fiche = {
        "Nom": nom,
        "Palmares_Actif": f"{stats['V']} V - {stats['D']} D",
        "Victoires_Actives": stats['V'],
        "Defaites_Actives": stats['D'],
        "Nuls_Actifs": stats['N'],
        "NC_Actifs": stats['NC'],
        "Total_Combats": stats['Total_Analyzes']
    }

    # 3. Insertion à la position exacte
    db[categorie_cible].insert(rang, fiche)

    # 4. Sauvegarde
    with open('database.json', 'w', encoding='utf-8') as fichier:
        json.dump(db, fichier, indent=4, ensure_ascii=False)
        
    print(f"\n✅ SUCCÈS ! {nom} a été inséré à la position #{rang} chez les {categorie_cible}.")
