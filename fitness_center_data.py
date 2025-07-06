import csv
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import logging

import geocoder 
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

from data import (
    fitness_centers,
)

# Set up logging
logger = logging.getLogger(__name__)

def is_valid_coordinate(value):
    try:
        num = float(value)
        return num != 0
    except (ValueError, TypeError):
        return False


def convert_coordinate(fitness_centers):
    fitness_centers = fitness_centers[
        fitness_centers["latitude"].apply(is_valid_coordinate)
        & fitness_centers["longitude"].apply(is_valid_coordinate)
    ]
    fitness_centers["latitude"] = fitness_centers["latitude"].astype(float)
    fitness_centers["longitude"] = fitness_centers["longitude"].astype(float)


def get_all_fitness_centers():
    all_data = []
    required_columns = [
        "name",
        "addr:city",
        "longitude",
        "latitude",
        "opening_hours",
        "addr:country",
        "contact:phone",
        "website",
        "addr:street",
        "addr:housenumber",
        "addr:postcode",
        "addr:country"
    ]
    for file in fitness_centers:
        df = pd.read_csv(file, low_memory=False, usecols=required_columns)        
        all_data.append(df)

    if all_data:
        merged_data = pd.concat(all_data, ignore_index=True)
        merged_data["name"] = merged_data["name"].str.strip().str.lower()
        return merged_data
    else:
        return None

def get_unique_towns(all_fitness_centers):
    # Extract unique city names from the fitness centers data
    return all_fitness_centers["addr:city"].str.lower().unique()

def get_fitness_centers_by_town(town_name):
    # Filter all fitness centers by town
    city_studios = all_fitness[all_fitness["addr:city"].str.lower() == town_name.lower()]
    return len(city_studios)

# Function to return list of name 
def get_name_studio(all_fitness_centers, city_name):
    if all_fitness_centers.empty:
        return []
    
    city_studios = all_fitness_centers[all_fitness_centers["addr:city"].str.lower() == city_name.lower()]
    if city_studios is None :
        return []
    studio_names = city_studios["name"].dropna().unique().tolist()
    return studio_names

all_fitness = get_all_fitness_centers()

def get_fitness_centers_by_name(studio_chain, city_name):
    
    if studio_chain:
        city_studios = all_fitness[all_fitness["addr:city"].str.lower() == city_name.lower()]
        fitness_center = city_studios[city_studios["name"].str.contains(studio_chain.lower(), na=False)]
        return fitness_center
    else:
        return []

# NEW: Get fitness centers by coordinates with distance filtering
def get_fitness_centers_by_coordinates(coords, country_code, max_distance_km=50):
    """
    Get fitness centers within a certain distance from given coordinates.
    
    Args:
        coords (tuple): (latitude, longitude) of the search point
        country_code (str): Country code to filter results ('DE' or 'FR')
        max_distance_km (float): Maximum distance in kilometers
    
    Returns:
        pandas.DataFrame: Filtered fitness centers with distance column
    """
    if not coords or len(coords) != 2:
        return pd.DataFrame()
    
    lat, lon = coords
    
    # Get all fitness centers for the country
    all_centers = get_all_fitness_centers()
    if all_centers.empty:
        return pd.DataFrame()
    
    # Filter by country
    country_centers = all_centers[all_centers["addr:country"] == country_code]
    
    if country_centers.empty:
        return pd.DataFrame()
    
    # Calculate distances
    distances = []
    valid_centers = []
    
    for _, center in country_centers.iterrows():
        if (pd.notna(center["latitude"]) and pd.notna(center["longitude"]) and 
            center["latitude"] != 0 and center["longitude"] != 0):
            
            center_coords = (center["latitude"], center["longitude"])
            distance = compute_distance(coords, center_coords)
            
            if distance is not None and distance <= max_distance_km:
                distances.append(distance)
                valid_centers.append(center)
    
    if not valid_centers:
        return pd.DataFrame()
    
    # Create DataFrame with distance information
    result_df = pd.DataFrame(valid_centers)
    result_df["distance_km"] = distances
    result_df = result_df.sort_values("distance_km")
    
    return result_df

# NEW: Extract city from address string
def extract_city_from_address(address_string):
    """
    Try to extract city name from a full address string.
    
    Args:
        address_string (str): Full address string
    
    Returns:
        str: Extracted city name or None
    """
    try:
        geolocator = Nominatim(user_agent="GreenFitnessApp", timeout=10)
        location = geolocator.geocode(address_string)
        
        if location and hasattr(location, 'raw'):
            # Try to get city from different possible fields
            raw_data = location.raw
            city_fields = ['city', 'town', 'village', 'municipality']
            
            for field in city_fields:
                if field in raw_data.get('display_name', ''):
                    # Parse display name to extract city
                    parts = raw_data['display_name'].split(', ')
                    for part in parts:
                        if any(keyword in part.lower() for keyword in ['stadt', 'city', 'town']):
                            return part.strip()
                    # If no specific city indicator, return the second part (often the city)
                    if len(parts) > 1:
                        return parts[1].strip()
            
            # Fallback: try to extract from address components
            if 'address' in raw_data:
                addr = raw_data['address']
                for field in city_fields:
                    if field in addr:
                        return addr[field]
        
        return None
    except Exception as e:
        logger.error(f"Error extracting city from address: {e}")
        return None

# NEW: Get studio names from DataFrame
def get_studio_names_from_centers(fitness_centers_df):
    """
    Get unique studio names from a DataFrame of fitness centers.
    
    Args:
        fitness_centers_df (pandas.DataFrame): DataFrame with fitness centers
    
    Returns:
        list: List of unique studio names
    """
    if fitness_centers_df.empty:
        return []
    
    studio_names = fitness_centers_df["name"].dropna().str.strip().str.lower().unique().tolist()
    return [name for name in studio_names if name]  # Remove empty strings

# NEW: Get fitness centers by name from specific DataFrame
def get_fitness_centers_by_name_from_df(studio_chain, fitness_centers_df):
    """
    Get fitness centers by name from a specific DataFrame (used for distance-filtered results).
    
    Args:
        studio_chain (str): Name of the studio chain to filter
        fitness_centers_df (pandas.DataFrame): DataFrame to filter
    
    Returns:
        pandas.DataFrame: Filtered fitness centers
    """
    if studio_chain and not fitness_centers_df.empty:
        fitness_center = fitness_centers_df[
            fitness_centers_df["name"].str.contains(studio_chain.lower(), na=False)
        ]
        return fitness_center
    else:
        return pd.DataFrame()

# get the user's current geolocation (city-based fallback)
def get_user_location(city_name="Berlin"):
    geolocator = Nominatim(user_agent="GreenFitnessApp", timeout=10)
    location = geolocator.geocode(city_name)
    if location:
        return location.latitude, location.longitude
    return None, None

def get_user_address():
    g = geocoder.ip("me")  # Get user's approximate location
    if not g.latlng:
        return ""  # Return empty if no location found

    geolocator = Nominatim(user_agent="GreenFitnessApp", timeout=20)
    
    try:
        location = geolocator.reverse(g.latlng, exactly_one=True)
        return location.address if location else ""
    except (GeocoderTimedOut, GeocoderUnavailable):
        return ""  # Return empty instead of crashing

# geocode a custom address input by the user
def geocode_address(address):
    geolocator = Nominatim(user_agent="GreenFitnessApp")
    location = geolocator.geocode(address)
    if location:
        return location.latitude, location.longitude
    return None, None

def compute_distance(user_coords, fitness_coords):
    """
    Compute the distance between two geographical points.

    Args:
        user_coords (tuple): (latitude, longitude) of the user
        fitness_coords (tuple): (latitude, longitude) of the fitness studio

    Returns:
        float: Distance in kilometers
    """
    if None in user_coords or None in fitness_coords:
        return None  # Return None if location is unavailable
    
    return geodesic(user_coords, fitness_coords).km

def get_address_from_coordinates(latitude, longitude):
    """
    Get the address from latitude and longitude using reverse geocoding.

    Args:
        latitude (float): Latitude of the fitness studio.
        longitude (float): Longitude of the fitness studio.

    Returns:
        str: Full address of the fitness studio or 'Address not available'.
    """
    geolocator = Nominatim(user_agent="GreenFitnessApp", timeout=5)
    
    try:
        location = geolocator.reverse((latitude, longitude), exactly_one=True)
        return location.address if location else "Address not available"
    except GeocoderTimedOut:
        return "Geocoding service timeout. Try again later."
    except Exception:
        return "Error retrieving address."