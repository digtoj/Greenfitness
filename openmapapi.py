import requests
from dotenv import load_dotenv
import os
import json
import streamlit as st
from typing import Any
from pathlib import Path
from shapely.geometry import shape
from shapely.geometry import Point
from unidecode import unidecode

load_dotenv()

api_key = os.getenv("OPEN_MAP_API_KEY")

api_url = "https://api.openchargemap.io/v3/poi/"
if api_key is None:
    raise ValueError("⚠️ API key is missing! Please check your .env file.")

# API Open Charge Map
@st.cache_data(show_spinner=False)
def get_charging_stations(latitude, longitude, max_results=30, radius_km=1):

    if api_key is None:
        raise ValueError("The API key is not available.")

    params = {
        "maxresults": max_results,
        "compact": "true",
        "verbose": "false",
        "latitude": latitude,  
        "longitude": longitude,
        "distance": radius_km,  #*10,
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

def get_town_boundary(town_name: str, country_code: str, level=2) -> Any | None:
    """
    Find and return the boundary for a town from local GADM GeoJSON data.

    Args:
        town_name: Name of the town to look for
        country_code: 'DE' or 'FR'
        level: 1 or 2 (Level of granularity)

    Returns:
        GeoJSON feature dict or None
    """
    filename = f"{country_code}_level2.json"
    path = Path("data/boundaries") / filename  # Change this if your path differs

    if not path.exists():
        raise FileNotFoundError(f"{path} not found.")

    with open(path, "r", encoding="utf-8") as f:
        geojson = json.load(f)

    # Try to find matching town in features
    for feature in geojson["features"]:
        props = feature["properties"]
        for key in ["NAME_2", "NAME_1", "NAME_0"]:
            name = props.get(key)
            if name and unidecode(town_name.lower()) in unidecode(name.lower()):
                return feature

    return None


def get_country_boundary(country_code, level=0):
    """Load the local GeoJSON file for a country and level."""
    base_path = "data/boundaries"
    file_map = {
        "DE": "DE_level0.json",
        "FR": "FR_level0.json"
    }

    filename = file_map.get(country_code)
    if not filename:
        raise ValueError(f"No GeoJSON file configured for country {country_code} at level {level}")

    filepath = f"{base_path}/{filename}"
    with open(filepath, "r", encoding="utf-8") as f:
        geojson_data = json.load(f)
    return geojson_data
