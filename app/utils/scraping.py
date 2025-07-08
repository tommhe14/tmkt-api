import aiohttp

from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

from datetime import datetime

import traceback

from .cache import player_search_cache, club_search_cache, player_profile_cache, player_transfers_cache, leagues_search_cache, player_injuries_cache, player_stats_cache, club_profile_cache, club_squad_cache, club_transfers_cache, staff_search_cache, staff_profile_cache, leagues_top_scorers_cache, leagues_clubs_cache, leagues_table_cache, player_injuries_cache, leagues_transfers_overview_cache

BASE_URL = "https://www.transfermarkt.co.uk"

headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

async def fetch_transfermarkt_players(query: str):
    if query in player_search_cache:
        return player_search_cache[query]

    headers = {"User-Agent": "Mozilla/5.0"}
    url = "https://www.transfermarkt.co.uk/spieler/searchSpielerDaten"
    params = {"q": query}

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url, params=params) as response:
            if response.status != 200:
                raise Exception(f"Transfermarkt returned status {response.status}")
            data = await response.json()

    players = []
    for entry in data:
        player_id = entry["id"]
        soup = BeautifulSoup(entry["name"], "html.parser")

        team_tag = soup.find("i")
        team_name = team_tag.get_text(strip=True) if team_tag else "Unknown"

        for tag in soup.find_all("i"):
            tag.extract()  

        player_name = soup.get_text(strip=True)

        if team_name in ["---", "Retired"]:
            team_name = "Retired"

        if not player_name:
            player_name = "Unknown"

        players.append({"id": player_id, "name": player_name, "team": team_name})

    if players:
        player_search_cache[query] = players

    return players

async def fetch_transfermarkt_clubs(query: str):
    if query in club_search_cache:
        return club_search_cache[query]

    headers = {"User-Agent": "Mozilla/5.0"}
    url = "https://www.transfermarkt.co.uk/news/search"
    params = {
        "index": "clubs_lang_new",
        "q": query
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url, params=params) as response:
            if response.status != 200:
                raise Exception(f"Transfermarkt returned status {response.status}")
            data = await response.json()

    clubs = []
    for entry in data:
        club_id = entry["id"]
        name_parts = entry["name"].split("~")
        club_name = name_parts[0].strip()
        
        clubs.append({
            "id": club_id,
            "name": club_name,
            "market_value": entry.get("mw", "Unknown")
        })

    if clubs:
        club_search_cache[query] = clubs

    return clubs

def extract_team_id(url: str) -> str:
    """Extract team ID from various Transfermarkt URL formats"""
    if not url:
        return None
    parts = url.split('/')
    if 'verein' in parts:
        verein_index = parts.index('verein')
        if verein_index + 1 < len(parts):
            return parts[verein_index + 1]
    return None

async def scrape_todays_matches(date: str = None):  
    base_url = "https://www.transfermarkt.co.uk/live/index"
    url = f"{base_url}?datum={date}" if date else base_url
    
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise Exception(f"Failed to fetch data: HTTP {response.status}")
            html = await response.text()
    
    soup = BeautifulSoup(html, 'html.parser')
    matches = []
    
    for competition_section in soup.select('div.kategorie'):
        competition_name = competition_section.select_one('h2 a').get_text(strip=True)
        competition_logo = competition_section.select_one('h2 img.lazy').get('data-src')
        competition_id = competition_section.select_one('h2 a').get('href').split('/')[-1]
        
        for row in competition_section.find_next('table', class_='livescore').select('tr.begegnungZeile'):
            if row.select_one('span.live-ergebnis'):
                status = 'live'
            elif 'finished' in row.select_one('span.matchresult').get('class', []):
                status = 'finished'
            else:
                status = 'scheduled'
            
            home_team_a = row.select_one('td.verein-heim a')
            away_team_a = row.select_one('td.verein-gast a')
            
            match = {
                'match_id': row.get('id'),
                'competition': {
                    'name': competition_name,
                    'stage': row.select_one('td.zeit').get_text(strip=True),
                    'logo': competition_logo,
                    'id': competition_id
                },
                'home_team': {
                    'name': home_team_a.get_text(strip=True) if home_team_a else None,
                    'logo': row.select_one('td.verein-heim img').get('data-src'),
                    'id': extract_team_id(home_team_a.get('href')) if home_team_a else None
                },
                'away_team': {
                    'name': away_team_a.get_text(strip=True) if away_team_a else None,
                    'logo': row.select_one('td.verein-gast img').get('data-src'),
                    'id': extract_team_id(away_team_a.get('href')) if away_team_a else None
                },
                'status': status,
                'time_or_score': row.select_one('span.matchresult').get_text(strip=True),
                'minute': row.select_one('span.live-ergebnis').get_text(strip=True) if status == 'live' else None
            }
            matches.append(match)
    
    return matches

async def scrape_player_profile(player_id: str):   
    if player_id in player_profile_cache:
        return player_profile_cache[player_id]
    
    url = f"https://www.transfermarkt.co.uk/-/profil/spieler/{player_id}"
    
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"Failed to fetch player data: HTTP {response.status}")
                html = await response.text()
        
        soup = BeautifulSoup(html, 'html.parser')
        header = soup.find('header', class_='data-header')
        if not header:
            raise Exception("Player profile header not found")

        name_element = header.find('h1', class_='data-header__headline-wrapper')
        shirt_number_element = header.find('span', class_='data-header__shirt-number')
        shirt_number = shirt_number_element.get_text(strip=True) if shirt_number_element else None
        
        full_name = None
        if name_element:
            name_text = name_element.get_text(strip=False)  
            if shirt_number:
                name_text = name_text.replace(shirt_number, '')
            full_name = re.sub(r'\s+', ' ', name_text).strip()

        is_retired = 'Retired' in html or 'Former International' in html
        is_deceased = bool(header.find('div', class_='dataRibbonRIP'))

        club_link = header.find('span', class_='data-header__club').find('a') if header.find('span', class_='data-header__club') else None
        club_id = club_link['href'].split('/')[-1] if club_link else None
        
        club_logo_img = header.find('a', class_='data-header__box__club-link').find('img') if header.find('a', class_='data-header__box__club-link') else None
        club_logo = None
        if club_logo_img:
            if 'srcset' in club_logo_img.attrs:
                club_logo = club_logo_img['srcset'].split()[0]
            elif 'src' in club_logo_img.attrs:
                club_logo = club_logo_img['src']

        market_value_div = header.find('div', class_='data-header__box--small')
        market_value_text = market_value_div.get_text(' ', strip=True) if market_value_div else None
        market_value = market_value_text.split('Last update:')[0].strip() if market_value_text else None
        market_value_update_element = market_value_div.find('p', class_='data-header__last-update') if market_value_div else None
        market_value_update = market_value_update_element.get_text(strip=True).split("Last update:")[-1].strip() if market_value_update_element else None

        international_data = None
        international_section = header.select_one('ul.data-header__items li:-soup-contains("Current international")') or \
                               header.select_one('ul.data-header__items li:-soup-contains("Former International")')

        if international_section:
            country_link = international_section.find('a')
            country = country_link.get_text(strip=True) if country_link else None
            country_id = country_link['href'].split('/')[-1] if country_link else None
            
            caps_goals_li = international_section.find_next_sibling('li', class_='data-header__label')
            caps = None
            goals = None
            
            if caps_goals_li and "Caps/Goals" in caps_goals_li.get_text():
                caps_goals_links = caps_goals_li.select('a.data-header__content--highlight')
                if len(caps_goals_links) >= 2:
                    caps = caps_goals_links[0].get_text(strip=True)
                    goals = caps_goals_links[1].get_text(strip=True)
            
            international_data = {
                'country': country,
                'country_id': country_id,
                'caps': caps,
                'goals': goals
            }

        def extract_date(label):
            label_element = header.select_one(f'span.data-header__label:-soup-contains("{label}")')
            if label_element:
                return label_element.find_next('span', class_='data-header__content').get_text(strip=True)
            return None

        joined_date = extract_date('Joined:')
        contract_expires = extract_date('Contract expires:')

        birth_date_element = header.find('span', itemprop='birthDate')
        birth_date = None
        age = None
        if birth_date_element:
            birth_date_text = birth_date_element.get_text(strip=True)
            if '(' in birth_date_text:
                birth_date = birth_date_text.split('(')[0].strip()
                age = birth_date_text.split('(')[1].replace(')', '').strip()
            else:
                birth_date = birth_date_text

        position_element = header.select_one('li:-soup-contains("Position:") span.data-header__content')
        position = position_element.get_text(strip=True) if position_element else None

        height_element = header.select_one('li:-soup-contains("Height:") span[itemprop="height"]')
        height = height_element.get_text(strip=True) if height_element else None

        agent_link = header.find('a', href=lambda x: x and 'beraterfirma' in x)
        agent_info = {
            "name": agent_link.get_text(strip=True).replace(".", "").strip() if agent_link else None,
            "id": agent_link['href'].split('/')[-1] if agent_link else None
        }

        trophies = []
        for trophy in header.select('.data-header__success-data'):
            img = trophy.find('img')
            count = trophy.find('span', class_='data-header__success-number')
            if img and count:
                trophies.append({
                    'name': img.get('title', '').replace(' winner', ''),
                    'count': count.get_text(strip=True),
                    'image': img['src'] if 'src' in img.attrs else None
                })

        result = {
            "id": int(player_id),
            "name": full_name,
            "shirt_number": shirt_number.replace("#", ""),
            "club": {
                "name": header.find('span', class_='data-header__club').get_text(strip=True) if header.find('span', class_='data-header__club') else None,
                "id": club_id,
                "logo": club_logo,
                "league": header.find('span', class_='data-header__league').get_text(strip=True) if header.find('span', class_='data-header__league') else None
            },
            "market_value": market_value,
            "market_value_last_update": market_value_update,
            "profile_image": header.find('img', class_='data-header__profile-image')['src'] if header.find('img', class_='data-header__profile-image') else None,
            "position": position,
            "age": age,
            "birth_date": birth_date,
            "birth_place": header.find('span', itemprop='birthPlace').get_text(strip=True) if header.find('span', itemprop='birthPlace') else None,
            "nationality": header.find('span', itemprop='nationality').get_text(strip=True) if header.find('span', itemprop='nationality') else None,
            "height": height,
            "agent": agent_info,
            "joined_date": joined_date,
            "contract_expires": contract_expires,
            "international": international_data,
            "trophies": trophies,
            "status": "deceased" if is_deceased else "retired" if is_retired else "active"
        }

        player_profile_cache[player_id] = {"result": result}

        return {"result": result}

    except Exception as e:
        print(f"Error scraping player {player_id}: {str(e)}")
        raise

async def scrape_player_stats(player_id: str, season: str = None):    

    if (player_id, season) in player_stats_cache:
        return player_stats_cache[(player_id, season)]
    
    if season:
        url = f"https://www.transfermarkt.co.uk/-/leistungsdaten/spieler/{player_id}/plus/0?saison={season}"
    else:
        url = f"https://www.transfermarkt.co.uk/-/leistungsdaten/spieler/{player_id}"
    
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise Exception(f"Failed to fetch player stats: HTTP {resp.status}")
            html = await resp.text()
    
    soup = BeautifulSoup(html, 'html.parser')
    
    stats_table = soup.find('table', class_='items')
    if not stats_table:
        raise Exception("Player stats table not found")
    
    stats_data = {
        "player_id": player_id,
        "season": season if season else "all-time",
        "total": None,
        "competitions": []
    }
    
    tfoot = stats_table.find('tfoot')
    if tfoot:
        total_row = tfoot.find('tr')
        if total_row and "Total" in total_row.get_text():
            total_cells = total_row.find_all('td')
            if len(total_cells) >= 8:
                stats_data["total"] = {
                    "appearances": total_cells[2].get_text(strip=True) if total_cells[2].get_text(strip=True) else "0",
                    "goals": total_cells[3].get_text(strip=True) if total_cells[3].get_text(strip=True) else "0",
                    "assists": total_cells[4].get_text(strip=True) if total_cells[4].get_text(strip=True) else "0",
                    "yellow_cards": total_cells[5].get_text(strip=True) if total_cells[5].get_text(strip=True) else "0",
                    "second_yellow_cards": total_cells[6].get_text(strip=True) if total_cells[6].get_text(strip=True) else "0",
                    "red_cards": total_cells[7].get_text(strip=True) if total_cells[7].get_text(strip=True) else "0",
                    "minutes_played": total_cells[8].get_text(strip=True) if len(total_cells) > 8 and total_cells[8].get_text(strip=True) else "0"
                }
    
    tbody = stats_table.find('tbody')
    if tbody:
        for row in tbody.find_all('tr', class_=['odd', 'even']):
            cells = row.find_all('td')
            if len(cells) >= 9:
                competition_logo = cells[0].find('img')['src'] if cells[0].find('img') else None
                competition_name = cells[1].get_text(strip=True)
                competition_id = None
                competition_link = cells[1].find('a')
                if competition_link and 'href' in competition_link.attrs:
                    competition_id = competition_link['href'].split('/')[-1]
                
                stats_data["competitions"].append({
                    "competition": {
                        "name": competition_name,
                        "id": competition_id,
                        "logo": competition_logo
                    },
                    "appearances": cells[2].get_text(strip=True) if cells[2].get_text(strip=True) else "0",
                    "goals": cells[3].get_text(strip=True) if cells[3].get_text(strip=True) else "0",
                    "assists": cells[4].get_text(strip=True) if cells[4].get_text(strip=True) else "0",
                    "yellow_cards": cells[5].get_text(strip=True) if cells[5].get_text(strip=True) else "0",
                    "second_yellow_cards": cells[6].get_text(strip=True) if cells[6].get_text(strip=True) else "0",
                    "red_cards": cells[7].get_text(strip=True) if cells[7].get_text(strip=True) else "0",
                    "minutes_played": cells[8].get_text(strip=True) if cells[8].get_text(strip=True) else "0"
                })
    
    player_stats_cache[(player_id, season)] = stats_data
    return stats_data

async def get_team_name(team_id: str) -> str:
    """
    Fetches and returns the official team name from Transfermarkt.
    
    Args:
        team_id: The team ID from Transfermarkt (e.g., '11' for Arsenal)
        
    Returns:
        The team name (e.g., "Arsenal FC")
    """
    url = f"https://www.transfermarkt.co.uk/-/startseite/verein/{team_id}"

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"HTTP Error {response.status}")
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                header = soup.find('h1', class_='data-header__headline-wrapper')
                if not header:
                    raise Exception("Team page not found or invalid structure")
                
                team_name = header.get_text(strip=True)
                return team_name
    
    except Exception as e:
        raise Exception(f"Failed to fetch team name: {str(e)}")
    
async def get_player_transfers(player_id: str):
    """
    Fetches a player's transfer history from Transfermarkt API and enriches with team names.
    
    Args:
        player_id: Transfermarkt player ID (e.g., '418560' for Haaland)
        
    Returns:
        {
            "player_id": str,
            "transfers": List[Dict] (each transfer with full details),
            "current_club": Dict (current club info if available)
        }
    """
    if player_id in player_transfers_cache:
        return player_transfers_cache[player_id]
    
    api_url = f"https://tmapi-alpha.transfermarkt.technology/transfer/history/player/{player_id}"
    
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(api_url) as response:
                if response.status != 200:
                    return []
                transfer_data = await response.json()
                
                if not transfer_data.get('success'):
                    raise Exception("Transfer API returned unsuccessful response")
                
                transfers = []
                for transfer in transfer_data['data']['history']['terminated']:
                    source_club_name = await get_team_name(transfer['transferSource']['clubId'])
                    dest_club_name = await get_team_name(transfer['transferDestination']['clubId'])
                    
                    transfers.append({
                        "transfer_id": transfer['id'],
                        "date": transfer['details']['date'],
                        "season": transfer['details']['season']['display'],
                        "age": transfer['details']['age'],
                        "market_value": transfer['details']['marketValue']['compact'],
                        "fee": transfer['details']['fee']['compact'],
                        "from": {
                            "club_id": transfer['transferSource']['clubId'],
                            "club_name": source_club_name,
                            "country_id": transfer['transferSource']['countryId'],
                            "competition_id": transfer['transferSource']['competitionId']
                        },
                        "to": {
                            "club_id": transfer['transferDestination']['clubId'],
                            "club_name": dest_club_name,
                            "country_id": transfer['transferDestination']['countryId'],
                            "competition_id": transfer['transferDestination']['competitionId']
                        },
                        "contract_until": transfer['details']['contractUntilDate'],
                        "type": transfer['typeDetails']['type'],
                        "relative_url": transfer['relativeUrl']
                    })
                
                current_club = None
                if transfer_data['data'].get('currentClub'):
                    current_club_id = transfer_data['data']['currentClub']['clubId']
                    current_club_name = await get_team_name(current_club_id)
                    current_club = {
                        "club_id": current_club_id,
                        "club_name": current_club_name,
                        "country_id": transfer_data['data']['currentClub']['countryId'],
                        "competition_id": transfer_data['data']['currentClub']['competitionId'],
                        "joined_date": transfer_data['data']['currentClub']['joined'],
                        "contract_until": transfer_data['data']['currentClub']['contractUntil']
                    }
                
                returnData = {
                    "player_id": player_id,
                    "transfers": transfers,
                    "current_club": current_club
                }

                player_transfers_cache[player_id] = returnData
                return returnData
                
    except Exception as e:
        raise Exception(f"Failed to fetch transfer history: {str(e)}")

async def scrape_club_profile(club_id: str):
    """
    Scrapes detailed club profile information from Transfermarkt.
    
    Args:
        club_id: Transfermarkt club ID (e.g., '11' for Arsenal)
        
    Returns:
        Dictionary containing all extracted club data
    """
    if club_id in club_profile_cache:
        return club_profile_cache[club_id]
    
    url = f"https://www.transfermarkt.co.uk/-/startseite/verein/{club_id}"
    
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"HTTP Error {response.status}")
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                header = soup.find('header', class_='data-header')
                if not header:
                    raise Exception("Club profile header not found")
                
                name_element = header.find('h1', class_='data-header__headline-wrapper')
                club_name = name_element.get_text(strip=True) if name_element else None
                
                logo_element = header.find('img', src=lambda x: x and 'wappen/head' in x)
                club_logo = logo_element['src'] if logo_element else None
                
                trophies = []
                for trophy in header.select('.data-header__success-data'):
                    img = trophy.find('img')
                    count = trophy.find('span', class_='data-header__success-number')
                    if img and count:
                        trophies.append({
                            'title': img.get('title', ''),
                            'count': count.get_text(strip=True),
                            'image': img.get('data-src', '')
                        })
                
                league_info = {}
                league_link = header.find('span', class_='data-header__club').find('a')
                if league_link:
                    league_info = {
                        'name': league_link.get_text(strip=True),
                        'id': league_link['href'].split('/')[-1]
                    }
                
                info_boxes = header.find_all('div', class_='data-header__details')
                
                squad_size = None
                avg_age = None
                foreigners_count = None
                foreigners_percentage = None
                national_players = None
                stadium_name = None
                stadium_capacity = None
                transfer_record = None
                
                for box in info_boxes:
                    items = box.find_all('li', class_='data-header__label')
                    for item in items:
                        text = item.get_text(strip=True)
                        
                        if 'Squad size:' in text:
                            squad_size = item.find_next('span', class_='data-header__content').get_text(strip=True)
                        elif 'Average age:' in text:
                            avg_age = item.find_next('span', class_='data-header__content').get_text(strip=True)
                        elif 'Foreigners:' in text:
                            foreigners_count = item.find('a').get_text(strip=True) if item.find('a') else None
                            foreigners_percentage = item.find('span', class_='tabellenplatz').get_text(strip=True) if item.find('span', class_='tabellenplatz') else None
                        elif 'National team players:' in text:
                            national_players = item.find('a').get_text(strip=True) if item.find('a') else None
                        elif 'Stadium:' in text:
                            stadium_name = item.find('a').get('title') if item.find('a') else None
                            stadium_capacity = item.find('span', class_='tabellenplatz').get_text(strip=True) if item.find('span', class_='tabellenplatz') else None
                        elif 'Current transfer record:' in text:
                            transfer_record = item.find('a').get_text(strip=True) if item.find('a') else None
                
                market_value_a = header.find('a', class_='data-header__market-value-wrapper')
                if market_value_a:
                    market_value_text = market_value_a.get_text(' ', strip=True)
                    market_value_p = market_value_a.find('p', class_='data-header__last-update')
                    market_value = {
                        'value': market_value_text.replace(market_value_p.get_text(strip=True), '').strip() if market_value_p else market_value_text
                    }
                else:
                    market_value = {
                        'value': None,
                        'last_update': None
                    }
                
                returnData = {
                    'club_id': club_id,
                    'name': club_name,
                    'logo': club_logo,
                    'trophies': trophies,
                    'league': league_info,
                    'squad_info': {
                        'size': squad_size,
                        'average_age': avg_age,
                        'foreigners': {
                            'count': foreigners_count,
                            'percentage': foreigners_percentage
                        },
                        'national_players': national_players
                    },
                    'stadium': {
                        'name': stadium_name,
                        'capacity': stadium_capacity
                    },
                    'transfer_record': transfer_record,
                    'market_value': market_value
                }

                club_profile_cache[club_id] = returnData
                return returnData
    
    except Exception as e:
        raise Exception(f"Failed to scrape club profile: {str(e)}")
    
async def scrape_club_squad(club_id: str):
    """
    Scrapes squad information from Transfermarkt club page using the correct URL structure
    while maintaining the same BeautifulSoup extraction logic
    
    Args:
        club_id: Transfermarkt club ID (e.g., '11' for Arsenal)
        
    Returns:
        List of player dictionaries with complete details
    """
    if club_id in club_squad_cache:
        return club_squad_cache[club_id]
    
    url = f"https://www.transfermarkt.co.uk/-/startseite/verein/{club_id}"
    
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"HTTP Error {response.status}")
                
                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")
                players = []
                
                for row in soup.select("table.items tr")[1:]: 
                    cols = row.find_all("td")
                    if len(cols) < 8: 
                        continue

                    try:
                        number = cols[0].text.strip()
                        
                        image_url = cols[2].select_one("img")
                        image_url = image_url["data-src"] if image_url and "data-src" in image_url.attrs else None
                        
                        player_link_tag = cols[3].select_one("a")
                        player_name = player_link_tag.text.strip() if player_link_tag else None
                        player_id = player_link_tag["href"].split("/")[-1] if player_link_tag else None
                        
                        position = cols[4].text.strip()
                        
                        dob = cols[5].text.strip()
                        
                        nationality_img = cols[6].select_one("img")
                        nationality = nationality_img["title"] if nationality_img else None
                        
                        market_value = cols[7].text.strip()
                        
                        injury_tag = player_link_tag.select_one("span.verletzt-table.icons_sprite") if player_link_tag else None
                        injury_status = injury_tag["title"] if injury_tag else None

                        players.append({
                            "player_id": player_id,
                            "player_name": player_name,
                            "position": position,
                            "number": number,
                            "dob": dob,
                            "market_value": market_value,
                            "nationality": nationality,
                            "image": image_url,
                            "injury_status": injury_status
                        })
                    except Exception as e:
                        print(f"Error processing player row: {e}")
                        continue
                
                club_squad_cache[club_id] = players
                return players
    
    except Exception as e:
        print(traceback.format_exc())
        raise Exception(f"Failed to scrape squad: {str(e)}")

async def scrape_transfers(club_id: int, season: int):
    """Scrape transfers for a specific team and season"""
    if (club_id, season) in club_transfers_cache:
        return club_transfers_cache[(club_id, season)]

    transfers_url = f"https://www.transfermarkt.co.uk/-/transfers/verein/{club_id}/saison_id/{season}"
    
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(transfers_url) as response:
                if response.status != 200:
                    print(f"Failed to fetch: HTTP {response.status}")
                    return []
                
                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")
                transfers = []

                for table_type in ["Arrivals", "Departures"]:
                    table_header = soup.find("h2", string=lambda text: text and table_type in text)
                    if table_header:
                        table = table_header.find_next("table")
                        if table:
                            for row in table.select("tbody > tr"):
                                transfer = await process_transfer_row(row, table_type.lower()[:-1])
                                if transfer:
                                    transfers.append(transfer)

                club_transfers_cache[(club_id, season)] = transfers
                return transfers
    except Exception as e:
        print(f"Error scraping transfers: {str(e)}")
        return []

async def process_transfer_row(row, transfer_type):
    """Process a single transfer row with improved error handling"""
    try:
        player_name_elem = row.select_one("td.hauptlink a[title]")
        if not player_name_elem:
            return None

        player_name = player_name_elem.text.strip()
        player_href = player_name_elem.get("href", "")
        player_id = player_href.split("/")[-1] if player_href else None
        
        age_elem = row.select_one("td.zentriert:not([colspan])")
        age = int(age_elem.text.strip()) if age_elem and age_elem.text.strip().isdigit() else None
        
        nationality_elem = row.select_one("td.zentriert img.flaggenrahmen")
        nationality = nationality_elem.get("title") if nationality_elem else None
        
        position_elem = row.select_one("td table.inline-table tr:nth-of-type(2) td")
        position = position_elem.text.strip() if position_elem else None
        
        club_elem = row.select_one("td img.tiny_wappen")
        club = club_elem.get("title") if club_elem else None
        
        fee_elem = row.select_one("td.rechts.hauptlink a")
        fee = "Free"
        loan_end_date = None
        
        if fee_elem:
            fee_text = fee_elem.text.strip()
            if "End of loan" in fee_text:
                loan_end_date_elem = row.select_one("td.rechts.hauptlink i")
                loan_end_date = loan_end_date_elem.text.strip() if loan_end_date_elem else None
                fee = "Loan Transfer"
            elif "loan" in fee_text.lower():
                fee = "Loan Transfer"
            elif "€" in fee_text:
                fee = fee_text.replace("€", "€ ").replace("\u20ac", "€")
                fee = fee.replace("m", "M").replace("bn", "B").strip()
        
        player_logo_elem = row.select_one("img.bilderrahmen-fixed")
        player_logo = player_logo_elem.get("data-src") if player_logo_elem else None

        return {
            "player_id": player_id,
            "player_name": player_name,
            "age": age,
            "nationality": nationality,
            "position": position,
            "club": club,
            "fee": fee,
            "type": transfer_type,
            "loan_end_date": loan_end_date,
            "player_image": player_logo
        }
    except Exception as e:
        print(f"Error processing transfer row: {str(e)}")
        return None
    
async def scrape_transfers():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/113.0.0.0 "
            "Safari/537.36"
        ),
    }
    url = "https://www.transfermarkt.co.uk/transfers/neuestetransfers/statistik/plus/?plus=0&galerie=0&wettbewerb_id=alle&land_id=&selectedOptionInternalType=nothingSelected&minMarktwert=500.000&maxMarktwert=500.000.000&minAbloese=0&maxAbloese=500.000.000&top10=Top+10+leagues"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            response.raise_for_status()  
            content = await response.text()  

            soup = BeautifulSoup(content, 'html.parser')
            table = soup.find('table', {'class': 'items'}) 
            transfers = []

            if table:
                rows = table.find_all('tr')[1:]  

                for row in rows:
                    columns = row.find_all('td')
                    if len(columns) < 15:  
                        continue

                    player_info = {
                        'name': '',
                        'position': '',
                        'age': '',
                        'nationality': '',
                        'current_club': '',
                        'current_club_league': '',
                        'current_club_nationality': '',
                        'previous_club': '',
                        'previous_club_league': '',
                        'previous_club_nationality': '',
                        'transfer_fee': '',
                        'player_logo': '',
                        'date': int(datetime.now().timestamp()),
                        'player_id': ''
                    }

                    player_info_table = columns[0].find('table', {'class': 'inline-table'})
                    if player_info_table:
                        info_rows = player_info_table.find_all('tr')
                        if len(info_rows) > 1:
                            name_td = info_rows[0].find('td', {'class': 'hauptlink'})
                            if name_td:
                                player_info['name'] = name_td.get_text(strip=True)
                                # Extract player ID from href
                                name_link = name_td.find('a')
                                if name_link and 'href' in name_link.attrs:
                                    href = name_link['href']
                                    player_info['player_id'] = href.split('/')[-1]

                            position_td = info_rows[1].find('td')
                            if position_td:
                                player_info['position'] = position_td.get_text(strip=True)

                            player_logo_img = info_rows[0].find('img')
                            if player_logo_img:
                                player_info['player_logo'] = player_logo_img.get('data-src', '')

                    player_info['age'] = columns[4].get_text(strip=True)

                    nationality_img = columns[5].find('img')
                    if nationality_img:
                        player_info['nationality'] = nationality_img.get('title', 'N/A')

                    current_club_table = columns[10].find('table', {'class': 'inline-table'})
                    if current_club_table:
                        current_club_rows = current_club_table.find_all('tr')
                        if len(current_club_rows) > 1:
                            current_club_name_td = current_club_rows[0].find('td', {'class': 'hauptlink'})
                            if current_club_name_td:
                                player_info['current_club'] = current_club_name_td.get_text(strip=True)
                            current_club_country = current_club_rows[1].find('img', {'class': 'flaggenrahmen'})
                            if current_club_country:
                                player_info['current_club_nationality'] = current_club_country.get('title', '').strip()

                            current_club_league_td = current_club_rows[1].find('td')
                            if current_club_league_td:
                                player_info['current_club_league'] = current_club_league_td.get_text(strip=True)

                    previous_club_table = columns[6].find('table', {'class': 'inline-table'})
                    if previous_club_table:
                        previous_club_rows = previous_club_table.find_all('tr')
                        if len(previous_club_rows) > 1:
                            previous_club_name_td = previous_club_rows[0].find('td', {'class': 'hauptlink'})
                            if previous_club_name_td:
                                player_info['previous_club'] = previous_club_name_td.get_text(strip=True)

                            previous_club_league_td = previous_club_rows[1].find('td')
                            if previous_club_league_td:
                                player_info['previous_club_league'] = previous_club_league_td.get_text(strip=True)

                            previous_club_nationality_img = previous_club_rows[1].find('img', {'class': 'flaggenrahmen'})
                            if previous_club_nationality_img:
                                player_info['previous_club_nationality'] = previous_club_nationality_img.get('title', '').strip()

                    transfer_fee_a = columns[14].find('a')
                    if transfer_fee_a:
                        player_info['transfer_fee'] = transfer_fee_a.get_text(strip=True)
                    else:
                        transfer_fee_span = columns[14].find('span')
                        if transfer_fee_span:
                            player_info['transfer_fee'] = transfer_fee_span.get_text(strip=True)

                    transfers.append(player_info)

            return transfers
    
async def scrape_transfermarkt_leagues(search_query: str):
    if search_query in leagues_search_cache:
        return leagues_search_cache[search_query]
    
    url = f"https://www.transfermarkt.co.uk/schnellsuche/ergebnis/schnellsuche?query={search_query.replace(' ', '+')}"
    
    try:
        async with aiohttp.ClientSession(headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }) as session:
            async with session.get(url) as response:
                response.raise_for_status()
                html = await response.text()
                
                soup = BeautifulSoup(html, 'html.parser')
                leagues = []
                
                for table in soup.find_all('table', class_='items'):
                    headers = [th.get_text(strip=True) for th in table.find_all('th')]
                    if 'Competition' in headers and 'Country' in headers:
                        for row in table.find_all('tr', class_=['odd', 'even']):
                            cols = row.find_all('td')
                            if len(cols) >= 8:
                                league_link = cols[1].find('a', href=True)
                                league_url = league_link['href'] if league_link else None
                                league_code = None
                                
                                if league_url:
                                    parts = league_url.split('/')
                                    if len(parts) >= 5 and parts[-2] == 'wettbewerb':
                                        league_code = parts[-1]
                                
                                leagues.append({
                                    'name': league_link['title'] if league_link else None,
                                    'code': league_code,  # Added league code
                                    'country': cols[2].find('img')['title'] if cols[2].find('img') else None,
                                    'clubs': cols[3].get_text(strip=True),
                                    'players': cols[4].get_text(strip=True),
                                    'total_value': cols[5].get_text(strip=True),
                                    'mean_value': cols[6].get_text(strip=True),
                                    'continent': cols[7].get_text(strip=True),
                                    'logo': cols[0].find('img')['src'] if cols[0].find('img') else None  # Added league logo
                                })
                        break

                leagues_search_cache[search_query] = leagues
                return leagues
                
    except Exception as e:
        print(f"Error scraping leagues: {e}")
        return []

async def fetch_player_injuries(player_id: str):
    """
    Fetches injury history for a player by their Transfermarkt ID
    Returns a list of dictionaries containing injury data
    """
    if player_id in player_injuries_cache:
        return player_injuries_cache[player_injuries_cache]
    
    url = f"{BASE_URL}/-/verletzungen/spieler/{player_id}"
    
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                response.raise_for_status()
                html = await response.text()
                
                soup = BeautifulSoup(html, 'html.parser')
                table = soup.find('table', {'class': 'items'})
                
                if not table:
                    return []
                
                injuries = []
                for row in table.find_all('tr', class_=['odd', 'even']):
                    cols = row.find_all('td')
                    if len(cols) < 6:
                        continue
                    
                    team_elements = cols[5].find_all('a')
                    teams = []
                    for team in team_elements:
                        if 'verein' in team['href']:
                            teams.append({
                                'name': team.get('title'),
                                'type': 'club' if 'verein' in team['href'] else 'national team',
                                'image': team.find('img')['src'] if team.find('img') else None
                            })
                    
                    games_missed = cols[5].get_text(strip=True)
                    if cols[5].find('span'):
                        games_missed = cols[5].find('span').get_text(strip=True)
                    
                    injuries.append({
                        'season': cols[0].get_text(strip=True),
                        'injury': cols[1].get_text(strip=True),
                        'from_date': cols[2].get_text(strip=True),
                        'until_date': cols[3].get_text(strip=True),
                        'duration': cols[4].get_text(strip=True),
                        'games_missed': games_missed,
                        'teams_affected': teams
                    })

                player_injuries_cache[player_id] = injuries
                return injuries
                
    except Exception as e:
        print(f"Error fetching injuries for player {player_id}: {e}")
        return []
    
async def search_club_staff(query: str):
    """
    Search for club staff (managers, coaches) on Transfermarkt
    
    Args:
        query: Name of the staff member to search for (e.g. "Mikel Arteta")
    
    Returns:
        List of dictionaries containing staff information with keys:
        - name: Staff member's name
        - position: Their role (Manager, Coach, etc.)
        - nationality: Country flag
        - club: Current club
        - club_logo: URL of club logo
        - contract_end: Contract expiration date
        - profile_url: URL to staff profile
        - photo_url: URL to staff photo
    """
    if query in staff_search_cache:
        return staff_search_cache[query]
    
    url = f"{BASE_URL}/schnellsuche/ergebnis/schnellsuche?query={query.replace(' ', '+')}"
    
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                response.raise_for_status()
                html = await response.text()
                
                soup = BeautifulSoup(html, 'html.parser')
                staff_list = []
                
                for table in soup.find_all('table', class_='items'):
                    staff_headers = [th.get_text(strip=True) for th in table.find_all('th')]
                    if 'Name' in staff_headers and 'Club' in staff_headers and 'Contract until' in staff_headers:
                        for row in table.find_all('tr', class_=['odd', 'even']):
                            staff_data = extract_staff_data(row)
                            if staff_data:
                                staff_list.append(staff_data)

                staff_search_cache[query] = staff_list
                return staff_list
                
    except Exception as e:
        print(f"Error searching for staff: {e}")
        return []

def extract_staff_data(row):
    """Extracts staff data from a table row with the new structure including ID"""
    try:
        profile_link = row.find('a', href=True, title=True)
        if not profile_link:
            return None

        href = profile_link.get('href', '')
        staff_id = href.split('/')[-1] if href and href.split('/') else None
        
        name = profile_link.get('title', '').strip()
        
        photo_img = row.find('img', class_='bilderrahmen-fixed')
        photo_url = photo_img['src'] if photo_img else None
        
        position_td = row.find_all('td', class_='rechts')
        position = position_td[0].get_text(strip=True) if position_td else None
        
        nationality_img = row.find('img', class_='flaggenrahmen')
        nationality = nationality_img['title'] if nationality_img else None
        
        club_link = row.find('a', href=lambda x: x and '/verein/' in x)
        club = club_link.get('title') if club_link else None
        
        club_img = row.find('img', class_='tiny_wappen')
        club_logo = club_img['src'] if club_img else None
        
        contract_end = position_td[1].get_text(strip=True) if len(position_td) > 1 else None
        
        return {
            'id': staff_id,  
            'name': name,
            'position': position,
            'nationality': nationality,
            'club': club,
            'club_logo': club_logo,
            'contract_end': contract_end,
            'profile_url': urljoin(BASE_URL, profile_link['href']),
            'photo_url': photo_url
        }
        
    except Exception as e:
        print(f"Error extracting staff data: {e}")
        return None

async def get_staff_profile_scraping(staff_id: str):
    """
    Get detailed profile information for a staff member (manager/coach)
    
    Args:
        staff_id: The Transfermarkt ID of the staff member (e.g. '47620' for Mikel Arteta)
    
    Returns:
        Dictionary containing clean, properly structured staff profile information
    """
    if staff_id in staff_profile_cache:
        return staff_profile_cache[staff_id]

    url = f"{BASE_URL}/-/profil/trainer/{staff_id}"
    
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                response.raise_for_status()
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                profile_data = {
                    'personal_info': {},
                    'coaching_info': {},
                    'current_club': {},
                    'agent': None
                }
                
                info_box = soup.find('div', class_='data-header__info-box')
                if info_box:
                    for item in info_box.find_all('li', class_='data-header__label'):
                        label = item.get_text(strip=True).split(':')[0].strip()
                        content = item.find('span', class_='data-header__content')
                        if not content:
                            continue
                            
                        content_text = content.get_text(strip=True)
                        
                        if 'Date of birth' in label:
                            dob, age = content_text.split('(')
                            profile_data['personal_info']['date_of_birth'] = dob.strip()
                            profile_data['personal_info']['age'] = age.replace(')', '').strip()
                        elif 'Citizenship' in label:
                            profile_data['personal_info']['citizenship'] = content_text
                            flag = content.find('img')
                            if flag:
                                profile_data['personal_info']['citizenship_flag'] = flag['src']
                        elif 'Im Amt seit' in label:
                            profile_data['coaching_info']['appointed'] = content_text
                        elif 'Vertrag bis' in label:
                            profile_data['coaching_info']['contract_expires'] = content_text
                        elif 'Avg. term' in label:
                            profile_data['coaching_info']['avg_term'] = content_text
                        elif 'Preferred formation' in label:
                            profile_data['coaching_info']['preferred_formation'] = content_text
                
                spielerdaten = soup.find('div', class_='spielerdaten')
                if spielerdaten:
                    table = spielerdaten.find('table', class_='auflistung')
                    if table:
                        for row in table.find_all('tr'):
                            th = row.find('th')
                            td = row.find('td')
                            if not th or not td:
                                continue
                                
                            key = th.get_text(strip=True).split(':')[0].strip().lower().replace(' ', '_')
                            value = td.get_text(strip=True)
                            
                            if 'name_in_home_country' in key:
                                profile_data['personal_info']['full_name'] = value
                            elif 'place_of_birth' in key:
                                profile_data['personal_info']['place_of_birth'] = value.split('  ')[0].strip()
                                flag = td.find('img')
                                if flag:
                                    profile_data['personal_info']['birth_country_flag'] = flag['src']
                            elif 'coaching_licence' in key:
                                profile_data['coaching_info']['licence'] = value
                            elif 'agent' in key:
                                agent_link = td.find('a')
                                if agent_link:
                                    profile_data['agent'] = {
                                        'name': agent_link.get_text(strip=True),
                                        'url': urljoin(BASE_URL, agent_link['href'])
                                    }
                
                current_club = soup.find('div', class_='data-header__club-info')
                if current_club:
                    club_link = current_club.find('a')
                    if club_link:
                        profile_data['current_club']['name'] = club_link.get('title')
                        profile_data['current_club']['url'] = urljoin(BASE_URL, club_link['href'])
                        club_img = club_link.find('img')
                        if club_img:
                            profile_data['current_club']['logo'] = club_img['src']
                
                if not profile_data['agent']:
                    del profile_data['agent']
                
                profile_data['profile_url'] = url
                staff_profile_cache[staff_id] = profile_data
                return profile_data
                
    except Exception as e:
        print(f"Error fetching staff profile {staff_id}: {e}")
        return None

async def get_league_top_scorers(league_code: str, season: str):
    """
    Get top scorers for a specific league and season
    
    Args:
        league_code: League code (e.g. 'GB1' for Premier League)
        season: Season year (e.g. '2024')
    
    Returns:
        List of dictionaries containing top scorer data
    """
    if (league_code, season) in leagues_top_scorers_cache:
        return leagues_top_scorers_cache[(league_code, season)]
    
    url = f"{BASE_URL}/-/torschuetzenliste/wettbewerb/{league_code}/plus/?saison_id={season}"
    
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                response.raise_for_status()
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                scorers = []
                table = soup.find('table', {'class': 'items'})
                
                if not table:
                    return []
                
                for row in table.find_all('tr', class_=['odd', 'even']):
                    cols = row.find_all('td')
                    
                    rank = cols[0].get_text(strip=True)
                    
                    player_table = cols[1].find('table', class_='inline-table')
                    if not player_table:
                        continue
                        
                    player_link = player_table.find('a', href=True)
                    player_name = player_link.get('title') if player_link else None
                    player_url = urljoin(BASE_URL, player_link['href']) if player_link else None
                    position = player_table.find_all('tr')[1].get_text(strip=True) if len(player_table.find_all('tr')) > 1 else None
                    
                    flags = cols[5].find_all('img', class_='flaggenrahmen')
                    nationality = [flag['title'] for flag in flags if flag.has_attr('title')]
                    
                    age = cols[6].get_text(strip=True)
                    
                    club_link = cols[7].find('a')
                    club = club_link.get('title') if club_link else None
                    club_logo = club_link.find('img')['src'] if club_link and club_link.find('img') else None
                    
                    appearances = cols[8].get_text(strip=True)
                    
                    goals = cols[9].get_text(strip=True)
                    
                    photo_img = cols[1].find('img', class_='bilderrahmen-fixed')
                    photo_url = photo_img.get('data-src') or photo_img.get('src') if photo_img else None
                    
                    scorers.append({
                        'rank': rank,
                        'name': player_name,
                        'position': position,
                        'nationality': nationality,
                        'age': age,
                        'club': club,
                        'club_logo': club_logo,
                        'appearances': appearances,
                        'goals': goals,
                        'player_url': player_url,
                        'photo_url': photo_url
                    })
                
                leagues_top_scorers_cache[(league_code, season)] = scorers
                return scorers
                
    except Exception as e:
        print(f"Error fetching top scorers for {league_code} season {season}: {e}")
        return []
    
async def get_league_clubs_request(league_code: str):
    """
    Get league overview data including club statistics
    
    Args:
        league_code: League code (e.g. 'GB1' for Premier League)
    
    Returns:
        List of dictionaries containing club data with:
        - rank: Position in table
        - name: Club name
        - logo: Club logo URL
        - squad_size: Number of players
        - avg_age: Average squad age
        - foreigners: Number of foreign players
        - avg_market_value: Average player market value
        - total_market_value: Total squad market value
        - club_url: Club profile URL
    """
    if league_code in leagues_clubs_cache:
        return leagues_clubs_cache[league_code]
    
    url = f"{BASE_URL}/-/startseite/wettbewerb/{league_code}"
    
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                response.raise_for_status()
                html = await response.text()
                
                soup = BeautifulSoup(html, 'html.parser')
                clubs = []
                table = soup.find('table', {'class': 'items'})
                
                if not table:
                    return []
                
                for row in table.find_all('tr', class_=['odd', 'even']):
                    cols = row.find_all('td')
                    if len(cols) < 7:  
                        continue
                    
                    logo_link = cols[0].find('a')
                    logo = logo_link.find('img')['src'] if logo_link and logo_link.find('img') else None
                    
                    name_link = cols[1].find('a')
                    name = name_link.get('title') if name_link else None
                    club_url = urljoin(BASE_URL, name_link['href']) if name_link else None
                    
                    clubs.append({
                        'rank': len(clubs) + 1,  
                        'club_id': club_url.split("/")[-3] if club_url else None,
                        'name': name,
                        'logo': logo,
                        'squad_size': cols[2].get_text(strip=True),
                        'avg_age': cols[3].get_text(strip=True),
                        'foreigners': cols[4].get_text(strip=True),
                        'avg_market_value': cols[5].get_text(strip=True),
                        'total_market_value': cols[6].get_text(strip=True),
                        'club_url': club_url
                    })
                leagues_clubs_cache[league_code] = clubs
                return clubs
                
    except Exception as e:
        print(f"Error fetching league overview for {league_code}: {e}")
        return []

async def get_league_transfers_overview_request(league_code: str, season: int):
    """
    Get transfer data for a specific league and season, grouped by team
    
    Args:
        league_code: League code (e.g. 'GB1' for Premier League)
        season: Season year (e.g. '2025')
    
    Returns:
        List of dictionaries containing team transfer data with:
        - team_name: Name of the club
        - team_logo: URL of club logo
        - team_url: URL to club's transfer page
        - transfers: List of transfers (both incoming and outgoing)
    """
    if (league_code, season) in leagues_transfers_overview_cache:
        return leagues_transfers_overview_cache[(league_code, season)]
    
    url = f"{BASE_URL}/-/transfers/wettbewerb/{league_code}/plus/?saison_id={season}&leihe=1&intern=0&intern=1"
    
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                response.raise_for_status()
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                teams_data = []
                team_boxes = soup.find_all('div', class_='box')
                
                for box in team_boxes:
                    team_header = box.find('h2', class_='content-box-headline')
                    if not team_header:
                        continue
                        
                    team_link = team_header.find('a')

                    if not team_link:
                        continue

                    team_name = team_link.get('title').replace('Array', '').strip() if team_link else None
                    team_url = urljoin(BASE_URL, team_link['href']) if team_link else None
                    
                    logo_img = team_header.find('img')
                    team_logo = logo_img['src'] if logo_img else None
                    
                    transfers = []
                    table = box.find('table')
                    if table:
                        for row in table.find_all('tr')[1:]: 
                            cols = row.find_all('td')
                            if len(cols) < 9:  
                                continue

                            player_link = cols[0].find('a')
                            player_name = player_link.get('title') if player_link else None
                            player_url = urljoin(BASE_URL, player_link['href']) if player_link else None
                            
                            age = cols[1].get_text(strip=True)
                            
                            nationality_img = cols[2].find('img')
                            nationality = nationality_img['title'] if nationality_img else None
                            
                            position = cols[3].get_text(strip=True)
                            short_position = cols[4].get_text(strip=True)
                            market_value = cols[5].get_text(strip=True)
                            
                            prev_club_link = cols[7].find('a')
                            prev_club = prev_club_link.get_text(strip=True) if prev_club_link else None
                            prev_club_url = urljoin(BASE_URL, prev_club_link['href']) if prev_club_link else None
                            
                            prev_club_img = cols[6].find('img')
                            prev_club_logo = prev_club_img['src'] if prev_club_img else None
                            
                            fee = cols[8].get_text(strip=False)
                            
                            transfers.append({
                                'player_id':player_url.split("/")[-1] if player_url else None,
                                'player_name': player_name,
                                'player_url': player_url,
                                'age': age,
                                'nationality': nationality,
                                'position': position,
                                'short_position': short_position,
                                'market_value': market_value,
                                'previous_club': prev_club,
                                'previous_club_logo': prev_club_logo,
                                'previous_club_url': prev_club_url,
                                'fee': fee,
                                'transfer_type': 'in'  
                            })
                    
                    teams_data.append({
                        'team_id': team_url.split("/")[-3] if team_url else None,
                        'team_name': team_name,
                        'team_logo': team_logo,
                        'team_url': team_url,
                        'transfers': transfers
                    })

                leagues_transfers_overview_cache[(league_code, season)] = teams_data
                return teams_data
                
    except Exception as e:
        print(f"Error fetching transfers for {league_code} season {season}: {e}")
        return []
    
async def get_league_table_request(league_code: str, season: str):
    """
    Get league table for a specific league and season
    
    Args:
        league_code: League code (e.g. 'GB1' for Premier League)
        season: Season year (e.g. '2025')
    
    Returns:
        List of dictionaries containing team data in the league table
    """
    if (league_code, season) in leagues_table_cache:
        return leagues_table_cache[(league_code, season)]
    
    url = f"{BASE_URL}/-/tabelle/wettbewerb/{league_code}/saison_id/{season}"
    
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                response.raise_for_status()
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                table = []
                
                table_element = soup.find('table', class_='items')
                if not table_element:
                    return []
                
                rows = table_element.find_all('tr', class_=lambda x: x != 'zeile-unterschiedliche-tabellenfarben')
                
                for row in rows:
                    if not row.find('td', class_='rechts'):
                        continue
                    
                    pos = row.find('td', class_='rechts').get_text(strip=True).split()[0]
                    
                    team_link = row.find('td', class_='no-border-links').find('a')
                    team_name = team_link.get('title', '').strip()
                    team_url = urljoin(BASE_URL, team_link.get('href', ''))
                    
                    logo_img = row.find('img', class_='tiny_wappen')
                    logo_url = logo_img.get('src') if logo_img else None
                    
                    cols = row.find_all('td', class_='zentriert')
                    if len(cols) < 7:
                        continue
                    
                    played = cols[0].get_text(strip=True)
                    wins = cols[1].get_text(strip=True)
                    draws = cols[2].get_text(strip=True)
                    losses = cols[3].get_text(strip=True)
                    goals = cols[4].get_text(strip=True)
                    goal_diff = cols[5].get_text(strip=True)
                    points = cols[6].get_text(strip=True)
                    
                    pos_change = None
                    pos_change_span = row.find('td', class_='rechts').find('span')
                    if pos_change_span and 'title' in pos_change_span.attrs:
                        pos_change = pos_change_span['title']
                    
                    table.append({
                        'position': pos,
                        'position_change': pos_change,
                        'team_id': team_url.split("/")[-3] if team_url else None,
                        'team': team_name,
                        'team_url': team_url,
                        'team_logo': logo_url,
                        'matches_played': played,
                        'wins': wins,
                        'draws': draws,
                        'losses': losses,
                        'goals': goals,
                        'goal_difference': goal_diff,
                        'points': points
                    })

                leagues_table_cache[(league_code, season)] = table
                return table
                
    except Exception as e:
        print(f"Error fetching league table for {league_code} season {season}: {e}")
        return []
