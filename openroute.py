import os
import numpy as np
from dotenv import load_dotenv
import openrouteservice
import folium
from geopy.geocoders import Nominatim

load_dotenv()

# api_key = os.getenv("OPEN_ROUTE")
API_KEY = "5b3ce3597851110001cf6248c929106501184f79bb5406d603aae1ad"

client = openrouteservice.Client(key=API_KEY) 

def snap_to_nearest_road(coords):
    try:
        response = client.nearest(
            coordinates=[coords], 
            number=1  # Get the nearest routable point
        )
        snapped_coords = response['results'][0]['location']
        return tuple(snapped_coords)  # Convert to (lat, lon)
    except Exception as e:
        print(f"Error snapping to road: {e}")
        return coords  # Fallback to original coords

def get_route(start_coords, end_coords):
    start_coords = snap_to_nearest_road(start_coords)
    end_coords = snap_to_nearest_road(end_coords)
    
    try:
        routes = client.directions(
            coordinates=[list(start_coords), list(end_coords)],
            profile="driving-car",
            format="geojson",
            validate=False,
            radiuses=[1000, 1000]  # Keep increased radius
        )
        return routes
    except openrouteservice.exceptions.ApiError as e:
        print(f"OpenRouteService API error: {e}")
        return None
    
def get_route_from_address(start_address, end_coords):
    geolocator = Nominatim(user_agent="GreenFitnessApp")
    start_location = geolocator.geocode(start_address)
    
    if start_location:
        start_coords = (start_location.latitude, start_location.longitude)
        return get_route(start_coords, end_coords)  # Call existing function
    else:
        print("Could not determine start location")
        return None


# Function to add the route to the map
def add_route_to_map(m, user_latitude, user_longitude, fitness_center_latitude, fitness_center_longitude):
    route = get_route([user_latitude, user_longitude], [fitness_center_latitude, fitness_center_longitude])
    folium.GeoJson(
        route,
        name="Route",
        style_function=lambda x: {
            "color": "blue",
            "weight": 5,
            "opacity": 0.7,
        }
    ).add_to(m)