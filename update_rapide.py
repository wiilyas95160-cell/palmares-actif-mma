import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import urllib.parse
import json
import os

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'
}

# --- LES EXCEPTIONS ---
URL_EXCEPTIONS = {
    "Charles Oliveira": "https://www.sherdog.com/fighter/Charles-Oliveira-30300",
    "Benoît Saint Denis": "https://www.sherdog.com/fighter/Benoit-St-Denis-317103",
    "Khamzat Chimaev": "https://www.sherdog.com/fighter/Khamzat-Chimaev-280021"
}

def trouver_url_sherdog(recherche):
    nom_encode = urllib.parse.quote_plus(recherche)
    url_recherche = f"https://www.sherdog.com/stats/fightfinder?SearchTxt={nom_encode}"
    reponse = requests.get(url_recherche, headers=HEADERS)
    if reponse.status_code == 200:
        soup = BeautifulSoup(reponse.text, 'html.parser')
        liens = soup.select('td a[href^="/fighter/"]')
        for lien in liens:
            if "-" in lien['href'] and lien.text.strip():
                return "https://www.sherdog.com" + lien['href']
    return None

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
    print("⚡ BIENVENUE DANS LA MISE À JOUR EXPRESS ⚡")
    
    if not os.path.exists('database.json'):
        print("Erreur : Le fichier database.json est introuvable.")
        exit()

    with open('database.json', 'r', encoding='utf-8') as fichier:
        db = json.load(fichier)

    nom_cible = input("\n👉 Entrez le nom exact du combattant à mettre à jour (ex: Islam Makhachev) : ").strip()

    categorie_trouvee = None
    index_combattant = -1

    for cat_name, combattants in db.items():
        for i, fighter in enumerate(combattants):
            if fighter['Nom'].lower() == nom_cible.lower():
                categorie_trouvee = cat_name
                index_combattant = i
                vrai_nom = fighter['Nom']
                break
        if categorie_trouvee:
            break

    if not categorie_trouvee:
        print(f"❌ Impossible de trouver '{nom_cible}' dans ton classement actuel.")
        exit()

    print(f"\n✅ {vrai_nom} trouvé dans la catégorie '{categorie_trouvee}'.")
    print(f"📡 Analyse du nouveau palmarès actif en cours (patientez ~30s)...")
    
    if vrai_nom in URL_EXCEPTIONS:
        url = URL_EXCEPTIONS[vrai_nom]
    else:
        url = trouver_url_sherdog(vrai_nom)

    if url:
        stats = calculer_palmares(url)
        
        db[categorie_trouvee][index_combattant] = {
            "Nom": vrai_nom,
            "Palmares_Actif": f"{stats['V']} V - {stats['D']} D",
            "Victoires_Actives": stats['V'],
            "Defaites_Actives": stats['D'],
            "Nuls_Actifs": stats['N'],
            "NC_Actifs": stats['NC'],
            "Total_Combats": stats['Total_Analyzes']
        }
        print(f"--> Nouveau palmarès actif calculé : {stats['V']} V - {stats['D']} D")
        
        with open('database.json', 'w', encoding='utf-8') as fichier:
            json.dump(db, fichier, indent=4, ensure_ascii=False)
            
        print(f"\n💾 MISE À JOUR TERMINÉE ! Ton fichier database.json est prêt à être envoyé sur GitHub.")
    else:
        print(f"❌ [ERREUR] Impossible de trouver l'URL pour {vrai_nom}.")