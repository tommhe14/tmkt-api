import json
from pathlib import Path

_countries_path = Path(__file__).parent / 'countries.json'
with open(_countries_path, 'r') as f:
    countries = json.load(f)

def get_country_list():
    return countries

def search_countries_query(query: str):
    """
    Search countries by name or ID
    Returns results in the specified format
    """
    query = query.lower().strip()
    results = []
    
    for country in countries["results"]:
        if (query in country['id'].lower() or 
            query in country['name'].lower()):
            results.append(country)
    
    return {
        "query": query,
        "results": results,
        "stored_data": True,
        "count": len(results)
    }