import requests
from dotenv import load_dotenv
import os
import time
from time import sleep

load_dotenv()

api_key = os.getenv("OPEN_MAP_API_KEY")

api_url = "https://api.openchargemap.io/v3/poi/"
if api_key is None:
    raise ValueError("⚠️ API key is missing! Please check your .env file.")

# API Open Charge Map
def get_charging_stations(latitude, longitude, max_results=100, radius_km=10):
    radius_km=100*radius_km
    if api_key is None:
        raise ValueError("The API key is not available.")

    params = {
        "maxresults": max_results,
        "compact": "true",
        "verbose": "false",
        "latitude": latitude,  
        "longitude": longitude,
        "distance": radius_km+100,
        "distanceunit": "KM",
        "key": api_key
    }
    
    response = requests.get(api_url, params=params)
        # Check if the request was successful
    if response.status_code == 200:
        charge_points = response.json()
        # Collecting the station details
        stations = []
        for point in charge_points:
            station_info = {
                "name": point.get("AddressInfo", {}).get("Title", "Unknown"),
                "address": point.get("AddressInfo", {}).get("AddressLine1", "Unknown"),
                "city": point.get("AddressInfo", {}).get("Town", "Unknown"),
                "country": point.get("AddressInfo", {}).get("Country", "Unknown"),
                "latitude": point.get("AddressInfo", {}).get("Latitude", "Unknown"),
                "longitude": point.get("AddressInfo", {}).get("Longitude", "Unknown"),
                "distance": point.get("Distance", "Unknown")
            }
            stations.append(station_info)
        return stations
    else:
        print(f"Error {response.status_code}: Unable to retrieve data.")
        return []
    
    
def get_town_boundary(town_name, country_code="DE"):
    """
    Fetches the boundary (polygon) of a town using the OpenStreetMap API.
    
    Args:
        town_name (str): Name of the town.
        country_code (str): Country code (default: "DE" for Germany).
    
    Returns:
        dict: GeoJSON object of the boundary or None if not found. 
    """
    try:
        # Nominatim API URL for searching town boundaries
        nominatim_url = f"https://nominatim.openstreetmap.org/search"
        
        # Adding a User-Agent header to prevent blocking
        headers = {
            "User-Agent": "GreenFitnessApp/1.0 (olivianguimdo@gmail.com)"
        }

        params = {
            "q": f"{town_name}, {country_code}",
            "format": "json",
            "polygon_geojson": 1,  # Request boundary polygon
            "limit": 1
        }
        
        # Add a delay to avoid hitting rate limits
        time.sleep(1)

        response = requests.get(nominatim_url, params=params, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if data and "geojson" in data[0]:
                return data[0]["geojson"]  # Return the boundary GeoJSON
            else:
                print(f"No boundary found for {town_name}.")
                return None
        else:
            print(f"Error {response.status_code}: Could not fetch boundary.")
            return None
    except Exception as e:
        print(f"Error fetching town boundary: {e}")
        return None