# Étape 1 : Importer les bibliothèques dont on a besoin
import os
import requests
from bs4 import BeautifulSoup
import time
import random
import re
from supabase import create_client, Client 

# Étape 2 : Configurer nos variables
DEALABS_URL = "https://www.dealabs.com/hot"

# Configuration des secrets via variables d'environnement
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "https://discordapp.com/api/webhooks/1406262114183807146/BHrmH-9KbJfd-e6bHz9ScTnS7VuwL7NDnlArqWxoE86IO4RGiArnT9oOy5v0Mu4WPq2x")
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://onfdyanegbttxrmhdyqp.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9uZmR5YW5lZ2J0dHhybWhkeXFwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTUzNTg3NjEsImV4cCI6MjA3MDkzNDc2MX0.X7zwaCcCH0CVaSxrfAhDlk56NtcoQiN2R9PnmP7Oq9s")

# PARAMÈTRES DE FILTRAGE
TEMPERATURE_MINIMUM = 100  # Température minimum pour traiter un deal
TEMPERATURE_PREMIUM = 500  # Température pour les deals "premium"
TEMPERATURE_HOT = 1000     # Température pour les deals "très hot"

# PARAMÈTRES D'AFFILIATION
AMAZON_TAG = "dealbot00-21"  # Remplacez par votre vrai tag Amazon

# Headers pour éviter la détection anti-bot
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Referer': 'https://www.google.com/'
}

def scraper_dealabs():
    """
    Trouve et retourne le premier deal valide de Dealabs
    """
    print("🔍 Tentative de scraping de Dealabs...")
    
    try:
        time.sleep(random.uniform(1, 3))  # Délai aléatoire
        
        session = requests.Session()
        session.headers.update(HEADERS)
        
        response = session.get(DEALABS_URL, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Sélecteurs CSS pour trouver les deals
        selectors_to_try = [
            'article[class*="thread"]',
            'div[class*="thread"]',
            'article[data-thread-id]',
            'div[data-thread-id]',
            'article.thread--card',
            'article'
        ]
        
        all_deals = []
        for selector in selectors_to_try:
            all_deals = soup.select(selector)
            if all_deals:
                print(f"✅ Trouvé {len(all_deals)} éléments avec le sélecteur: {selector}")
                break
        
        if not all_deals:
            print("❌ Aucun élément trouvé")
            return None, None, 0
        
        # Analyser chaque deal
        for i, deal_element in enumerate(all_deals[:20]):
            print(f"🔍 Analyse de l'élément {i+1}...")
            
            # ÉTAPE 1 : Extraire la température
            temperature = extraire_temperature(deal_element)
            print(f"🌡️ Température détectée : {temperature}°")
            
            # Filtrer par température
            if temperature < TEMPERATURE_MINIMUM:
                print(f"❄️ Deal ignoré (température {temperature}° < {TEMPERATURE_MINIMUM}°)")
                continue
            
            # ÉTAPE 2 : Extraire le lien du deal
            link_selectors = [
                'a[class*="thread-link"]',
                'a[href*="/deals/"]', 
                'a[href*="/bons-plans/"]',
                'a[title]',
                'a'
            ]
            
            link_tag = None
            for link_selector in link_selectors:
                link_tag = deal_element.select_one(link_selector)
                if link_tag and 'href' in link_tag.attrs:
                    break
            
            if not link_tag:
                print("❌ Aucun lien trouvé")
                continue
            
            # ÉTAPE 3 : Extraire le titre
            title_selectors = ['strong', 'h1', 'h2', 'h3', '[class*="title"]', 'span']
            
            title_text = None
            for title_selector in title_selectors:
                title_element = link_tag.select_one(title_selector)
                if title_element:
                    title_text = title_element.get_text(strip=True)
                    if title_text and len(title_text) > 10:
                        break
            
            # Fallback pour le titre
            if not title_text:
                title_text = link_tag.get('title', '').strip()
                if not title_text:
                    title_text = link_tag.get_text(strip=True)
            
            # ÉTAPE 4 : Construire l'URL complète
            if title_text and len(title_text) > 5:
                deal_link = link_tag['href']
                
                if not deal_link.startswith('http'):
                    deal_link = "https://www.dealabs.com" + deal_link
                
                temp_emoji = get_temperature_emoji(temperature)
                print(f"✅ Deal {temp_emoji} trouvé ({temperature}°) : {title_text[:80]}{'...' if len(title_text) > 80 else ''}")
                return title_text, deal_link, temperature
        
        print("❌ Aucun deal valide trouvé")
        return None, None, 0
        
    except Exception as e:
        print(f"❌ Erreur lors du scraping : {e}")
        return None, None, 0

def extraire_temperature(deal_element):
    """
    Extrait la température d'un élément de deal
    """
    temp_selectors = [
        '[class*="temperature"]', '[class*="temp"]', '[class*="vote"]', 
        '[class*="score"]', 'span[title*="°"]', '*'
    ]
    
    for selector in temp_selectors:
        try:
            elements = deal_element.select(selector)
            for element in elements:
                # Chercher dans le texte
                text = element.get_text(strip=True)
                temperature = extraire_nombre_temperature(text)
                if temperature > 0:
                    return temperature
                
                # Chercher dans les attributs
                for attr_value in element.attrs.values():
                    if isinstance(attr_value, str):
                        temperature = extraire_nombre_temperature(attr_value)
                        if temperature > 0:
                            return temperature
        except:
            continue
    
    return 0

def extraire_nombre_temperature(text):
    """
    Extrait un nombre de température d'un texte
    """
    patterns = [
        r'(\d+)°',           # 123°
        r'(\d+)\s*°',        # 123 °
        r'\+(\d+)',          # +123
        r'-(\d+)',           # -123
        r'(\d+)\s*points?',  # 123 points
        r'(\d+)\s*votes?',   # 123 votes
        r'(\d{2,4})',        # 2-4 chiffres
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text)
        if matches:
            try:
                numbers = [int(match) for match in matches]
                valid_temps = [n for n in numbers if 1 <= n <= 9999]
                if valid_temps:
                    return max(valid_temps)
            except ValueError:
                continue
    
    return 0

def get_temperature_emoji(temperature):
    """
    Retourne un émoji selon la température
    """
    if temperature >= TEMPERATURE_HOT:
        return "🔥🔥🔥"
    elif temperature >= TEMPERATURE_PREMIUM:
        return "🔥🔥"
    elif temperature >= TEMPERATURE_MINIMUM:
        return "🔥"
    else:
        return "❄️"

def deal_existe_en_bdd(supabase, deal_link):
    """
    Vérifie si un deal existe déjà en base de données
    """
    try:
        response = supabase.table('deals_envoyes').select('id').eq('deal_link', deal_link).execute()
        existe = len(response.data) > 0
        
        if existe:
            print("🥱 Deal déjà traité (trouvé en BDD)")
        else:
            print("✨ Nouveau deal détecté !")
            
        return existe
        
    except Exception as e:
        print(f"❌ Erreur BDD lors de la vérification : {e}")
        return True  # En cas d'erreur, on considère qu'il existe pour éviter les doublons

def recuperer_lien_marchand(url_dealabs):
    """
    Visite la page du deal et récupère le lien vers le marchand
    """
    print(f"🕵️‍♂️ Recherche du lien marchand sur {url_dealabs[:50]}...")
    
    try:
        time.sleep(random.uniform(1, 2))  # Délai pour éviter d'être détecté
        
        session = requests.Session()
        session.headers.update(HEADERS)
        response = session.get(url_dealabs, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Sélecteurs possibles pour le bouton "Voir le deal"
        bouton_selectors = [
            'a[class*="thread-deal-link"]',
            'a[class*="dealLink"]', 
            'a[class*="goToLink"]',
            'a[data-gtm-payload]',
            'a[href*="out.php"]',
            '.cept-dealBtn a',
            '.thread-deal-btn a'
        ]
        
        for selector in bouton_selectors:
            bouton_deal = soup.select_one(selector)
            if bouton_deal and bouton_deal.get('href'):
                lien_marchand = bouton_deal.get('href')
                
                # Construire l'URL complète si nécessaire
                if not lien_marchand.startswith('http'):
                    lien_marchand = "https://www.dealabs.com" + lien_marchand
                
                print(f"✅ Lien marchand trouvé : {lien_marchand[:70]}...")
                return lien_marchand
        
        print("❌ Aucun lien marchand trouvé")
        return None
        
    except Exception as e:
        print(f"❌ Erreur lors de la récupération du lien marchand : {e}")
        return None

def transformer_en_lien_affilie(url_marchand):
    """
    Transforme une URL en lien affilié si possible
    """
    if not url_marchand:
        return None
    
    print(f"💰 Analyse du lien pour affiliation...")
    
    # Amazon France
    if "amazon.fr" in url_marchand:
        # Nettoyer l'URL et ajouter notre tag
        url_propre = url_marchand.split('?')[0].split('&')[0]
        lien_affilie = f"{url_propre}?tag={AMAZON_TAG}"
        print(f"✅ Lien Amazon affilié créé")
        return lien_affilie
    
    # Fnac (exemple)
    elif "fnac.com" in url_marchand:
        # Ajouter votre logique Fnac/Awin ici
        print("ℹ️  Fnac détecté mais pas encore implémenté")
        return url_marchand
    
    # Cdiscount (exemple)  
    elif "cdiscount.com" in url_marchand:
        # Ajouter votre logique Cdiscount ici
        print("ℹ️  Cdiscount détecté mais pas encore implémenté")
        return url_marchand
    
    else:
        print("ℹ️  Marchand non partenaire, lien original conservé")
        return url_marchand

def envoyer_notification_discord(titre, lien_final, temperature=0):
    """
    Envoie une notification Discord avec le lien final (affilié si possible)
    """
    # Limiter la longueur du titre
    if len(titre) > 180:
        titre = titre[:177] + "..."
    
    temp_emoji = get_temperature_emoji(temperature)
    temp_text = f" ({temperature}°)" if temperature > 0 else ""
    
    # Message selon la température
    if temperature >= TEMPERATURE_HOT:
        intro = f"🚨 **DEAL TRÈS HOT DÉTECTÉ !** {temp_emoji}"
    elif temperature >= TEMPERATURE_PREMIUM:
        intro = f"🔥 **EXCELLENT DEAL DÉTECTÉ !** {temp_emoji}"
    else:
        intro = f"✨ **Nouveau Deal Détecté !** {temp_emoji}"
    
    # Indiquer si c'est un lien affilié
    lien_info = "🔗 **Lien :** " 
    if lien_final and "amazon.fr" in lien_final and AMAZON_TAG in lien_final:
        lien_info = "💰 **Lien affilié :** "
    
    message = f"{intro}\n\n**{titre}**{temp_text}\n\n{lien_info}{lien_final}"
    
    data = {
        "content": message,
        "username": "DealBot Pro",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/3159/3159310.png"
    }

    print("📤 Envoi de la notification à Discord...")
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=data, timeout=10)
        response.raise_for_status()
        print("✅ Notification envoyée avec succès !")
        return True
    except Exception as e:
        print(f"❌ Erreur lors de l'envoi à Discord : {e}")
        return False

def sauvegarder_deal_traite(supabase, deal_link, titre="", temperature=0):
    """
    Sauvegarde le deal traité en base de données
    """
    try:
        data = {
            "deal_link": deal_link,
            "titre": titre[:200],  # Limiter la longueur
            "temperature": temperature,
            "traite_le": "now()"
        }
        
        supabase.table('deals_envoyes').insert(data).execute()
        print("💾 Deal sauvegardé en base de données")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde : {e}")
        return False

def debug_page_structure():
    """
    Fonction de debug pour analyser la structure de la page
    """
    print("🔍 Mode debug activé...")
    
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        response = session.get(DEALABS_URL, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        all_links = soup.find_all('a', href=True)
        deal_links = [link for link in all_links if '/deals/' in link.get('href', '').lower()]
        
        print(f"🔗 {len(all_links)} liens total, {len(deal_links)} liens de deals")
        
        if deal_links[:3]:
            print("📋 Premiers deals trouvés:")
            for i, link in enumerate(deal_links[:3]):
                title = link.get_text(strip=True)[:60]
                href = link['href']
                print(f"  {i+1}. {title} -> {href}")
        
    except Exception as e:
        print(f"❌ Erreur debug : {e}")

# --- PROGRAMME PRINCIPAL ---
if __name__ == "__main__":
    print("🤖 Démarrage du DealBot Pro avec monétisation...")
    
    # Vérifier les configurations
    if not DISCORD_WEBHOOK_URL or len(DISCORD_WEBHOOK_URL) < 50:
        print("❌ ERREUR: DISCORD_WEBHOOK_URL mal configuré")
        exit(1)
        
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ ERREUR: Configuration Supabase manquante")
        exit(1)
    
    # Connexion à Supabase
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Connecté à Supabase")
    except Exception as e:
        print(f"❌ Erreur connexion Supabase : {e}")
        exit(1)
    
    print(f"🌡️ Seuil de température : {TEMPERATURE_MINIMUM}°")
    print(f"💰 Tag Amazon : {AMAZON_TAG}")
    
    # Décommentez pour debug
    # debug_page_structure()
    
    # --- WORKFLOW PRINCIPAL ---
    # 1. Trouver un deal
    titre, lien_dealabs, temperature = scraper_dealabs()
    
    if not titre or not lien_dealabs:
        print("❌ Aucun deal trouvé")
        exit(0)
    
    # 2. Vérifier s'il est nouveau
    if deal_existe_en_bdd(supabase, lien_dealabs):
        print("🛑 Deal déjà traité, arrêt du processus")
        exit(0)
    
    # 3. Récupérer le lien marchand
    lien_marchand = recuperer_lien_marchand(lien_dealabs)
    
    # 4. Le transformer en lien affilié si possible
    lien_final = transformer_en_lien_affilie(lien_marchand) if lien_marchand else lien_dealabs
    
    # 5. Envoyer la notification
    temp_emoji = get_temperature_emoji(temperature)
    print(f"📤 Envoi du deal {temp_emoji} ({temperature}°)...")
    
    success = envoyer_notification_discord(titre, lien_final, temperature)
    
    # 6. Sauvegarder le traitement
    if success:
        sauvegarder_deal_traite(supabase, lien_dealabs, titre, temperature)
        print("🎉 Mission accomplie ! Deal envoyé et sauvegardé")
    else:
        print("⚠️ Erreur lors de l'envoi, deal non sauvegardé")