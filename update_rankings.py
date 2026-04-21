import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import urllib.parse
import json

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'
}

# --- LES EXCEPTIONS POUR LES HOMONYMES ---
# Si un combattant bug (0-0), ajoute son vrai lien Sherdog ici.
URL_EXCEPTIONS = {
    "Charles Oliveira": "https://www.sherdog.com/fighter/Charles-Oliveira-30300"
    "Benoît Saint Denis": "https://www.sherdog.com/fighter/Benoit-Saint-Denis-306915",
}

# --- TES CLASSEMENTS OFFICIELS ACTUALISÉS ---
CATEGORIES = {
    "Poids Légers": [
        "Ilia Topuria", "Justin Gaethje", "Arman Tsarukyan", "Charles Oliveira", 
        "Max Holloway", "Benoît Saint Denis", "Paddy Pimblett", "Mateusz Gamrot", 
        "Dan Hooker", "Renato Moicano", "Mauricio Ruffy"
    ],
    "Poids Mi-Moyens": [
        "Islam Makhachev", "Jack Della Maddalena", "Ian Machado Garry", "Michael Morales", 
        "Belal Muhammad", "Carlos Prates", "Sean Brady", "Kamaru Usman", 
        "Leon Edwards", "Joaquin Buckley", "Gabriel Bonfim"
    ],
    "Poids Moyens": [
        "Khamzat Chimaev", "Dricus Du Plessis", "Nassourdine Imavov", "Sean Strickland", 
        "Brendan Allen", "Caio Borralho", "Joe Pyfer", "Anthony Hernandez", 
        "Reinier de Ridder", "Israel Adesanya", "Robert Whittaker"
    ]
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
        date_texte = lignes[0].find('span', class_='sub_line').text
        annee_dernier_combat = int(date_texte.split('/')[-1].strip())
        annee_actuelle = datetime.now().year
        return (annee_actuelle - annee_dernier_combat) <= 1
    except:
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
    print("DÉMARRAGE DE LA MISE À JOUR GÉNÉRALE (Cela va prendre 10 à 15 minutes)...")
    all_data = {}

    for cat_name, liste_combattants in CATEGORIES.items():
        print(f"\n========================================")
        print(f" SCRAPING DE LA CATÉGORIE : {cat_name.upper()}")
        print(f"========================================")
        
        cat_results = []
        
        for nom in liste_combattants:
            print(f"\nRecherche de {nom}...", end=" ")
            
            # --- CORRECTION : Vérification du dictionnaire d'exceptions ---
            if nom in URL_EXCEPTIONS:
                url = URL_EXCEPTIONS[nom]
                print("[Exception URL utilisée]")
            else:
                url = trouver_url_sherdog(nom)
                if url:
                    print("[Trouvé]")
            
            if url:
                print(f"Calcul en cours pour {nom}...")
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
                cat_results.append(fiche)
                print(f"--> Terminé : {fiche['Palmares_Actif']}")
            else:
                print(f"[ERREUR] Impossible de trouver l'URL pour {nom}.")
                
        # --- CORRECTION : Suppression de la ligne de tri ---
        # Le classement respectera maintenant exactement l'ordre de la liste CATEGORIES
        all_data[cat_name] = cat_results

    # Sauvegarde
    print("\nSauvegarde dans la base de données (database.json)...")
    with open('database.json', 'w', encoding='utf-8') as fichier:
        json.dump(all_data, fichier, indent=4, ensure_ascii=False)
        
    print("✅ MISE À JOUR TERMINÉE ! La base de données est corrigée.")