import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time

# --- PARAMÈTRES ---
url_cible = "https://www.sherdog.com/fighter/Ciryl-Gane-293973"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'
}

# --- FONCTION : VÉRIFIER L'ACTIVITÉ ---
def est_actif(url_adversaire):
    """Visite le profil de l'adversaire et renvoie True s'il a combattu récemment."""
    try:
        reponse = requests.get(url_adversaire, headers=headers)
        soup = BeautifulSoup(reponse.text, 'html.parser')
        
        lignes = soup.select('.fight_history tr:not(.table_head)')
        if not lignes:
            return False
        
        date_texte = lignes[0].find('span', class_='sub_line').text
        annee_dernier_combat = int(date_texte.split('/')[-1].strip())
        annee_actuelle = datetime.now().year
        
        if (annee_actuelle - annee_dernier_combat) <= 1:
            return True
        else:
            return False
    except:
        return False

# --- SCRIPT PRINCIPAL ---
print("==================================================")
print("     CALCULATEUR DE PALMARÈS ACTIF (INTÉGRAL)     ")
print("==================================================")
print("Connexion à la page principale en cours...")

reponse = requests.get(url_cible, headers=headers)

if reponse.status_code == 200:
    soup = BeautifulSoup(reponse.text, 'html.parser')
    nom_cible = soup.find('span', class_='fn').text
    
    # On récupère toutes les lignes de combats
    lignes_combats = soup.select('.fight_history tr:not(.table_head)')
    total_combats = len(lignes_combats)
    
    print(f"\nAnalyse de la carrière complète de {nom_cible} ({total_combats} combats trouvés)...")
    print("Veuillez patienter pendant le scan des adversaires...\n")
    
    victoires_actives = 0
    defaites_actives = 0
    nuls_actifs = 0
    nc_actifs = 0
    
    combats_scannes = 0
    
    for ligne in lignes_combats:
        liens = ligne.find_all('a')
        
        if len(liens) > 0:
            combats_scannes += 1
            nom_adversaire = liens[0].text
            lien_profil = "https://www.sherdog.com" + liens[0]['href']
            resultat = ligne.find('td').text.strip().lower()
            
            # Affichage de la progression
            print(f"[{combats_scannes}/{total_combats}] Scan de {nom_adversaire}...", end=" ")
            
            if est_actif(lien_profil):
                print("[ACTIF]")
                if "win" in resultat:
                    victoires_actives += 1
                elif "loss" in resultat:
                    defaites_actives += 1
                elif "draw" in resultat:
                    nuls_actifs += 1
                elif "nc" in resultat:
                    nc_actifs += 1
            else:
                print("[Retraité/Inactif]")
            
            # Pause de sécurité pour ne pas spammer le serveur de Sherdog
            time.sleep(0.2)

    # --- RÉSULTAT FINAL ---
    print("\n" + "="*50)
    print(f" RÉSULTAT POUR {nom_cible.upper()}")
    print("="*50)
    print(f"Palmarès contre des combattants ENCORE ACTIFS :")
    print(f"*** {victoires_actives} V - {defaites_actives} D - {nuls_actifs} N ({nc_actifs} NC) ***")
    print("==================================================")

else:
    print(f"Erreur de connexion : {reponse.status_code}")