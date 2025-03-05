import csv
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

import geocoder 
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

from data import (
    fitness_centers,
)



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
