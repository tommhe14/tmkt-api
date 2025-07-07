import aiohttp
from bs4 import BeautifulSoup
import re
import traceback
from .cache import player_search_cache, club_search_cache, player_profile_cache, player_transfers_cache, leagues_search_cache

from datetime import datetime

import asyncio
import json
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
    # Handle both formats:
    # /anapolis-futebol-clube-go-/spielplan/verein/17568
    # /verein/17568/anapolis-futebol-clube-go-
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
            # Extract status
            if row.select_one('span.live-ergebnis'):
                status = 'live'
            elif 'finished' in row.select_one('span.matchresult').get('class', []):
                status = 'finished'
            else:
                status = 'scheduled'
            
            # Extract team info with proper ID handling
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
    # Build the URL based on whether season is provided
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
    
    # Find the main stats table
    stats_table = soup.find('table', class_='items')
    if not stats_table:
        raise Exception("Player stats table not found")
    
    # Initialize response data
    stats_data = {
        "player_id": player_id,
        "season": season if season else "all-time",
        "total": None,
        "competitions": []
    }
    
    # Extract total stats if available (found in tfoot)
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
    
    # Extract competition-specific stats
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
    url = f"https://www.transfermarkt.co.uk/-/startseite/verein/{club_id}"
    
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"HTTP Error {response.status}")
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Extract basic info
                header = soup.find('header', class_='data-header')
                if not header:
                    raise Exception("Club profile header not found")
                
                # Club name
                name_element = header.find('h1', class_='data-header__headline-wrapper')
                club_name = name_element.get_text(strip=True) if name_element else None
                
                # Club logo
                logo_element = header.find('img', src=lambda x: x and 'wappen/head' in x)
                club_logo = logo_element['src'] if logo_element else None
                
                # Trophies
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
                
                # League info
                league_info = {}
                league_link = header.find('span', class_='data-header__club').find('a')
                if league_link:
                    league_info = {
                        'name': league_link.get_text(strip=True),
                        'id': league_link['href'].split('/')[-1]
                    }
                
                # Squad info - find the info boxes
                info_boxes = header.find_all('div', class_='data-header__details')
                
                # Initialize all squad info variables
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
                
                # Market value
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
                
                return {
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
    # Correct squad URL structure
    url = f"https://www.transfermarkt.co.uk/-/startseite/verein/{club_id}"
    
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"HTTP Error {response.status}")
                
                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")
                players = []
                
                for row in soup.select("table.items tr")[1:]:  # Skip header row
                    cols = row.find_all("td")
                    if len(cols) < 8:  # Ensure we have all columns
                        continue

                    try:
                        # Player number
                        number = cols[0].text.strip()
                        
                        # Player image
                        image_url = cols[2].select_one("img")
                        image_url = image_url["data-src"] if image_url and "data-src" in image_url.attrs else None
                        
                        # Player name and ID
                        player_link_tag = cols[3].select_one("a")
                        player_name = player_link_tag.text.strip() if player_link_tag else None
                        player_id = player_link_tag["href"].split("/")[-1] if player_link_tag else None
                        
                        # Position
                        position = cols[4].text.strip()
                        
                        # Date of birth
                        dob = cols[5].text.strip()
                        
                        # Nationality
                        nationality_img = cols[6].select_one("img")
                        nationality = nationality_img["title"] if nationality_img else None
                        
                        # Market value
                        market_value = cols[7].text.strip()
                        
                        # Injury status
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

                return players
    
    except Exception as e:
        print(traceback.format_exc())
        raise Exception(f"Failed to scrape squad: {str(e)}")

async def scrape_transfers(team_id: int, season: int):
    """Scrape transfers for a specific team and season"""
    transfers_url = f"https://www.transfermarkt.co.uk/-/transfers/verein/{team_id}/saison_id/{season}"
    
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(transfers_url) as response:
                if response.status != 200:
                    print(f"Failed to fetch: HTTP {response.status}")
                    return []
                
                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")
                transfers = []

                # Process both incoming and outgoing tables
                for table_type in ["Arrivals", "Departures"]:
                    table_header = soup.find("h2", string=lambda text: text and table_type in text)
                    if table_header:
                        table = table_header.find_next("table")
                        if table:
                            for row in table.select("tbody > tr"):
                                transfer = await process_transfer_row(row, table_type.lower()[:-1])
                                if transfer:
                                    transfers.append(transfer)
                return transfers
    except Exception as e:
        print(f"Error scraping transfers: {str(e)}")
        return []

async def process_transfer_row(row, transfer_type):
    """Process a single transfer row with improved error handling"""
    try:
        # Player name and ID
        player_name_elem = row.select_one("td.hauptlink a[title]")
        if not player_name_elem:
            return None

        player_name = player_name_elem.text.strip()
        player_href = player_name_elem.get("href", "")
        player_id = player_href.split("/")[-1] if player_href else None
        
        # Age
        age_elem = row.select_one("td.zentriert:not([colspan])")
        age = int(age_elem.text.strip()) if age_elem and age_elem.text.strip().isdigit() else None
        
        # Nationality
        nationality_elem = row.select_one("td.zentriert img.flaggenrahmen")
        nationality = nationality_elem.get("title") if nationality_elem else None
        
        # Position
        position_elem = row.select_one("td table.inline-table tr:nth-of-type(2) td")
        position = position_elem.text.strip() if position_elem else None
        
        # Club (either left or joining club)
        club_elem = row.select_one("td img.tiny_wappen")
        club = club_elem.get("title") if club_elem else None
        
        # Fee handling
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
                # Clean up the fee format
                fee = fee.replace("m", "M").replace("bn", "B").strip()
        
        # Player image
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
                rows = table.find_all('tr')[1:]  # Skip the header row

                for row in rows:
                    columns = row.find_all('td')
                    if len(columns) < 15:  # Skip rows that don't have enough columns
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

                    # Player info (name, position, logo)
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

                    # Age
                    player_info['age'] = columns[4].get_text(strip=True)

                    # Nationality
                    nationality_img = columns[5].find('img')
                    if nationality_img:
                        player_info['nationality'] = nationality_img.get('title', 'N/A')

                    # Current club info
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

                    # Previous club info
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

                    # Transfer fee
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
        return search_query[leagues_search_cache]
    
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
                
                # Find all tables with class 'items'
                for table in soup.find_all('table', class_='items'):
                    # Check if this is the leagues table by looking at column headers
                    headers = [th.get_text(strip=True) for th in table.find_all('th')]
                    if 'Competition' in headers and 'Country' in headers:
                        # This is the leagues table
                        for row in table.find_all('tr', class_=['odd', 'even']):
                            cols = row.find_all('td')
                            if len(cols) >= 8:  # Ensure we have all columns
                                leagues.append({
                                    'name': cols[1].find('a')['title'] if cols[1].find('a') else None,
                                    'country': cols[2].find('img')['title'] if cols[2].find('img') else None,
                                    'clubs': cols[3].get_text(strip=True),
                                    'players': cols[4].get_text(strip=True),
                                    'total_value': cols[5].get_text(strip=True),
                                    'continent': cols[7].get_text(strip=True)
                                })
                        break  # Found the leagues table, no need to check others
                leagues_search_cache[search_query] = leagues
                return leagues
                
    except Exception as e:
        print(f"Error scraping leagues: {e}")
        return []
    
#asyncio.run(scrape_transfermarkt_leagues("premier league"))