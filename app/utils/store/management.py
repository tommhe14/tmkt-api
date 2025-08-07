import json
from pathlib import Path

_countries_path = Path(__file__).parent / 'countries.json'
with open(_countries_path, 'r') as f:
    countries = json.load(f)

def get_country_list():
    return countries