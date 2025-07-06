import streamlit as st
import json
import logging
import folium
from geopy.distance import geodesic
from folium.plugins import HeatMap
import pandas as pd
from dotenv import load_dotenv
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from typing import Dict, Any, List, Tuple, Optional, Callable
import logging
from functools import lru_cache

from fitness_center_data import *
from openmapapi import * # get_charging_stations, get_town_boundary
from openroute import *
from result_view import get_card_view_fitness, get_show_details_fitness, get_card_view_fitness_enhanced
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
DEFAULT_SEARCH_RADIUS_KM = 1

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
        "studio_filters": {},  # New state to track which studios are checked/unchecked
        "town_boundary": None,  # For town boundary visualization
        "search_results_info": None,  # For search results statistics
        "search_radius_km": DEFAULT_SEARCH_RADIUS_KM  # Initialize radius
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
            return location_data.latitude, location_data.longitude
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
    m = folium.Map(location=center, zoom_start=zoom)
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
    Add markers for charging stations within the search radius to the map.

    Args:
        m: Folium map object
        stations: List of charging station data dictionaries
    """
    try:
        selected = st.session_state.get("selected_fitness")
        radius_km = st.session_state.get("search_radius_km", DEFAULT_SEARCH_RADIUS_KM)

        if not selected or "latitude" not in selected or "longitude" not in selected:
            logger.warning("No selected fitness studio with coordinates found.")
            return

        selected_coords = (selected["latitude"], selected["longitude"])

        for station in stations:
            if "latitude" in station and "longitude" in station:
                station_coords = (station["latitude"], station["longitude"])
                distance = geodesic(selected_coords, station_coords).km

                if distance <= radius_km:
                    logger.info(f"Distance to station: {distance:.2f} km (limit: {radius_km})")
                    folium.Marker(
                        location=station_coords,
                        tooltip=(
                            f"🔌Charging Station"
                            f"<br>📍 {station.get('name', 'Charging Station')} ({distance:.2f} km)"
                        ),
                        icon=folium.Icon(**ICONS["charging_station"]),
                    ).add_to(m)

    except Exception as e:
        logger.error(f"Error in filtering charging stations by radius: {str(e)}")

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
        st.session_state.zoom_start = 16
        
        # Ensure latitude/longitude are present and valid
        if "latitude" in fitness and "longitude" in fitness:
            st.session_state.map_center = [fitness["latitude"], fitness["longitude"]]
            
            # Fetch nearby charging stations using radius from session state
            radius_km = st.session_state.get("search_radius_km", DEFAULT_SEARCH_RADIUS_KM)
            country_code = st.session_state.get("selected_country_code", DEFAULT_COUNTRY_CODE)
            
            st.session_state.charging_stations = get_charging_stations(
                fitness["latitude"],
                fitness["longitude"],
                radius_km
            )
            
    except Exception as e:
        logger.error(f"Error in fitness selection handler: {str(e)}")
        st.error("Es ist ein Fehler bei der Auswahl des Studios aufgetreten.")

# Enhanced address search handler
def handle_address_search(address: str, country_code: str) -> None:
    """
    Handle the search operation for both cities and street addresses.
    
    Args:
        address: Address string to search (can be city or full address)
        country_code: Country code to filter results
    """
    try:
        # Save search parameters to avoid duplicate searches
        search_params = {
            "address": address,
            "country_code": country_code
        }
        
        # Skip if this is the same as the last search
        if st.session_state.last_search_params == search_params:
            return
            
        # Update search history
        if address not in st.session_state.search_history:
            st.session_state.search_history.append(address)
            if len(st.session_state.search_history) > 10:
                st.session_state.search_history.pop(0)
        
        st.session_state.location = address

        # Geocode the address
        coords = geocode_location(address)
        if not coords:
            st.error(f"Konnte die Adresse '{address}' nicht finden.")
            return
        
        # Update map center
        st.session_state.map_center = coords
        
        # Try to extract city name for town boundary
        extracted_city = extract_city_from_address(address)
        
        # Get town boundary if we can extract a city
        if extracted_city:
            st.session_state.town_boundary = get_town_boundary(extracted_city, country_code)
        else:
            st.session_state.town_boundary = None
        
        # Get fitness centers within reasonable distance (e.g., 50km)
        nearby_centers = get_fitness_centers_by_coordinates(coords, country_code, max_distance_km=50)
        
        if not nearby_centers.empty:
            # Store the filtered fitness centers
            st.session_state.fitness_centers = nearby_centers
            
            # Extract studio names for filtering
            st.session_state.studios_name = get_studio_names_from_centers(nearby_centers)
            
            # Initialize all studios as checked by default in the filters
            for studio in st.session_state.studios_name:
                if studio not in st.session_state.studio_filters:
                    st.session_state.studio_filters[studio] = True
            
            # Show search results info
            st.session_state.search_results_info = {
                "total_centers": len(nearby_centers),
                "max_distance": nearby_centers["distance_km"].max() if "distance_km" in nearby_centers.columns else 0,
                "closest_distance": nearby_centers["distance_km"].min() if "distance_km" in nearby_centers.columns else 0
            }
        else:
            st.warning(f"Keine Fitnessstudios in der Nähe von '{address}' gefunden.")
            st.session_state.fitness_centers = pd.DataFrame()
            st.session_state.studios_name = []
            st.session_state.search_results_info = None
        
        # Reset selections
        st.session_state.selected_fitness = None
        st.session_state.charging_stations = []
        st.session_state.selected_studios = []
        
        # Save this search as the last one performed
        st.session_state.last_search_params = search_params
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        st.error(f"Fehler bei der Suche: {str(e)}")

# Enhanced fitness studios display for sidebar
def show_fitness_studios_in_sidebar():
    """Enhanced version for sidebar display with compact design."""
    if st.session_state.studios_name and not st.session_state.fitness_centers.empty:
        displayed_studios = False
        
        # Show search info if available
        if hasattr(st.session_state, 'search_results_info') and st.session_state.search_results_info:
            info = st.session_state.search_results_info
            st.success(f"📍 {info['total_centers']} Studios gefunden "
                      f"({info['closest_distance']:.1f}-{info['max_distance']:.1f}km)")
        
        # Scrollable container for fitness studios
        with st.container(height=400):
            card_index = 0  # Simple counter for unique keys - THIS IS THE FIX
            for studio in st.session_state.studios_name:
                # Check if this studio is currently filtered in (checkbox is checked)
                if studio in st.session_state.studio_filters and st.session_state.studio_filters[studio]:
                    fitness_centers = get_fitness_centers_by_name_from_df(studio, st.session_state.fitness_centers)
                    if not fitness_centers.empty:
                        for _, fitness_row in fitness_centers.iterrows():
                            # Convert DataFrame row to dictionary
                            fitness_dict = fitness_row.to_dict()
                            
                            # Create compact card for sidebar - PASS THE INDEX
                            show_compact_fitness_card(fitness_dict, card_index)
                            card_index += 1  # INCREMENT FOR UNIQUENESS
                            displayed_studios = True
                    else:
                        st.text(f"🧰 Keine Ergebnisse für {studio}")
        
        if not displayed_studios:
            st.info("🧰 Wählen Sie mindestens ein Studio aus.")
    else:
        st.info("🔍 Führen Sie eine Suche durch, um Ergebnisse zu sehen.")


def show_compact_fitness_card(fitness_data, card_index):  # ADD card_index PARAMETER
    """Show a compact fitness card suitable for sidebar."""
    if not fitness_data:
        return

    # Get basic info
    name = fitness_data.get("name", "Unbekanntes Studio")
    distance_text = ""
    if "distance_km" in fitness_data and pd.notna(fitness_data["distance_km"]):
        distance_text = f" ({fitness_data['distance_km']:.1f}km)"
    
    # Address parts
    address_parts = [
        fitness_data.get("addr:street", ""),
        fitness_data.get("addr:housenumber", ""),
        fitness_data.get("addr:city", "")
    ]
    address = " ".join(filter(None, address_parts))
    
    # Create compact container
    with st.container(border=True):
        # Title with distance
        st.markdown(f"**🏋️‍♂️ {name}{distance_text}**")
        
        # Address
        if address:
            st.caption(f"📍 {address}")
        
        # Action button with simple index-based unique key - NO MORE HASH
        unique_key = f"fitness_btn_{card_index}"  # SIMPLE SEQUENTIAL KEY
        
        if st.button(
            "🗺️ Auf Karte anzeigen", 
            key=unique_key,
            help="Studio auswählen und Ladestationen anzeigen",
            use_container_width=True
        ):
            handle_fitness_selection(fitness_data)

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
    st.sidebar.title("🎛️ Filter und Einstellungen")
    
    # Use default country code from session state
    country_code = st.session_state.selected_country_code
    
    # Studio filter section
    if not st.session_state.fitness_centers.empty:
        st.sidebar.markdown("---")
        
        # Initialize selection state
        all_selected = all(
            st.session_state.studio_filters.get(studio, False) for studio in st.session_state.studios_name)

        # Function to toggle selection
        def toggle_all_studios():
            new_state = not all_selected  # Toggle
            for studio in st.session_state.studios_name:
                st.session_state.studio_filters[studio] = new_state
                st.session_state[f"studio_{studio}"] = new_state

        # Sidebar dropdown menu (expander) for studios
        with st.sidebar.expander("🏋️‍♂️ Ausgewählte Fitnessstudiokette", expanded=True):
            # Small toggle button
            toggle_label = "✅ Alle auswählen" if not all_selected else "🚫 Alle abwählen"
            st.button(toggle_label, on_click=toggle_all_studios, use_container_width=True)

            # Scrollable checkbox list inside the expander
            with st.container(height=200):
                if st.session_state.studios_name:
                    for studio in st.session_state.studios_name:
                        checkbox_value = st.checkbox(
                            studio,
                            key=f"studio_{studio}",
                            value=st.session_state.studio_filters.get(studio, True),
                        )
                        st.session_state.studio_filters[studio] = checkbox_value
                else:
                    st.text("🧰 Keine Studios verfügbar")
        
        # Results section in sidebar - NEW: Enhanced section
        st.sidebar.markdown("---")
        with st.sidebar.expander("🎯 Ergebnisse", expanded=True):
            show_fitness_studios_in_sidebar()
    else:
        st.sidebar.info("🔍 Führen Sie eine Suche durch, um Fitnessstudios zu finden.")

    # Main content
    st.title("_:blue[GreenFitness]_ - Fitness und E-Ladung")
    
    # Search interface (without subheader for more space)
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Text input for flexible address search
        address_input = st.text_input(
            "Geben Sie eine Adresse oder Stadt ein:",
            placeholder="z.B. Luisental 29F, Berlin oder einfach Berlin",
            label_visibility="collapsed",
            help="Sie können eine vollständige Adresse (Straße + Hausnummer + Stadt) oder nur eine Stadt eingeben"
        )
        
        # Optional: Show recent searches as expander
        if st.session_state.search_history:
            with st.expander("📋 Letzte Suchen"):
                for search in reversed(st.session_state.search_history[-5:]):  # Show last 5 searches
                    if st.button(f"🔄 {search}", key=f"recent_{search}"):
                        address_input = search
                        # Trigger search immediately
                        handle_address_search(search, country_code)

    with col2:
        search_button = st.button("🔍 Suchen", type="primary")
    
    # Handle search
    if search_button and address_input.strip():
        handle_address_search(address_input.strip(), country_code)
    elif search_button and not address_input.strip():
        st.warning("Bitte geben Sie eine Adresse oder Stadt ein.")

    # Display current search location and statistics
    if st.session_state.location:
        # Show search info
        info_col1, info_col2, info_col3 = st.columns([2, 1, 1])
        with info_col1:
            st.title(f"📍 {st.session_state.location}")
        
        with info_col2:
            if hasattr(st.session_state, 'search_results_info') and st.session_state.search_results_info:
                info = st.session_state.search_results_info
                st.metric(
                    label="Gefundene Studios", 
                    value=info['total_centers'],
                    delta=f"Nächstes: {info['closest_distance']:.1f}km"
                )
        
        with info_col3:
            if st.session_state.selected_fitness:
                selected_name = st.session_state.selected_fitness.get("name", "Studio")
                st.metric(
                    label="Ausgewähltes Studio",
                    value="✅ Aktiv",
                    delta=f"{selected_name[:20]}..."
                )
    
    # Contextual radius filter - only when studio is selected
    if st.session_state.selected_fitness:
        st.markdown("---")
        radius_col1, radius_col2 = st.columns([2, 1])
        with radius_col1:
            st.markdown("**🔌 Ladestationen-Einstellungen**")
        with radius_col2:
            new_search_radius = st.slider(
                "Suchradius (km):", 
                min_value=1, 
                max_value=5,
                value=st.session_state.get("search_radius_km", DEFAULT_SEARCH_RADIUS_KM),
                help="Entfernung für die Suche nach Ladestationen um das ausgewählte Fitnessstudio",
                key="contextual_radius_slider"
            )
            # Update session state if value changed
            if new_search_radius != st.session_state.get("search_radius_km", DEFAULT_SEARCH_RADIUS_KM):
                st.session_state.search_radius_km = new_search_radius
                # Refresh charging stations if fitness center is selected
                if st.session_state.selected_fitness and "latitude" in st.session_state.selected_fitness:
                    fitness = st.session_state.selected_fitness
                    st.session_state.charging_stations = get_charging_stations(
                        fitness["latitude"],
                        fitness["longitude"],
                        new_search_radius
                    )
    
    # Full-width map section
    st.markdown("---")
    
    # Map header with legend on same line (smaller size)
    st.markdown("**🗺️ Karte | Legende:** 🟣 Suchort | 🟢 Fitnessstudio | 🔴 Ausgewählt | 🔵 Ladestation")

    # Create map
    if st.session_state.get("selected_fitness"):
        selected = st.session_state.selected_fitness
        m = create_base_map(
            center=(selected["latitude"], selected["longitude"]),
            zoom=14
        )
    else:
        m = create_base_map(st.session_state.map_center, st.session_state.zoom_start)

    # Add country boundary visualization
    country_name_map = {"DE": "Germany", "FR": "France"}
    country_name = country_name_map[country_code]
    country_boundary = get_country_boundary(country_code)

    if country_boundary:
        # Add country boundary
        folium.GeoJson(
            country_boundary,
            name="Country Boundary",
            style_function=lambda feature: {
                "fillColor": "#A0C8F0",
                "color": "#0050A0",
                "weight": 2,
                "fillOpacity": 0.2,
            }
        ).add_to(m)

        # Fit to bounds if available and no specific search location
        try:
            if not st.session_state.get("selected_fitness") and not st.session_state.location:
                bounds = folium.GeoJson(country_boundary).get_bounds()
                m.fit_bounds(bounds)
        except Exception as e:
            logger.warning(f"Could not fit to bounds: {e}")
    else:
        st.warning(f"⚠️ Grenze für {country_name} konnte nicht geladen werden.")
    
    # Add town boundary if available
    if st.session_state.get("town_boundary"):
        folium.GeoJson(
            st.session_state.town_boundary,
            name="Selected Town",
            style_function=lambda feature: {
                "fillColor": "orange",
                "color": "orange",
                "weight": 2,
                "fillOpacity": 0.1,
            },
        ).add_to(m)
    
    # Add search location marker
    if st.session_state.location and st.session_state.map_center:
        folium.Marker(
            location=st.session_state.map_center,
            tooltip=f"🔍 Suchstandort: {st.session_state.location}",
            icon=folium.Icon(color="purple", icon="search"),
        ).add_to(m)
    
    # Add filtered fitness markers to the map
    if st.session_state.studios_name and not st.session_state.fitness_centers.empty:
        for studio in st.session_state.studios_name:
            # Only add markers for checked studios
            if st.session_state.studio_filters.get(studio, True):
                fitness_centers = get_fitness_centers_by_name_from_df(studio, st.session_state.fitness_centers)
                if not fitness_centers.empty:
                    for _, fitness_row in fitness_centers.iterrows():
                        fitness_dict = fitness_row.to_dict()
                        if "latitude" in fitness_dict and "longitude" in fitness_dict:
                            try:
                                distance_text = ""
                                if "distance_km" in fitness_dict and pd.notna(fitness_dict["distance_km"]):
                                    distance_text = f" ({fitness_dict['distance_km']:.1f}km)"
                                
                                folium.Marker(
                                    location=[fitness_dict["latitude"], fitness_dict["longitude"]],
                                    tooltip=(f"🏋️‍♂️ {fitness_dict.get('name', 'Fitness Center')}{distance_text}"
                                             f"<br>📍 {fitness_dict.get('addr:street', '')} {fitness_dict.get('addr:housenumber', '')}"
                                             ),
                                    icon=folium.Icon(**ICONS["fitness"]),
                                ).add_to(m)
                            except Exception as e:
                                logger.error(f"Error adding fitness marker: {str(e)}")
    
    # Add selected fitness and charging stations if applicable
    if st.session_state.selected_fitness:
        selected = st.session_state.selected_fitness
        
        if "latitude" in selected and "longitude" in selected:
            # Get search radius from session state
            current_search_radius = st.session_state.get("search_radius_km", DEFAULT_SEARCH_RADIUS_KM)
            
            # Add special marker for selected fitness
            distance_text = ""
            if "distance_km" in selected and pd.notna(selected["distance_km"]):
                distance_text = f" ({selected['distance_km']:.1f}km)"
            
            folium.Marker(
                location=[selected["latitude"], selected["longitude"]],
                tooltip=(f"⭐🏋️‍♂️ {selected.get('name', 'Selected Fitness')}{distance_text}"
                         f"<br>📍 {selected.get('addr:street', '')} {selected.get('addr:housenumber', '')}"
                         ),
                icon=folium.Icon(**ICONS["selected_fitness"]),
            ).add_to(m)

            # Draw a radius around the selected fitness studio
            folium.Circle(
                location=[selected["latitude"], selected["longitude"]],
                radius=current_search_radius * 1000,  # Convert km to meters
                color=None,
                fill=True,
                fill_color="blue",
                fill_opacity=0.3,
                tooltip=f"Suchradius: {current_search_radius} km"
            ).add_to(m)

            # Add charging station markers
            add_charging_station_markers(m, st.session_state.charging_stations)

    # Render the full-width map (NEW: No column constraints)
    st_folium(m, width=None, height=700, use_container_width=True)


# Check if UI needs to be refreshed
if st.session_state.get("refresh_ui", False):
    st.session_state.refresh_ui = False  # Reset flag
    st.rerun()  # ✅ Only rerun here, outside of callbacks

if __name__ == "__main__":
    main()