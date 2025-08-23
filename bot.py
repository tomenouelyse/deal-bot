# Étape 1 : Importer les bibliothèques dont on a besoin
import os
import requests
from bs4 import BeautifulSoup
import time
import random
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from supabase import create_client, Client 

# Étape 2 : Configurer nos variables
DEALABS_URL = "https://www.dealabs.com/hot"

# Configuration des secrets via variables d'environnement
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

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
        
        # Sélecteurs CSS pour trouver les deals - Version améliorée
        selectors_to_try = [
            'article[data-thread-id]',  # Sélecteur le plus fiable
            'div[data-thread-id]',
            'article[class*="thread"]',
            'div[class*="thread"]',
            'article.thread--card',
            'article',
            '.threadGrid article',
            '.threadList article'
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
            
            # ÉTAPE 2 : Extraire le lien du deal - Version améliorée
            link_selectors = [
                'a[class*="thread-link"]',
                'a[href*="/deals/"]', 
                'a[href*="/bons-plans/"]',
                'a[href*="/codes-promo/"]',
                'a[href*="/gratuit/"]',
                'h1 a', 'h2 a', 'h3 a',  # Titre cliquable
                'a[title]',
                'a'
            ]
            
            link_tag = None
            for link_selector in link_selectors:
                link_tag = deal_element.select_one(link_selector)
                if link_tag and 'href' in link_tag.attrs:
                    href = link_tag.get('href', '')
                    # Vérifier que c'est bien un lien vers un deal
                    if any(keyword in href.lower() for keyword in ['/deals/', '/bons-plans/', '/codes-promo/', '/gratuit/']):
                        break
            
            if not link_tag:
                print("❌ Aucun lien trouvé")
                continue
            
            # ÉTAPE 3 : Extraire le titre - Version améliorée
            title_selectors = [
                'strong[class*="thread-title"]',
                'h1', 'h2', 'h3',
                'strong', 
                '[class*="title"]', 
                'span[class*="title"]',
                'a span'
            ]
            
            title_text = None
            for title_selector in title_selectors:
                title_element = deal_element.select_one(title_selector)
                if title_element:
                    title_text = title_element.get_text(strip=True)
                    if title_text and len(title_text) > 10:
                        break
            
            # Fallback pour le titre
            if not title_text or len(title_text) < 10:
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
    Extrait la température d'un élément de deal - Version améliorée
    """
    # Sélecteurs spécifiques pour la température sur Dealabs
    temp_selectors = [
        'span[class*="vote-temp"]',
        'span[class*="temperature"]', 
        'div[class*="temperature"]',
        'span[class*="vote-box"]',
        '[class*="vote-"] span',
        '[data-vote]',
        '[class*="temp"]', 
        '[class*="vote"]', 
        '[class*="score"]', 
        'span[title*="°"]',
        '.vote-box span',
        '.vote-temp',
        '*'
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
                for attr_name, attr_value in element.attrs.items():
                    if isinstance(attr_value, str):
                        temperature = extraire_nombre_temperature(attr_value)
                        if temperature > 0:
                            return temperature
                    elif isinstance(attr_value, list):
                        for val in attr_value:
                            temperature = extraire_nombre_temperature(str(val))
                            if temperature > 0:
                                return temperature
        except:
            continue
    
    return 0

def extraire_nombre_temperature(text):
    """
    Extrait un nombre de température d'un texte - Version améliorée
    """
    if not text:
        return 0
        
    patterns = [
        r'(\d+)°',           # 123°
        r'(\d+)\s*°',        # 123 °
        r'\+(\d+)',          # +123
        r'temp[^0-9]*(\d+)', # temp: 123
        r'vote[^0-9]*(\d+)', # vote: 123
        r'score[^0-9]*(\d+)',# score: 123
        r'(\d+)\s*points?',  # 123 points
        r'(\d+)\s*votes?',   # 123 votes
        r'(\d{2,4})',        # 2-4 chiffres consécutifs
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text.lower())
        if matches:
            try:
                numbers = [int(match) for match in matches]
                # Filtrer les nombres raisonnables pour une température
                valid_temps = [n for n in numbers if 0 <= n <= 9999]
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
        print(f"🔍 Vérification en BDD pour : {deal_link[:60]}...")
        
        response = supabase.table('deals_envoyes').select('id, titre').eq('deal_link', deal_link).execute()
        existe = len(response.data) > 0
        
        if existe:
            deal_info = response.data[0]
            print(f"🥱 Deal déjà traité : '{deal_info.get('titre', 'Sans titre')[:50]}...'")
            return True
        else:
            print("✨ Nouveau deal détecté, pas encore en BDD !")
            return False
            
    except Exception as e:
        print(f"❌ Erreur BDD lors de la vérification : {e}")
        print("⚠️  Par précaution, on considère le deal comme existant pour éviter les doublons")
        return True

def recuperer_lien_marchand(url_dealabs):
    """
    Visite la page du deal et récupère le lien vers le marchand - Version corrigée
    """
    print(f"🕵️‍♂️ Recherche du lien marchand sur {url_dealabs[:50]}...")
    
    try:
        time.sleep(random.uniform(1, 2))
        
        session = requests.Session()
        session.headers.update(HEADERS)
        response = session.get(url_dealabs, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # MÉTHODE 1: Chercher les boutons "Voir le deal" avec de meilleurs sélecteurs
        bouton_selectors = [
            'a[class*="cept-dealBtn"]',           # Sélecteur principal Dealabs
            'a[class*="dealBtn"]',
            'a[class*="thread-deal"]',
            'a[data-handler="goToLink"]',         # Handler JavaScript
            'a[href*="out.php"]',                 # Lien de redirection Dealabs
            'a[href*="/visit/"]',                 # Autre type de redirection
            'a[class*="goToLink"]',
            'a.btn[href*="dealabs.com"]',
            '.deal-btn a',
            '.thread-deal-btn a',
            '.cept-dealBtn',
            'a[title*="aller"]',
            'a[title*="voir"]',
        ]
        
        lien_marchand = None
        
        for selector in bouton_selectors:
            boutons = soup.select(selector)
            for bouton in boutons:
                href = bouton.get('href', '')
                if href and ('out.php' in href or '/visit/' in href or any(domain in href for domain in ['amazon.fr', 'fnac.com', 'cdiscount.com'])):
                    if not href.startswith('http'):
                        href = "https://www.dealabs.com" + href
                    
                    print(f"✅ Lien de redirection trouvé : {href[:70]}...")
                    
                    # MÉTHODE 2: Suivre la redirection pour obtenir l'URL finale
                    lien_final = suivre_redirection(href, session)
                    if lien_final:
                        return lien_final
                    else:
                        lien_marchand = href  # Fallback
                        
        # MÉTHODE 3: Chercher directement les liens vers des marchands connus
        if not lien_marchand:
            print("🔍 Recherche directe des liens marchands...")
            liens_directs = soup.find_all('a', href=True)
            
            marchands = ['amazon.fr', 'fnac.com', 'cdiscount.com', 'darty.com', 'boulanger.com', 'ldlc.com']
            
            for link in liens_directs:
                href = link.get('href', '')
                if any(marchand in href.lower() for marchand in marchands):
                    if not href.startswith('http'):
                        continue
                    print(f"✅ Lien marchand direct trouvé : {href[:70]}...")
                    return href
        
        if lien_marchand:
            print(f"✅ Lien de redirection retourné : {lien_marchand[:70]}...")
            return lien_marchand
        else:
            print("❌ Aucun lien marchand trouvé")
            return None
        
    except Exception as e:
        print(f"❌ Erreur lors de la récupération du lien marchand : {e}")
        return None

def suivre_redirection(url_redirection, session):
    """
    Suit une redirection Dealabs pour obtenir l'URL finale du marchand
    """
    try:
        print(f"🔄 Suivi de la redirection : {url_redirection[:50]}...")
        
        # Suivre les redirections sans télécharger le contenu complet
        response = session.head(url_redirection, allow_redirects=True, timeout=10)
        
        if response.url != url_redirection:
            print(f"✅ URL finale après redirection : {response.url[:70]}...")
            return response.url
        else:
            # Si pas de redirection automatique, essayer avec GET
            response = session.get(url_redirection, timeout=10, allow_redirects=True)
            if response.url != url_redirection:
                print(f"✅ URL finale après redirection GET : {response.url[:70]}...")
                return response.url
                
    except Exception as e:
        print(f"⚠️  Erreur lors du suivi de redirection : {e}")
    
    return None

def transformer_en_lien_affilie(url_marchand):
    """
    Transforme une URL en lien affilié si possible - Version améliorée
    """
    if not url_marchand:
        return None
    
    print(f"💰 Analyse du lien pour affiliation : {url_marchand[:50]}...")
    
    try:
        # Amazon France
        if "amazon.fr" in url_marchand.lower():
            parsed_url = urlparse(url_marchand)
            query_params = parse_qs(parsed_url.query)
            
            # Nettoyer et ajouter notre tag
            query_params['tag'] = [AMAZON_TAG]
            
            # Supprimer les paramètres de tracking externes
            params_to_remove = ['ref', 'ref_', 'pf_rd_p', 'pf_rd_r', 'pd_rd_i', 'pd_rd_r', 'pd_rd_w', 'pd_rd_wg']
            for param in params_to_remove:
                query_params.pop(param, None)
            
            new_query = urlencode(query_params, doseq=True)
            lien_affilie = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, parsed_url.params, new_query, parsed_url.fragment))
            
            print(f"✅ Lien Amazon affilié créé avec tag : {AMAZON_TAG}")
            return lien_affilie
        
        # Fnac (Awin/Commission Junction)
        elif "fnac.com" in url_marchand.lower():
            # Exemple d'ajout d'affiliation Fnac (remplacez par vos vrais paramètres)
            if "?" in url_marchand:
                lien_affilie = f"{url_marchand}&awc=VOTRE_ID_AWIN"
            else:
                lien_affilie = f"{url_marchand}?awc=VOTRE_ID_AWIN"
            print("ℹ️  Fnac - ajoutez votre vrai ID Awin")
            return lien_affilie
        
        # Cdiscount
        elif "cdiscount.com" in url_marchand.lower():
            # Exemple d'ajout d'affiliation Cdiscount
            print("ℹ️  Cdiscount détecté - ajoutez votre logique d'affiliation")
            return url_marchand
        
        # Autres marchands
        else:
            print("ℹ️  Marchand non partenaire, lien original conservé")
            return url_marchand
            
    except Exception as e:
        print(f"⚠️  Erreur lors de la transformation en lien affilié : {e}")
        return url_marchand

def envoyer_notification_discord(titre, lien_final, temperature=0, lien_dealabs=None):
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
    
    # Indiquer le type de lien
    lien_info = ""
    if lien_final:
        if "amazon.fr" in lien_final and AMAZON_TAG in lien_final:
            lien_info = "💰 **Lien Amazon affilié :** "
        elif any(marchand in lien_final.lower() for marchand in ['fnac.com', 'cdiscount.com']):
            lien_info = "🛒 **Lien marchand :** "
        elif "dealabs.com" in lien_final:
            lien_info = "🔗 **Lien Dealabs :** "
        else:
            lien_info = "🔗 **Lien :** "
    
    # Construction du message
    message = f"{intro}\n\n**{titre}**{temp_text}\n\n{lien_info}{lien_final}"
    
    # Ajouter le lien Dealabs si différent
    if lien_dealabs and lien_final != lien_dealabs and not "dealabs.com" in lien_final:
        message += f"\n📋 **Voir sur Dealabs :** {lien_dealabs}"
    
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

def sauvegarder_deal_traite(supabase, deal_link, titre="", temperature=0, lien_marchand=""):
    """
    Sauvegarde le deal traité en base de données - Version corrigée
    """
    try:
        # Structure de base des données (sans created_at car géré automatiquement par Supabase)
        data = {
            "deal_link": deal_link,
            "titre": titre[:200],  # Limiter la longueur
            "temperature": temperature
        }
        
        # Ajouter le lien marchand seulement s'il existe et si la colonne existe
        if lien_marchand:
            data["lien_marchand"] = lien_marchand[:500]
        
        # Utiliser upsert pour éviter les erreurs de doublons
        result = supabase.table('deals_envoyes').upsert(data, on_conflict="deal_link").execute()
        print("💾 Deal sauvegardé en base de données")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde : {e}")
        print(f"🔧 Tentative avec structure minimale...")
        
        # Fallback avec structure minimale
        try:
            data_minimal = {
                "deal_link": deal_link,
                "titre": titre[:200],
                "temperature": temperature
            }
            
            result = supabase.table('deals_envoyes').upsert(data_minimal, on_conflict="deal_link").execute()
            print("💾 Deal sauvegardé avec structure minimale")
            return True
            
        except Exception as e2:
            print(f"❌ Erreur même avec structure minimale : {e2}")
            return False

def debug_page_structure(url=None):
    """
    Fonction de debug pour analyser la structure de la page
    """
    url = url or DEALABS_URL
    print(f"🔍 Mode debug activé pour : {url}")
    
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        response = session.get(url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        if "/bons-plans/" in url:
            # Debug d'une page de deal spécifique
            print("🔍 Analyse d'une page de deal...")
            
            boutons_deal = soup.find_all('a', href=True)
            boutons_pertinents = []
            
            for bouton in boutons_deal:
                href = bouton.get('href', '')
                classes = ' '.join(bouton.get('class', []))
                text = bouton.get_text(strip=True)
                
                if any(keyword in href.lower() for keyword in ['out.php', '/visit/', 'amazon.fr', 'fnac.com']):
                    boutons_pertinents.append({
                        'href': href,
                        'classes': classes,
                        'text': text[:50]
                    })
            
            print(f"🎯 {len(boutons_pertinents)} boutons pertinents trouvés:")
            for i, bouton in enumerate(boutons_pertinents[:5]):
                print(f"  {i+1}. Classes: {bouton['classes']}")
                print(f"      Href: {bouton['href']}")
                print(f"      Text: {bouton['text']}")
                print()
        else:
            # Debug de la page principale
            all_links = soup.find_all('a', href=True)
            deal_links = [link for link in all_links if any(keyword in link.get('href', '').lower() for keyword in ['/deals/', '/bons-plans/', '/codes-promo/'])]
            
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
    print("🤖 Démarrage du DealBot Pro avec monétisation améliorée...")
    
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
    
    # --- WORKFLOW PRINCIPAL AVEC AFFILIATION AMÉLIORÉE ---
    # 1. Trouver un deal
    titre, lien_dealabs, temperature = scraper_dealabs()
    
    if not titre or not lien_dealabs:
        print("❌ Aucun deal trouvé")
        exit(0)
    
    # 2. VÉRIFICATION CRITIQUE : Le deal est-il nouveau ?
    if deal_existe_en_bdd(supabase, lien_dealabs):
        print("🛑 Deal déjà traité, arrêt du processus pour éviter doublon")
        exit(0)
    
    # 3. SAUVEGARDE IMMÉDIATE pour réserver le deal
    print("🔒 Réservation du deal en BDD...")
    if not sauvegarder_deal_traite(supabase, lien_dealabs, titre, temperature):
        print("❌ Impossible de réserver le deal, arrêt pour éviter les conflits")
        exit(1)
    
    # 4. Récupérer le lien marchand (version améliorée)
    lien_marchand = recuperer_lien_marchand(lien_dealabs)
    
    # 5. Le transformer en lien affilié si possible
    lien_final = transformer_en_lien_affilie(lien_marchand) if lien_marchand else lien_dealabs
    
    # 6. Mettre à jour la BDD avec le lien marchand trouvé
    if lien_marchand:
        sauvegarder_deal_traite(supabase, lien_dealabs, titre, temperature, lien_final)
    
    # 7. Envoyer la notification avec les deux liens si nécessaire
    temp_emoji = get_temperature_emoji(temperature)
    print(f"📤 Envoi du deal {temp_emoji} ({temperature}°)...")
    
    success = envoyer_notification_discord(titre, lien_final, temperature, lien_dealabs)
    
    # 8. Résultat final
    if success:
        if lien_marchand and lien_marchand != lien_dealabs:
            if "amazon.fr" in lien_final and AMAZON_TAG in lien_final:
                print("🎉 Mission accomplie ! Deal envoyé avec lien affilié Amazon 💰")
            else:
                print("🎉 Mission accomplie ! Deal envoyé avec lien marchand direct 🛒")
        else:
            print("🎉 Mission accomplie ! Deal envoyé (lien Dealabs) 📋")
    else:
        print("⚠️ Erreur lors de l'envoi Discord, mais deal déjà sauvegardé")
    
    # 9. Stats finales
    print(f"\n📊 RÉSUMÉ:")
    print(f"   🌡️  Température: {temperature}°")
    print(f"   🔗 Lien Dealabs: {lien_dealabs[:50]}...")
    print(f"   🛒 Lien marchand: {'Trouvé ✅' if lien_marchand else 'Non trouvé ❌'}")
    print(f"   💰 Affiliation: {'Activée ✅' if lien_final and AMAZON_TAG in lien_final else 'Non applicable'}")