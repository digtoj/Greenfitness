import requests
from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv("OPEN_MAP_API_KEY")

api_url = "https://api.openchargemap.io/v3/poi/"

# API Open Charge Map
def get_charging_stations(latitude, longitude, max_results=100, radius_km=10, country_code='DE'):

    if api_key is None:
        raise ValueError("The API key is not available.")

    params = {
        "countrycode": country_code,
        "maxresults": max_results,
        "compact": "true",
        "verbose": "false",
        "latitude": latitude,  
        "longitude": longitude,
        "distance": radius_km*10,
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