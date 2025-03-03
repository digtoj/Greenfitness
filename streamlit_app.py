import streamlit as st
import folium
import pandas as pd
from dotenv import load_dotenv
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from typing import Dict, Any, List, Tuple, Optional, Callable
import logging
from functools import lru_cache

from fitness_center_data import *
from openmapapi import get_charging_stations
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
DEFAULT_SEARCH_RADIUS_KM = 5

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
    Create a base Folium map.
    
    Args:
        center: (latitude, longitude) tuple for map center
        zoom: Initial zoom level
        
    Returns:
        Folium Map object
    """
    return folium.Map(location=center, zoom_start=zoom)


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
        st.session_state.zoom_start = 13
        
        # Ensure latitude/longitude are present and valid
        if "latitude" in fitness and "longitude" in fitness:
            st.session_state.map_center = [fitness["latitude"], fitness["longitude"]]
            
            # Fetch nearby charging stations
            radius_km = st.session_state.get("search_radius_km", DEFAULT_SEARCH_RADIUS_KM)
            country_code = st.session_state.get("selected_country_code", DEFAULT_COUNTRY_CODE)
            
            st.session_state.charging_stations = get_charging_stations(
                fitness["latitude"],
                fitness["longitude"],
                radius_km,
                country_code=country_code,
            )
            
            # Force a rerun to update the UI
            st.experimental_rerun()
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
        "Land der Suche für die Lade-stations:",
        ["DE", "FR"],
        captions=["Deutschland", "Frankreich"],
        index=0 if st.session_state.selected_country_code == "DE" else 1,
    )
    st.session_state.selected_country_code = country_code

    show_charging_station = st.sidebar.button(label="💡Lade Station anzeigen")
   
    if show_charging_station:
        st.text("Show lade station")
    
    # Search radius slider
    search_radius_km = st.sidebar.slider(
        "🔄 Adjust Proximity Radius (km):", 
        min_value=1, 
        max_value=20, 
        value=st.session_state.get("search_radius_km", DEFAULT_SEARCH_RADIUS_KM)
    )
    st.session_state.search_radius_km = search_radius_km
    
    # Filter options
    if st.session_state.fitness_centers.empty:
        st.error("The are no saved data for the fitness Studio.")
    else:
        st.sidebar.header("🏋️‍♂️ Fitnessstudiokette")
        
        # Function to select all studios
        def select_all_studios():
            for studio in st.session_state.studios_name:
                st.session_state.studio_filters[studio] = True
        
        # Add "Select All" button at the top of the container
        if st.session_state.studios_name:
            select_all = st.sidebar.button("Select All Studios", on_click=select_all_studios)
        
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
    col1, col2, col3 = st.columns((1, 1, 2))
    
    # Create map
    m = create_base_map(st.session_state.map_center, st.session_state.zoom_start)
    
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
        # Create a header row with title and legend
        header_col1, header_col2 = st.columns([1, 2])
        with header_col1:
            st.header("Die Karte")
        with header_col2:
            # Create a legend using HTML/CSS
            legend_html = """
            <div style="
                padding: 10px;
                background-color: white;
                border-radius: 5px;
                box-shadow: 0 0 5px rgba(0,0,0,0.2);
                margin-top: 20px;
                display: flex;
                flex-direction: row;
                gap: 15px;
                font-size: 14px;
            ">
                <div>
                    <span style="
                        display: inline-block;
                        width: 20px;
                        height: 20px;
                        border-radius: 50%;
                        background-color: green;
                        margin-right: 5px;
                        vertical-align: middle;
                    "></span>
                    <span style="vertical-align: middle;">Fitness Studios</span>
                </div>
                <div>
                    <span style="
                        display: inline-block;
                        width: 20px;
                        height: 20px;
                        border-radius: 50%;
                        background-color: red;
                        margin-right: 5px;
                        vertical-align: middle;
                    "></span>
                    <span style="vertical-align: middle;">Selected Studio</span>
                </div>
                <div>
                    <span style="
                        display: inline-block;
                        width: 20px;
                        height: 20px;
                        border-radius: 50%;
                        background-color: blue;
                        margin-right: 5px;
                        vertical-align: middle;
                    "></span>
                    <span style="vertical-align: middle;">Charging Stations</span>
                </div>
            </div>
            """
            st.markdown(legend_html, unsafe_allow_html=True)
            
        # Display the map
        st_folium(m, width=None, height=600, use_container_width=True)
    
    if not st.session_state.fitness_centers.empty:
        with col1:
            st.header("🏋️‍♂️ Fitnessstudios")
            show_fitness_studios()
        with col2:
            st.header("Die Details:")
            get_show_details_fitness(st.session_state.selected_fitness)

if __name__ == "__main__":
    main()