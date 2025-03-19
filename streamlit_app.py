import streamlit as st
import folium
from folium.plugins import HeatMap
import pandas as pd
from dotenv import load_dotenv
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from typing import Dict, Any, List, Tuple, Optional, Callable
import logging
from functools import lru_cache

from fitness_center_data import *
from openmapapi import get_charging_stations, get_town_boundary
from openroute import *
from result_view import get_card_view_fitness, get_show_details_fitness
from data import LOGO

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants for configuration
DEFAULT_COUNTRY_CODE = "DE"
DEFAULT_CITY = "Germany"
DEFAULT_COORDINATES = {
    "DE": (51.1657, 10.4515),  # Germany center
    "FR": (46.6034, 1.8883)    # France center
}
DEFAULT_ZOOM = 5
DEFAULT_SEARCH_RADIUS_KM = 10

all_fitness_centers = get_all_fitness_centers()

# Icon configuration
ICONS = {
    "fitness": {"color": "green", "icon": "dumbbell"},
    "selected_fitness": {"color": "red", "icon": "star"},
    "charging_station": {"color": "blue", "icon": "plug"}
}

# Initialize session state
def init_session_state() -> None:
    """Initialize all required session state variables."""
    state_defaults = {
        "selected_country_code": DEFAULT_COUNTRY_CODE,
        "fitness_centers": all_fitness_centers,
        "charging_stations": [],
        "selected_fitness": None,
        "map_center": DEFAULT_COORDINATES[DEFAULT_COUNTRY_CODE],
        "zoom_start": DEFAULT_ZOOM,
        "selected_studios": [],
        "studios_name": [],
        "selected_items": {},
        "search_history": [],
        "last_search_params": {},
        "location": None,
        "studio_filters": {}  # New state to track which studios are checked/unchecked
    }
    
    for key, default_value in state_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value


# Geocoding functions
@lru_cache(maxsize=32)
def geocode_location(location: str) -> Optional[Tuple[float, float]]:
    """
    Geocode a location string to latitude/longitude coordinates.
    Results are cached to reduce API calls.
    
    Args:
        location: Location string to geocode
        
    Returns:
        Tuple of (latitude, longitude) or None if geocoding failed
    """
    try:
        geolocator = Nominatim(user_agent="green_fitness_app")
        location_data = geolocator.geocode(location)
        
        if location_data:
            return (location_data.latitude, location_data.longitude)
        return None
    
    except Exception as e:
        logger.error(f"Geocoding error: {str(e)}")
        return None


# Map handling functions
def create_base_map(center: Tuple[float, float], zoom: int) -> folium.Map:
    """
    Create a base Folium map with an optional heatmap overlay.
    
    Args:
        center: (latitude, longitude) tuple for map center
        zoom: Initial zoom level
        
    Returns:
        Folium Map object
    """
    m = folium.Map(location=center, zoom_start=zoom)

    # Prepare heatmap data
    heat_data = []
    if not st.session_state.fitness_centers.empty:
        for _, row in st.session_state.fitness_centers.iterrows():
            if "latitude" in row and "longitude" in row:
                heat_data.append([row["latitude"], row["longitude"], 1])  # 1 is the intensity

    # Add HeatMap layer
    if heat_data:
        HeatMap(heat_data, radius=15).add_to(m)

    return m



def add_fitness_markers(m: folium.Map, fitness_centers: List[Dict[str, Any]]) -> None:
    """
    Add markers for fitness centers to the map.
    
    Args:
        m: Folium map object
        fitness_centers: List of fitness center data dictionaries
    """
    for fitness in fitness_centers:
        if "latitude" in fitness and "longitude" in fitness:
            try:
                folium.Marker(
                    location=[fitness["latitude"], fitness["longitude"]],
                    popup=fitness.get("name", "Fitness Center"),
                    icon=folium.Icon(**ICONS["fitness"]),
                ).add_to(m)
            except Exception as e:
                logger.error(f"Error adding fitness marker: {str(e)}")


def add_charging_station_markers(m: folium.Map, stations: List[Dict[str, Any]]) -> None:
    """
    Add markers for charging stations to the map.
    
    Args:
        m: Folium map object
        stations: List of charging station data dictionaries
    """
    for station in stations:
        if "latitude" in station and "longitude" in station:
            try:
                folium.Marker(
                    location=[station["latitude"], station["longitude"]],
                    popup=f"🔌 {station.get('name', 'Charging Station')}",
                    icon=folium.Icon(**ICONS["charging_station"]),
                ).add_to(m)
            except Exception as e:
                logger.error(f"Error adding charging station marker: {str(e)}")


# UI Handler functions
def handle_fitness_selection(fitness: Dict[str, Any]) -> None:
    """
    Handle when a fitness center is selected.
    
    Args:
        fitness: Dictionary with fitness center data
    """
    try:
        # Update session state
        st.session_state.selected_fitness = fitness
        st.session_state.zoom_start = 12
        
        # Ensure latitude/longitude are present and valid
        if "latitude" in fitness and "longitude" in fitness:
            st.session_state.map_center = [fitness["latitude"], fitness["longitude"]]
            
            # Fetch nearby charging stations
            radius_km = st.session_state.get("search_radius_km", DEFAULT_SEARCH_RADIUS_KM)
            country_code = st.session_state.get("selected_country_code", DEFAULT_COUNTRY_CODE)
            
            st.session_state.charging_stations = get_charging_stations(
                fitness["latitude"],
                fitness["longitude"],
                radius_km
            )
            
            # Force a rerun to update the UI
            # st.experimental_rerun() is outdated
            # st.rerun() is up to date, but should not be in callback
            # Set a flag for UI update
            st.session_state.refresh_ui = True  # Instead of using st.rerun()
    except Exception as e:
        logger.error(f"Error in fitness selection handler: {str(e)}")
        st.error("Es ist ein Fehler bei der Auswahl des Studios aufgetreten.")


def handle_search(location: str, country_code: str, fitness_centers) -> None:
    """
    Handle the search operation.
    
    Args:
        location: Location string to search
        country_code: Country code to filter results
    """
    try:
        # Save search parameters to avoid duplicate searches
        search_params = {
            "location": location,
            "country_code": country_code
        }
        
        # Skip if this is the same as the last search
        if st.session_state.last_search_params == search_params:
            return
            
        # Update search history
        if location not in st.session_state.search_history:
            st.session_state.search_history.append(location)
            if len(st.session_state.search_history) > 10:
                st.session_state.search_history.pop(0)
        
        st.session_state.location = location

        # Geocode the location
        coords = geocode_location(location)
        if not coords:
            st.error(f"Konnte den Ort '{location}' nicht finden.")
            return
        
        # ✅ Fetch and store the town boundary
        st.session_state.town_boundary = get_town_boundary(location, country_code)
            
        # Update map center
        st.session_state.map_center = coords
        
        # Get fitness data
        if not st.session_state.fitness_centers.empty:
            # Extract studio names for filtering
            st.session_state.studios_name = get_name_studio(st.session_state.fitness_centers, location)
            
            # Initialize all studios as checked by default in the filters
            for studio in st.session_state.studios_name:
                if studio not in st.session_state.studio_filters:
                    st.session_state.studio_filters[studio] = True
            
        else:
            st.warning(f"Keine Fitnessstudios in '{location}' gefunden.")
            st.session_state.fitness_centers = [] 
        
        # Reset selections
        st.session_state.selected_fitness = None
        st.session_state.charging_stations = []
        st.session_state.selected_studios = []
        
        # Save this search as the last one performed
        st.session_state.last_search_params = search_params
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        st.error(f"Fehler bei der Suche: {str(e)}")

def show_fitness_studios():
    with st.container(border=True, height=600):
        if st.session_state.studios_name:
            displayed_studios = False
            for studio in st.session_state.studios_name:
                # Check if this studio is currently filtered in (checkbox is checked)
                if studio in st.session_state.studio_filters and st.session_state.studio_filters[studio]:
                    fitness_centers = get_fitness_centers_by_name(studio, st.session_state.location)
                    if not fitness_centers.empty:
                        for _, fitness_row in fitness_centers.iterrows():
                            # Convert DataFrame row to dictionary
                            fitness_dict = fitness_row.to_dict()
                            # Create a closure to capture the current fitness center
                            def create_handler(data=fitness_dict):
                                return lambda: handle_fitness_selection(data)
                            
                            get_card_view_fitness(
                                fitness_data=fitness_dict,
                                action_handler=create_handler()
                            )
                            displayed_studios = True
                    else:
                        st.text(f"🧰  Keine Ergebnisse für {studio} anzuzeigen.")
            
            if not displayed_studios:
                st.text("🧰  Keine Studios ausgewählt. Bitte wählen Sie mindestens ein Studio aus der Seitenleiste.")
        else:
            st.text("🧰  Keine Ergebnisse anzuzeigen.")     

# Main application
def main():
    # Configure the page
    st.set_page_config(page_title="Green & Fitness", layout="wide", page_icon="image\\logo.png")
    
    # Initialize session state
    init_session_state()
    st.logo(LOGO, size="large")
    
    # Load CSS
    try:
        with open("styles.css") as f:
            st.html(f"<style>{f.read()}</style>")
    except FileNotFoundError:
        logger.warning("styles.css not found")
    
    # Sidebar
    st.sidebar.title("Filter und Einstellungen")
    
    # Country selection
    country_code = st.sidebar.radio(
        "Land der Suche auswählen:",
        ["DE", "FR"],
        captions=["Deutschland", "Frankreich"],
        index=0 if st.session_state.selected_country_code == "DE" else 1,
    )
    st.session_state.selected_country_code = country_code
    
    # Search radius slider
    search_radius_km = st.sidebar.slider(
        "🔄 Entfernung (km):", 
        min_value=1, 
        max_value=50, 
        value=st.session_state.get("search_radius_km", DEFAULT_SEARCH_RADIUS_KM)
    )
    st.session_state.search_radius_km = search_radius_km
    
    # Filter options
    if st.session_state.fitness_centers.empty:
        st.error("The are no saved data for the fitness Studio.")
    else:
        st.sidebar.header("🏋️‍♂️Ausgwähle Fitnessstudiokette")
        
        # Function to select all studios
        def select_all_studios():
            for studio in st.session_state.studios_name:
                st.session_state.studio_filters[studio] = True
                # Update the individual checkbox state variables
                st.session_state[f"studio_{studio}"] = True
            # Force a rerun to update the UI
            st.rerun()
        
        # Add "Select All" button at the top of the container
        if st.session_state.studios_name:
            select_all = st.sidebar.button("Alle Fitnessstuidioskette auswählen", on_click=select_all_studios)
        
        with st.sidebar.container(border=True, height=500):
            if st.session_state.studios_name:
                # Store the checkbox states in session_state.studio_filters
                for studio in st.session_state.studios_name:
                    checkbox_value = st.checkbox(
                        studio, 
                        key=f"studio_{studio}", 
                        value=st.session_state.studio_filters.get(studio, True)
                    )
                    # Update the filter state
                    st.session_state.studio_filters[studio] = checkbox_value
            else:
                st.text("🧰  Keine Ergebnisse anzuzeigen.")
    
    # Main content
    st.title("Green & Fitness")
    
    # Search bar
    col1, col2 = st.columns([3, 1])
    with col1:
        location = st.text_input("Geben Sie ein Stadt ein:")
    with col2:
        search_button = st.button("Suchen")
    
    if search_button:
        handle_search(location, country_code, st.session_state.fitness_centers)
    
    # Display search results
    st.title(f"📍 {location} - Fitness & Auto-Lade Stationen")
    
    # Create layout
    col1, col3 = st.columns((1, 3))

    
    # Create map
    m = create_base_map(st.session_state.map_center, st.session_state.zoom_start)
    
    # Add town boundary if available
    if st.session_state.get("town_boundary"):
        folium.GeoJson(
            st.session_state.town_boundary,
            name="Selected Town",
            style_function=lambda feature: {
                "fillColor": "blue",
                "color": "blue",
                "weight": 2,
                "fillOpacity": 0.2,
            },
        ).add_to(m)
    
    # Add filtered fitness markers to the map
    if st.session_state.studios_name and st.session_state.location:
        for studio in st.session_state.studios_name:
            # Only add markers for checked studios
            if st.session_state.studio_filters.get(studio, True):
                fitness_centers = get_fitness_centers_by_name(studio, st.session_state.location)
                if not fitness_centers.empty:
                    for _, fitness_row in fitness_centers.iterrows():
                        fitness_dict = fitness_row.to_dict()
                        if "latitude" in fitness_dict and "longitude" in fitness_dict:
                            try:
                                folium.Marker(
                                    location=[fitness_dict["latitude"], fitness_dict["longitude"]],
                                    popup=fitness_dict.get("name", "Fitness Center"),
                                    icon=folium.Icon(**ICONS["fitness"]),
                                ).add_to(m)
                            except Exception as e:
                                logger.error(f"Error adding fitness marker: {str(e)}")
    
    # Add selected fitness and charging stations if applicable
    if st.session_state.selected_fitness:
        # Get first matching row as a dictionary
        selected = st.session_state.selected_fitness
        
        if "latitude" in selected and "longitude" in selected:
            # Add special marker for selected fitness
            folium.Marker(
                location=[selected["latitude"], selected["longitude"]],
                popup=f"⭐ {selected.get('name', 'Selected Fitness')}",
                icon=folium.Icon(**ICONS["selected_fitness"]),
            ).add_to(m)
            
            # Add charging station markers
            add_charging_station_markers(m, st.session_state.charging_stations)
    
    # Display content in columns
    with col3:
        # Create a header and legend on the same line
        col3_1, col3_2 = st.columns([1, 3])
        with col3_1:
            st.header("Die Karte")
        with col3_2:
            # Add a legend to explain the map markers (inline style)
            legend_html = """
            <div style="background-color: white; padding: 5px; border-radius: 5px; margin-top: 10px;">
                <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 15px;">
                    <div style="display: flex; align-items: center;">
                        <div style="background-color: green; color: white; border-radius: 50%; width: 20px; height: 20px; text-align: center; margin-right: 5px; display: flex; justify-content: center; align-items: center;">
                            <i class="fa fa-dumbbell"></i>
                        </div>
                        <span>Fitnessstudio</span>
                    </div>
                    <div style="display: flex; align-items: center;">
                        <div style="background-color: red; color: white; border-radius: 50%; width: 20px; height: 20px; text-align: center; margin-right: 5px; display: flex; justify-content: center; align-items: center;">
                            <i class="fa fa-star"></i>
                        </div>
                        <span>Ausgewähltes Fitnessstudio</span>
                    </div>
                    <div style="display: flex; align-items: center;">
                        <div style="background-color: blue; color: white; border-radius: 50%; width: 20px; height: 20px; text-align: center; margin-right: 5px; display: flex; justify-content: center; align-items: center;">
                            <i class="fa fa-plug"></i>
                        </div>
                        <span>Ladestation</span>
                    </div>
                </div>
            </div>
            """
            st.markdown(legend_html, unsafe_allow_html=True)
        
        st_folium(m, width=None, height=700, use_container_width=True)
    
    if not st.session_state.fitness_centers.empty:
        with col1:
            st.header("🏋️‍♂️ Fitnessstudios")
            show_fitness_studios()

    detail = st.sidebar.columns
    if not st.session_state.fitness_centers.empty:
        with detail :
            st.header("Die Details:")
            get_show_details_fitness(st.session_state.selected_fitness)
            
# Check if UI needs to be refreshed
if st.session_state.get("refresh_ui", False):
    st.session_state.refresh_ui = False  # Reset flag
    st.rerun()  # ✅ Only rerun here, outside of callbacks


if __name__ == "__main__":
    main()
