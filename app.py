from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import urllib.parse
import json
import os

app = Flask(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'
}

# --- FONCTIONS DE SCRAPING ---
def trouver_url_sherdog(recherche):
    if "sherdog.com/fighter" in recherche:
        return recherche
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

# --- ROUTES DU SITE ---

@app.route('/')
def home():
    base_de_donnees = {}
    if os.path.exists('database.json'):
        with open('database.json', 'r', encoding='utf-8') as fichier:
            base_de_donnees = json.load(fichier)
            
            # --- CALCUL DES STATISTIQUES À LA VOLÉE ---
            for categorie, combattants in base_de_donnees.items():
                for fighter in combattants:
                    # 1. Calcul du Taux de Victoire (Win Rate) Actif
                    total_actifs = fighter['Victoires_Actives'] + fighter['Defaites_Actives'] + fighter['Nuls_Actifs']
                    if total_actifs > 0:
                        taux = (fighter['Victoires_Actives'] / total_actifs) * 100
                        fighter['Taux_Victoire'] = round(taux, 1) # Arrondi à 1 chiffre après la virgule
                    else:
                        fighter['Taux_Victoire'] = 0.0

                    # 2. Calcul des Combats "Obsolètes" (Vétéran vs Prospect)
                    # On prend le total de sa carrière moins les combats contre des actifs
                    combats_inactifs = fighter['Total_Combats'] - (total_actifs + fighter['NC_Actifs'])
                    # On s'assure de ne pas avoir de nombre négatif en cas de bug de Sherdog
                    fighter['Combats_Inactifs'] = max(0, combats_inactifs) 

    return render_template('index.html', db=base_de_donnees)

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    recherche_utilisateur = data.get('url')

    if not recherche_utilisateur:
        return jsonify({'error': 'Veuillez entrer un nom ou une URL.'})

    recherche_lower = recherche_utilisateur.lower().strip()

    # --- ÉTAPE 1 : VÉRIFIER DANS LE CACHE (Instantané) ---
    if os.path.exists('database.json'):
        with open('database.json', 'r', encoding='utf-8') as fichier:
            db = json.load(fichier)
            # On fouille dans toutes les catégories
            for categorie, combattants in db.items():
                for fighter in combattants:
                    # Si le nom correspond, on renvoie tout de suite !
                    if recherche_lower in fighter['Nom'].lower():
                        return jsonify({
                            'name': fighter['Nom'] + " (Chargé instantanément ⚡)",
                            'total_fights': fighter['Total_Combats'],
                            'wins': fighter['Victoires_Actives'],
                            'losses': fighter['Defaites_Actives'],
                            'draws': fighter['Nuls_Actifs'],
                            'nc': fighter['NC_Actifs']
                        })

    # --- ÉTAPE 2 : SI NON TROUVÉ, ON LANCE LE SCRAPING (Prend du temps) ---
    url_cible = trouver_url_sherdog(recherche_utilisateur)
    
    if not url_cible:
        return jsonify({'error': f'Aucun combattant trouvé pour : "{recherche_utilisateur}"'})

    reponse = requests.get(url_cible, headers=HEADERS)
    if reponse.status_code != 200:
        return jsonify({'error': 'Impossible de lire la page du combattant.'})

    soup = BeautifulSoup(reponse.text, 'html.parser')
    nom_cible = soup.find('span', class_='fn').text
    
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

    return jsonify({
        'name': nom_cible,
        'total_fights': len(lignes_combats),
        'wins': victoires,
        'losses': defaites,
        'draws': nuls,
        'nc': nc
    })

if __name__ == '__main__':
    app.run(debug=True)