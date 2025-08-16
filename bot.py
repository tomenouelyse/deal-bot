# Étape 1 : Importer les bibliothèques dont on a besoin
import os
import requests
from bs4 import BeautifulSoup
import time
import random
from supabase import create_client, Client 

# Étape 2 : Configurer nos variables
DEALABS_URL = "https://www.dealabs.com/hot"

# ATTENTION : J'ai masqué votre webhook Discord pour la sécurité
# Remplacez par votre vraie URL de webhook
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "https://discordapp.com/api/webhooks/1406262114183807146/BHrmH-9KbJfd-e6bHz9ScTnS7VuwL7NDnlArqWxoE86IO4RGiArnT9oOy5v0Mu4WPq2x")

# NOUVEAUX PARAMÈTRES DE FILTRAGE
TEMPERATURE_MINIMUM = 100  # Température minimum pour envoyer un deal
TEMPERATURE_PREMIUM = 500  # Température pour les deals "premium"
TEMPERATURE_HOT = 1000     # Température pour les deals "très hot"

# Headers plus réalistes pour éviter la détection
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
    Version améliorée du scraper avec plusieurs sélecteurs CSS pour s'adapter 
    aux changements de structure du site
    """
    print("🔍 Tentative de scraping de Dealabs...")
    
    try:
        # Ajouter un délai aléatoire pour paraître plus humain
        time.sleep(random.uniform(1, 3))
        
        session = requests.Session()
        session.headers.update(HEADERS)
        
        response = session.get(DEALABS_URL, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Essayer différents sélecteurs CSS possibles
        selectors_to_try = [
            # Sélecteurs récents possibles
            'article[class*="thread"]',
            'div[class*="thread"]',
            'article[data-thread-id]',
            'div[data-thread-id]',
            # Anciens sélecteurs
            'article.thread--card',
            'div.thread--card',
            # Sélecteurs génériques
            'article',
            'div[class*="deal"]',
            'div[class*="offer"]'
        ]
        
        all_deals = []
        
        for selector in selectors_to_try:
            all_deals = soup.select(selector)
            if all_deals:
                print(f"✅ Trouvé {len(all_deals)} éléments avec le sélecteur: {selector}")
                break
        
        if not all_deals:
            print("❌ Aucun élément trouvé avec les sélecteurs CSS")
            # Debug: afficher un échantillon du HTML
            print("📄 Voici un échantillon du HTML reçu:")
            print(soup.prettify()[:1000] + "...")
            return None, None
        
        # Essayer de trouver les liens et titres dans les éléments trouvés
        for i, deal_element in enumerate(all_deals[:20]):  # Augmenté à 20 pour plus de chances
            print(f"🔍 Analyse de l'élément {i+1}...")
            
            # ÉTAPE 1 : EXTRACTION DE LA TEMPÉRATURE
            temperature = extraire_temperature(deal_element)
            print(f"🌡️ Température détectée : {temperature}°")
            
            # FILTRAGE : On ignore les deals en dessous du seuil
            if temperature < TEMPERATURE_MINIMUM:
                print(f"❄️ Deal ignoré (température {temperature}° < {TEMPERATURE_MINIMUM}°)")
                continue
            
            # ÉTAPE 2 : EXTRACTION DU LIEN
            # Différentes façons de chercher le lien
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
                print("❌ Aucun lien trouvé dans cet élément")
                continue
            
            # ÉTAPE 3 : EXTRACTION DU TITRE
            # Différentes façons de chercher le titre
            title_selectors = [
                'strong',
                'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                '[class*="title"]',
                '[class*="heading"]',
                'span'
            ]
            
            title_text = None
            for title_selector in title_selectors:
                title_element = link_tag.select_one(title_selector)
                if title_element:
                    title_text = title_element.get_text(strip=True)
                    if title_text and len(title_text) > 10:  # Titre valide
                        break
            
            # Fallback: utiliser le texte du lien ou l'attribut title
            if not title_text:
                title_text = link_tag.get('title', '').strip()
                if not title_text:
                    title_text = link_tag.get_text(strip=True)
            
            # ÉTAPE 4 : VALIDATION ET RETOUR
            if title_text and len(title_text) > 5:
                deal_link = link_tag['href']
                
                # Construire l'URL complète si nécessaire
                if not deal_link.startswith('http'):
                    deal_link = "https://www.dealabs.com" + deal_link
                
                # Émoji en fonction de la température
                temp_emoji = get_temperature_emoji(temperature)
                
                print(f"✅ Deal {temp_emoji} trouvé ({temperature}°) : {title_text[:80]}{'...' if len(title_text) > 80 else ''}")
                return title_text, deal_link, temperature
        
        print("❌ Aucun deal valide trouvé dans les éléments analysés")
        return None, None, 0
        
    except requests.exceptions.Timeout:
        print("⏰ Timeout lors de la connexion à Dealabs")
        return None, None, 0
    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur lors de la requête à Dealabs : {e}")
        return None, None, 0
    except Exception as e:
        print(f"❌ Erreur inattendue : {e}")
        return None, None, 0

def extraire_temperature(deal_element):
    """
    Extrait la température d'un élément de deal.
    Retourne 0 si aucune température n'est trouvée.
    """
    # Sélecteurs possibles pour la température
    temp_selectors = [
        # Sélecteurs spécifiques à la température
        '[class*="temperature"]',
        '[class*="temp"]',
        '[class*="vote"]',
        '[class*="score"]',
        '[class*="rating"]',
        # Sélecteurs plus génériques
        'span[title*="°"]',
        'div[title*="°"]',
        'span[class*="number"]',
        # Recherche dans le texte
        '*'
    ]
    
    for selector in temp_selectors:
        try:
            elements = deal_element.select(selector)
            for element in elements:
                # Chercher dans le texte de l'élément
                text = element.get_text(strip=True)
                temperature = extraire_nombre_temperature(text)
                if temperature > 0:
                    return temperature
                
                # Chercher dans les attributs title, data-*, etc.
                for attr_name, attr_value in element.attrs.items():
                    if isinstance(attr_value, str):
                        temperature = extraire_nombre_temperature(attr_value)
                        if temperature > 0:
                            return temperature
        except:
            continue
    
    return 0

def extraire_nombre_temperature(text):
    """
    Extrait un nombre de température d'un texte.
    Exemples: "125°" -> 125, "+89" -> 89, "température: 234" -> 234
    """
    import re
    
    # Patterns pour trouver des nombres liés à la température
    patterns = [
        r'(\d+)°',           # Format: 123°
        r'(\d+)\s*°',        # Format: 123 °
        r'\+(\d+)',          # Format: +123
        r'-(\d+)',           # Format: -123 (température négative)
        r'(\d+)\s*points?',  # Format: 123 points
        r'(\d+)\s*votes?',   # Format: 123 votes
        r'(\d{2,4})',        # Nombres de 2 à 4 chiffres (probable température)
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text)
        if matches:
            try:
                # Prendre le plus grand nombre trouvé (souvent la température)
                numbers = [int(match) for match in matches]
                # Filtrer les nombres qui semblent être des températures (entre 1 et 9999)
                valid_temps = [n for n in numbers if 1 <= n <= 9999]
                if valid_temps:
                    return max(valid_temps)
            except ValueError:
                continue
    
    return 0

def get_temperature_emoji(temperature):
    """
    Retourne un émoji en fonction de la température du deal
    """
    if temperature >= TEMPERATURE_HOT:
        return "🔥🔥🔥"
    elif temperature >= TEMPERATURE_PREMIUM:
        return "🔥🔥"
    elif temperature >= TEMPERATURE_MINIMUM:
        return "🔥"
    else:
        return "❄️"

def envoyer_notification_discord(titre, lien, temperature=0):
    """
    Envoie une notification Discord avec une meilleure mise en forme
    et des informations sur la température
    """
    # Limiter la longueur du titre pour Discord
    if len(titre) > 180:  # Réduit pour faire place à la température
        titre = titre[:177] + "..."
    
    # Émoji et formatage en fonction de la température
    temp_emoji = get_temperature_emoji(temperature)
    temp_text = f" ({temperature}°)" if temperature > 0 else ""
    
    # Message personnalisé selon la température
    if temperature >= TEMPERATURE_HOT:
        intro = f"🚨 **DEAL TRÈS HOT DÉTECTÉ !** {temp_emoji}"
    elif temperature >= TEMPERATURE_PREMIUM:
        intro = f"🔥 **EXCELLENT DEAL DÉTECTÉ !** {temp_emoji}"
    else:
        intro = f"✨ **Nouveau Deal Détecté !** {temp_emoji}"
    
    message_pour_discord = f"{intro}\n\n**{titre}**{temp_text}\n\n🔗 **Lien :** {lien}"
    
    data = {
        "content": message_pour_discord,
        "username": "DealBot",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/3159/3159310.png"
    }

    print("📤 Envoi de la notification à Discord...")
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=data, timeout=10)
        response.raise_for_status()
        print("✅ Notification envoyée avec succès !")
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur lors de l'envoi à Discord : {e}")
        return False

def debug_page_structure():
    """
    Fonction de debug pour analyser la structure de la page
    """
    print("🔍 Mode debug - Analyse de la structure de la page...")
    
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        
        response = session.get(DEALABS_URL, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        print("📊 Analyse des éléments trouvés sur la page:")
        
        # Chercher tous les liens
        all_links = soup.find_all('a', href=True)
        deal_links = [link for link in all_links if any(keyword in link['href'].lower() for keyword in ['/deals/', '/bons-plans/', '/groupe/'])]
        
        print(f"🔗 Nombre total de liens: {len(all_links)}")
        print(f"🎯 Liens potentiels de deals: {len(deal_links)}")
        
        if deal_links:
            print("📋 Premiers liens de deals trouvés:")
            for i, link in enumerate(deal_links[:5]):
                title = link.get_text(strip=True)[:100]
                href = link['href']
                print(f"  {i+1}. {title} -> {href}")
        
        # Analyser les classes CSS communes
        all_elements_with_class = soup.find_all(attrs={"class": True})
        class_counts = {}
        for elem in all_elements_with_class[:100]:  # Limiter pour éviter la surcharge
            for class_name in elem.get('class', []):
                if 'thread' in class_name.lower() or 'deal' in class_name.lower():
                    class_counts[class_name] = class_counts.get(class_name, 0) + 1
        
        if class_counts:
            print("🏷️  Classes CSS intéressantes trouvées:")
            for class_name, count in sorted(class_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"  .{class_name} ({count} fois)")
        
    except Exception as e:
        print(f"❌ Erreur lors du debug : {e}")

# --- LE PROGRAMME PRINCIPAL - VERSION SUPABASE ---
if __name__ == "__main__":
    print("🤖 Démarrage du bot Dealabs...")

    # --- NOUVELLE PARTIE : CONNEXION À SUPABASE ---
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    # Vérifie si les secrets sont bien configurés
    if not supabase_url or not supabase_key:
        print("❌ ERREUR: Les secrets SUPABASE_URL et SUPABASE_KEY ne sont pas configurés.")
        exit(1)
        
    supabase: Client = create_client(supabase_url, supabase_key)
    print("✅ Connecté à la base de données Supabase.")

    titre_du_deal, lien_du_deal, temperature_du_deal = scraper_dealabs()

    if titre_du_deal and lien_du_deal:
        # Vérifier si le lien existe déjà dans la base de données
        response = supabase.table('deals_envoyes').select('id').eq('deal_link', lien_du_deal).execute()
        
        # Si la réponse contient des données, c'est qu'on l'a déjà envoyé
        if len(response.data) == 0:
            print(f"✨ Nouveau deal trouvé ! Envoi en cours...")
            success = envoyer_notification_discord(titre_du_deal, lien_du_deal, temperature_du_deal)
            
            if success:
                # Insérer le nouveau lien dans la table Supabase
                supabase.table('deals_envoyes').insert({"deal_link": lien_du_deal}).execute()
                print("💾 Deal sauvegardé dans la base de données.")
                print("🎉 Mission accomplie !")
            else:
                print("⚠️  Deal trouvé mais erreur lors de l'envoi à Discord.")
        else:
            print(f"🥱 Ce deal a déjà été envoyé (trouvé en BDD). On l'ignore.")
    else:
        print("❌ Aucun deal à envoyer.")
        print(f"💡 Seuil de température actuel : {TEMPERATURE_MINIMUM}°")
        print("\n🔧 Suggestions:")
        print("   1. Réduisez TEMPERATURE_MINIMUM pour des deals moins populaires")
        print("   2. Décommentez debug_page_structure() pour analyser la page.")
        print("   3. Vérifiez que le site n'a pas changé de structure.")
        print("   4. Essayez à nouveau dans quelques minutes.")