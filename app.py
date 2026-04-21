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
        
    def requete_sherdog(texte_recherche):
        nom_encode = urllib.parse.quote_plus(texte_recherche)
        url_recherche = f"https://www.sherdog.com/stats/fightfinder?SearchTxt={nom_encode}"
        reponse = requests.get(url_recherche, headers=HEADERS)
        
        if reponse.status_code != 200:
            return None
            
        soup = BeautifulSoup(reponse.text, 'html.parser')
        # On cible le tableau des résultats de recherche
        lignes = soup.select('table.fightfinder_result tr:not(.table_head)')
        
        meilleur_lien = None
        max_combats = -1
        
        for ligne in lignes:
            colonnes = ligne.find_all('td')
            # Sherdog a 9 colonnes dans son tableau de résultats
            if len(colonnes) >= 7:
                lien_tag = colonnes[1].find('a')
                if lien_tag and '/fighter/' in lien_tag['href']:
                    try:
                        # Sur Sherdog, Win est à la colonne 5 et Loss à la 6
                        victoires = int(colonnes[5].text)
                        defaites = int(colonnes[6].text)
                        total_combats = victoires + defaites
                    except:
                        total_combats = 0
                        
                    # On garde le combattant avec le plus gros palmarès (le vrai pro)
                    if total_combats > max_combats:
                        max_combats = total_combats
                        meilleur_lien = "https://www.sherdog.com" + lien_tag['href']
                        
        # Sécurité : Si l'analyse du tableau échoue, on prend le premier lien dispo
        if not meilleur_lien:
            premier_lien = soup.select_one('td a[href^="/fighter/"]')
            if premier_lien:
                meilleur_lien = "https://www.sherdog.com" + premier_lien['href']
                
        return meilleur_lien

    # 1. On tente la recherche exacte tapée par l'utilisateur
    resultat = requete_sherdog(recherche)
    
    # 2. Si rien n'est trouvé (ex: "cyril gane"), on tente avec juste le dernier mot ("gane")
    if not resultat:
        mots = recherche.split()
        if len(mots) > 1:
            resultat = requete_sherdog(mots[-1]) # On cherche uniquement le nom de famille
            
    return resultat

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

# --- ROUTES DU SITE ---

@app.route('/')
def home():
    base_de_donnees = {}
    indices_competitivite = {}
    
    if os.path.exists('database.json'):
        with open('database.json', 'r', encoding='utf-8') as fichier:
            base_de_donnees = json.load(fichier)
            
            for categorie, combattants in base_de_donnees.items():
                total_winrate = 0
                count = 0
                for fighter in combattants:
                    # Calcul Winrate (déjà présent)
                    total_actifs = fighter['Victoires_Actives'] + fighter['Defaites_Actives'] + fighter['Nuls_Actifs']
                    taux = (fighter['Victoires_Actives'] / total_actifs * 100) if total_actifs > 0 else 0
                    fighter['Taux_Victoire'] = round(taux, 1)
                    
                    # Calcul Combats Obsolètes (déjà présent)
                    fighter['Combats_Inactifs'] = max(0, fighter['Total_Combats'] - (total_actifs + fighter['NC_Actifs']))
                    
                    total_winrate += taux
                    count += 1
                
                # Calcul de l'indice de la catégorie
                indices_competitivite[categorie] = round(total_winrate / count, 1) if count > 0 else 0

    return render_template('index.html', db=base_de_donnees, indices=indices_competitivite)

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
                            'name': fighter['Nom'],
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