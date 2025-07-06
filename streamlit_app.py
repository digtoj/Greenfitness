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
import time

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
        "search_radius_km": DEFAULT_SEARCH_RADIUS_KM,  # Initialize radius
        "debug_mode": False  # Debug mode toggle
    }
    
    for key, default_value in state_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value


# Debug function
def debug_session_state():
    """Debug function to show current session state"""
    if st.checkbox("🔧 Debug Mode", key="debug_toggle"):
        st.session_state.debug_mode = True
        st.markdown("### 🔍 Debug Information")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Selected Fitness:**")
            if st.session_state.selected_fitness:
                selected = st.session_state.selected_fitness
                st.json({
                    "name": selected.get("name"),
                    "latitude": selected.get("latitude"), 
                    "longitude": selected.get("longitude"),
                    "has_coords": "latitude" in selected and "longitude" in selected,
                    "coords_valid": (selected.get("latitude") != 0 and selected.get("longitude") != 0) if "latitude" in selected else False
                })
            else:
                st.write("None")
        
        with col2:
            st.markdown("**Charging Stations:**")
            stations = st.session_state.get("charging_stations", [])
            st.write(f"Count: {len(stations)}")
            if stations:
                # Show first station as example
                first_station = stations[0]
                st.json({
                    "name": first_station.get("name"),
                    "latitude": first_station.get("latitude"),
                    "longitude": first_station.get("longitude"),
                    "distance": first_station.get("distance")
                })
        
        st.markdown("**Map State:**")
        st.json({
            "map_center": st.session_state.map_center,
            "zoom_start": st.session_state.zoom_start,
            "search_radius_km": st.session_state.get("search_radius_km", "not set")
        })
        
        # Manual refresh button
        if st.button("🔄 Force Refresh", help="Click if map doesn't update"):
            st.rerun()
    else:
        st.session_state.debug_mode = False


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
    Add markers for charging stations to the map with improved validation.
    """
    try:
        if not stations:
            logger.warning("No charging stations provided to add to map.")
            return

        added_stations = 0
        logger.info(f"Attempting to add {len(stations)} charging stations to map")

        for i, station in enumerate(stations):
            try:
                # Validate station data
                if not station.get("latitude") or not station.get("longitude"):
                    logger.warning(f"Station {i+1} missing coordinates: {station}")
                    continue
                
                # Check for "Unknown" values
                if station.get("latitude") == "Unknown" or station.get("longitude") == "Unknown":
                    logger.warning(f"Station {i+1} has 'Unknown' coordinates")
                    continue
                
                # Convert to float and validate
                lat = float(station["latitude"])
                lon = float(station["longitude"])
                
                if lat == 0 or lon == 0:
                    logger.warning(f"Station {i+1} has invalid coordinates: {lat}, {lon}")
                    continue
                
                # Create marker
                station_name = station.get('name', 'Charging Station')
                station_address = station.get('address', 'Adresse unbekannt')
                distance = station.get('distance', 'N/A')
                
                tooltip_text = (
                    f"🔌 {station_name}<br>"
                    f"📍 {station_address}<br>"
                    f"🚗 {distance}km entfernt" if distance != 'N/A' else f"🚗 Entfernung unbekannt"
                )
                
                folium.Marker(
                    location=[lat, lon],
                    tooltip=tooltip_text,
                    popup=f"""
                    <div style="width: 200px;">
                        <h4>🔌 {station_name}</h4>
                        <p><strong>📍 Adresse:</strong><br>{station_address}</p>
                        <p><strong>🏙️ Stadt:</strong> {station.get('city', 'Unbekannt')}</p>
                        <p><strong>🚗 Entfernung:</strong> {distance}km</p>
                    </div>
                    """,
                    icon=folium.Icon(color="blue", icon="plug"),
                ).add_to(m)
                
                added_stations += 1
                
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid coordinates for station {i+1} {station.get('name', 'Unknown')}: {e}")
                continue
            except Exception as e:
                logger.error(f"Error adding station {i+1}: {e}")
                continue

        logger.info(f"Successfully added {added_stations} charging station markers to map")
        
        if added_stations == 0:
            logger.warning("No charging stations were successfully added to the map")

    except Exception as e:
        logger.error(f"Error in adding charging station markers: {str(e)}")


# Enhanced UI Handler functions
def handle_fitness_selection(fitness: Dict[str, Any]) -> None:
    """
    Handle when a fitness center is selected with improved error handling and debugging.
    """
    try:
        logger.info(f"Selecting fitness studio: {fitness.get('name', 'Unknown')}")
        
        # Update session state
        st.session_state.selected_fitness = fitness
        st.session_state.zoom_start = 15  # Zoom in when studio selected
        
        # Ensure latitude/longitude are present and valid
        if "latitude" in fitness and "longitude" in fitness:
            # Convert to float and validate
            try:
                lat = float(fitness["latitude"])
                lon = float(fitness["longitude"])
                
                if lat == 0 or lon == 0:
                    st.error("Ungültige Koordinaten für das ausgewählte Studio.")
                    return
                    
            except (ValueError, TypeError):
                st.error("Fehler beim Verarbeiten der Studio-Koordinaten.")
                return
            
            # Update map center to the selected studio
            new_center = [lat, lon]
            st.session_state.map_center = new_center
            
            logger.info(f"Map center updated to: {new_center}")
            
            # Fetch nearby charging stations using radius from sidebar
            radius_km = st.session_state.get("search_radius_km", DEFAULT_SEARCH_RADIUS_KM)
            
            logger.info(f"Fetching charging stations with radius: {radius_km}km")
            
            # Show loading message
            with st.spinner(f"Lade Ladestationen im Umkreis von {radius_km}km..."):
                try:
                    charging_stations = get_charging_stations(
                        latitude=lat,
                        longitude=lon,
                        max_results=50,
                        radius_km=radius_km
                    )
                    
                    # Validate charging station data
                    valid_stations = []
                    for station in charging_stations:
                        try:
                            if (station.get("latitude") != "Unknown" and 
                                station.get("longitude") != "Unknown" and
                                station.get("latitude") is not None and 
                                station.get("longitude") is not None):
                                
                                # Convert to float to ensure they're numeric
                                station["latitude"] = float(station["latitude"])
                                station["longitude"] = float(station["longitude"])
                                valid_stations.append(station)
                        except (ValueError, TypeError):
                            continue
                    
                    st.session_state.charging_stations = valid_stations
                    logger.info(f"Found {len(valid_stations)} valid charging stations")
                    
                    # Show success message
                    if valid_stations:
                        st.success(f"✅ {len(valid_stations)} Ladestationen gefunden!")
                    else:
                        st.warning(f"⚠️ Keine Ladestationen im Umkreis von {radius_km}km gefunden.")
                        
                        # Try with larger radius as fallback
                        if radius_km < 5:
                            logger.info(f"Trying with larger radius: {radius_km + 2}km")
                            fallback_stations = get_charging_stations(
                                latitude=lat,
                                longitude=lon,
                                max_results=50,
                                radius_km=radius_km + 2
                            )
                            
                            # Validate fallback stations
                            valid_fallback = []
                            for station in fallback_stations:
                                try:
                                    if (station.get("latitude") != "Unknown" and 
                                        station.get("longitude") != "Unknown"):
                                        station["latitude"] = float(station["latitude"])
                                        station["longitude"] = float(station["longitude"])
                                        valid_fallback.append(station)
                                except (ValueError, TypeError):
                                    continue
                            
                            if valid_fallback:
                                st.session_state.charging_stations = valid_fallback
                                st.info(f"🔍 {len(valid_fallback)} Ladestationen in {radius_km + 2}km Umkreis gefunden.")
                            
                except Exception as e:
                    logger.error(f"Error fetching charging stations: {str(e)}")
                    st.session_state.charging_stations = []
                    st.error(f"Fehler beim Laden der Ladestationen: {str(e)}")
            
        else:
            logger.error("No valid coordinates found in fitness data")
            st.error("Keine gültigen Koordinaten für das ausgewählte Studio gefunden.")
            
        # Force app rerun to update the map
        st.rerun()
            
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
        st.session_state.zoom_start = 12  # Set zoom to 12 for search results
        
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


# Enhanced compact fitness card for sidebar
def show_compact_fitness_card(fitness_data, card_index):
    """Show a compact fitness card suitable for sidebar with improved state management."""
    if not fitness_data:
        return

    # Get basic info
    name = fitness_data.get("name", "Unbekanntes Studio")
    distance_text = ""
    if "distance_km" in fitness_data and pd.notna(fitness_data["distance_km"]):
        distance_text = f" ({fitness_data['distance_km']:.1f}km)"
    
    # Create compact container
    with st.container(border=True):
        # Title with distance
        st.markdown(f"**🏋️‍♂️ {name}{distance_text}**")
        
        # Create more reliable unique key
        lat = fitness_data.get('latitude', 0)
        lon = fitness_data.get('longitude', 0)
        name_hash = hash(name) % 10000  # Simple hash of name
        unique_key = f"btn_{card_index}_{name_hash}_{str(lat).replace('.', '_')}_{str(lon).replace('.', '_')}"
        
        # Show current selection status
        is_selected = False
        if st.session_state.selected_fitness:
            selected_lat = st.session_state.selected_fitness.get('latitude')
            selected_lon = st.session_state.selected_fitness.get('longitude')
            is_selected = (abs(float(selected_lat or 0) - float(lat or 0)) < 0.0001 and 
                          abs(float(selected_lon or 0) - float(lon or 0)) < 0.0001)
        
        button_text = "✅ Ausgewählt" if is_selected else "🗺️ Auf Karte anzeigen"
        button_type = "secondary" if is_selected else "primary"
        
        # Add debug info if debug mode is on
        if st.session_state.get("debug_mode", False):
            st.caption(f"Key: {unique_key}")
            st.caption(f"Coords: {lat}, {lon}")
        
        if st.button(
            button_text,
            key=unique_key,
            help="Studio auswählen und Ladestationen anzeigen",
            use_container_width=True,
            type=button_type
        ):
            if not is_selected:  # Only select if not already selected
                logger.info(f"Button clicked for studio: {name} at {lat}, {lon}")
                
                # Validate coordinates before selection
                try:
                    test_lat = float(lat)
                    test_lon = float(lon)
                    if test_lat != 0 and test_lon != 0:
                        handle_fitness_selection(fitness_data)
                    else:
                        st.error("Ungültige Koordinaten für dieses Studio.")
                except (ValueError, TypeError):
                    st.error("Fehler beim Verarbeiten der Studio-Koordinaten.")


# Enhanced fitness studios display for sidebar
def show_fitness_studios_in_sidebar():
    """Enhanced version for sidebar display with compact design."""
    if st.session_state.studios_name and not st.session_state.fitness_centers.empty:
        displayed_studios = False
        
        # Show search info with selected studio details in same line
        if hasattr(st.session_state, 'search_results_info') and st.session_state.search_results_info:
            info = st.session_state.search_results_info
            base_message = f"📍 {info['total_centers']} Studios gefunden ({info['closest_distance']:.1f}-{info['max_distance']:.1f}km)"
            
            # Add selected studio details if available
            if st.session_state.selected_fitness:
                selected = st.session_state.selected_fitness
                name = selected.get("name", "Studio")
                distance_text = ""
                if "distance_km" in selected and pd.notna(selected["distance_km"]):
                    distance_text = f" ({selected['distance_km']:.1f}km)"
                
                # Create address for selected studio
                address_parts = [
                    str(selected.get("addr:street", "")) if pd.notna(selected.get("addr:street")) else "",
                    str(selected.get("addr:housenumber", "")) if pd.notna(selected.get("addr:housenumber")) else "",
                    str(selected.get("addr:city", "")) if pd.notna(selected.get("addr:city")) else ""
                ]
                address_parts = [part for part in address_parts if part and part.lower() != "nan"]
                address = " ".join(address_parts)
                
                # Add selected studio info to the message
                selected_info = f" | ⭐ {name}{distance_text}"
                if address:
                    selected_info += f" - {address}"
                if selected.get("contact:phone"):
                    selected_info += f" - 📞 {selected.get('contact:phone')}"
                
                base_message += selected_info
            
            st.success(base_message)
        
        # Scrollable container for fitness studios
        with st.container(height=400):
            card_index = 0  # Simple counter for unique keys
            for studio in st.session_state.studios_name:
                # Check if this studio is currently filtered in (checkbox is checked)
                if studio in st.session_state.studio_filters and st.session_state.studio_filters[studio]:
                    fitness_centers = get_fitness_centers_by_name_from_df(studio, st.session_state.fitness_centers)
                    if not fitness_centers.empty:
                        for _, fitness_row in fitness_centers.iterrows():
                            # Convert DataFrame row to dictionary
                            fitness_dict = fitness_row.to_dict()
                            
                            # Create compact card for sidebar with unique index
                            show_compact_fitness_card(fitness_dict, card_index)
                            card_index += 1  # Increment for next card
                            displayed_studios = True
                    else:
                        st.text(f"🧰 Keine Ergebnisse für {studio}")
        
        if not displayed_studios:
            st.info("🧰 Wählen Sie mindestens ein Studio aus.")
    else:
        st.info("🔍 Führen Sie eine Suche durch, um Ergebnisse zu sehen.")


def show_selected_studio_details():
    """Show detailed information about the selected fitness studio."""
    if not st.session_state.selected_fitness:
        st.info("Kein Studio ausgewählt")
        return
    
    fitness_data = st.session_state.selected_fitness
    
    # Studio name with distance
    name = fitness_data.get("name", "Unbekanntes Studio")
    distance_text = ""
    if "distance_km" in fitness_data and pd.notna(fitness_data["distance_km"]):
        distance_text = f" ({fitness_data['distance_km']:.1f}km)"
    
    st.markdown(f"**🏋️‍♂️ {name}{distance_text}**")
    
    # Address information - convert all to strings to avoid float join error
    address_parts = [
        str(fitness_data.get("addr:street", "")) if pd.notna(fitness_data.get("addr:street")) else "",
        str(fitness_data.get("addr:housenumber", "")) if pd.notna(fitness_data.get("addr:housenumber")) else "",
        str(fitness_data.get("addr:postcode", "")) if pd.notna(fitness_data.get("addr:postcode")) else "",
        str(fitness_data.get("addr:city", "")) if pd.notna(fitness_data.get("addr:city")) else "",
    ]
    # Filter out empty strings and "nan" strings
    address_parts = [part for part in address_parts if part and part.lower() != "nan"]
    full_address = " ".join(address_parts)
    
    if full_address:
        st.markdown(f"📍 **Adresse:**  \n{full_address}")
    
    # Contact information
    if fitness_data.get("contact:phone"):
        st.markdown(f"📞 **Telefon:**  \n{fitness_data.get('contact:phone')}")
    
    if fitness_data.get("website"):
        website = fitness_data.get("website")
        if not website.startswith(('http://', 'https://')):
            website = f"https://{website}"
        st.markdown(f"🌍 **Website:**  \n[{fitness_data.get('website')}]({website})")
    
    # Opening hours
    if fitness_data.get("opening_hours"):
        st.markdown(f"⏰ **Öffnungszeiten:**  \n{fitness_data.get('opening_hours')}")
    
    # Coordinates (for debugging/reference)
    if fitness_data.get("latitude") and fitness_data.get("longitude"):
        st.caption(f"📍 Koordinaten: {fitness_data.get('latitude'):.4f}, {fitness_data.get('longitude'):.4f}")
    
    # Action buttons
    col1, col2 = st.columns(2)
    with col1:
        # Add nanoseconds for unique key
        nano_time1 = time.time_ns()
        if st.button("Auf Karte zentrieren", use_container_width=True, key=f"center_btn_{nano_time1}"):
            # Re-center map on selected studio
            st.session_state.map_center = [float(fitness_data["latitude"]), float(fitness_data["longitude"])]
            st.session_state.zoom_start = 15
            st.rerun()
    
    with col2:
        nano_time2 = time.time_ns() + 1  # Ensure different from first button
        if st.button("❌ Auswahl aufheben", use_container_width=True, key=f"clear_btn_{nano_time2}"):
            # Clear selection
            st.session_state.selected_fitness = None
            st.session_state.charging_stations = []
            # Reset map to default view
            st.session_state.zoom_start = DEFAULT_ZOOM
            st.rerun()


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
    
    # Main title
    st.title("_:blue[GreenFitness]_ - Fitness und E-Ladung")
    
    # Add debug section
    debug_session_state()
    
    # Sidebar
    # Filters in expandable section (closed by default)
    with st.sidebar.expander("⚙️ Filter", expanded=False):
        # Country selection
        country_code = st.radio(
            "🌍 Land der Suche auswählen:",
            ["DE", "FR"],
            captions=["Deutschland", "Frankreich"],
            index=0 if st.session_state.selected_country_code == "DE" else 1,
        )
        st.session_state.selected_country_code = country_code
        
        # Search radius slider
        search_radius_km = st.slider(
            "🔄 Suchradius für Ladestationen (km):", 
            min_value=1, 
            max_value=5,
            value=st.session_state.get("search_radius_km", DEFAULT_SEARCH_RADIUS_KM),
            help="Entfernung für die Suche nach Ladestationen um das ausgewählte Fitnessstudio"
        )
        
        # Update session state and refresh charging stations if needed
        if search_radius_km != st.session_state.get("search_radius_km", DEFAULT_SEARCH_RADIUS_KM):
            st.session_state.search_radius_km = search_radius_km
            # Auto-update charging stations if fitness center is selected
            if st.session_state.selected_fitness and "latitude" in st.session_state.selected_fitness:
                fitness = st.session_state.selected_fitness
                try:
                    lat = float(fitness["latitude"])
                    lon = float(fitness["longitude"])
                    charging_stations = get_charging_stations(lat, lon, radius_km=search_radius_km)
                    
                    # Validate stations
                    valid_stations = []
                    for station in charging_stations:
                        try:
                            if (station.get("latitude") != "Unknown" and 
                                station.get("longitude") != "Unknown"):
                                station["latitude"] = float(station["latitude"])
                                station["longitude"] = float(station["longitude"])
                                valid_stations.append(station)
                        except (ValueError, TypeError):
                            continue
                    
                    st.session_state.charging_stations = valid_stations
                    st.rerun()
                except Exception as e:
                    logger.error(f"Error updating charging stations: {e}")
    
    # Studio filter section
    if not st.session_state.fitness_centers.empty:
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
        with st.sidebar.expander("Ausgewählte Fitnessstudiokette", expanded=False):
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
        
        # Results section in sidebar
        with st.sidebar.expander("🎯 Ergebnisse", expanded=True):
            show_fitness_studios_in_sidebar()
    else:
        st.sidebar.info("🔍 Führen Sie eine Suche durch, um Fitnessstudios zu finden.")
    
    # Selected studio details section - Show regardless of search results
    if st.session_state.selected_fitness:
        st.sidebar.markdown("---")
        with st.sidebar.expander("📋 Ausgewähltes Studio", expanded=True):
            show_selected_studio_details()

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
    
    # Full-width map section
    st.markdown("---")
    
    # Map header with legend on same line (smaller size)
    st.markdown("**Karte | Legende:** 🟣 Suchort | 🟢 Fitnessstudio | 🔴 Ausgewählt | 🔵 Ladestation")
    
    # Debug info and charging station count
    debug_info = []
    if st.session_state.get("selected_fitness"):
        selected = st.session_state.selected_fitness
        debug_info.append(f"Ausgewähltes Studio: {selected.get('name')}")
        debug_info.append(f"Koordinaten: {st.session_state.map_center}")
        debug_info.append(f"Zoom: {st.session_state.zoom_start}")
        
        # Show charging station count
        charging_count = len(st.session_state.get("charging_stations", []))
        radius = st.session_state.get("search_radius_km", DEFAULT_SEARCH_RADIUS_KM)
        debug_info.append(f"Ladestationen: {charging_count} (Radius: {radius}km)")
        
        st.caption(f"🔍 Debug: {' | '.join(debug_info)}")
    
    # Show warning if no charging stations found
    if (st.session_state.get("selected_fitness") and 
        len(st.session_state.get("charging_stations", [])) == 0):
        st.warning(f"⚠️ Keine Ladestationen im Umkreis von {st.session_state.get('search_radius_km', DEFAULT_SEARCH_RADIUS_KM)}km gefunden. Versuchen Sie einen größeren Radius.")

    # Create map with proper center and zoom
    map_center = st.session_state.map_center
    zoom_level = st.session_state.zoom_start
    
    # Debug info (optional - can be removed in production)
    if st.session_state.get("selected_fitness"):
        selected = st.session_state.selected_fitness
        logger.info(f"Creating map centered on selected studio: {selected.get('name')} at {map_center} with zoom {zoom_level}")
    
    m = create_base_map(center=map_center, zoom=zoom_level)

    # Add country boundary visualization
    country_name_map = {"DE": "Germany", "FR": "France"}
    country_name = country_name_map[country_code]
    try:
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
    except Exception as e:
        logger.warning(f"Error loading country boundary: {e}")
    
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
        fitness_count = 0
        for studio in st.session_state.studios_name:
            # Only add markers for checked studios
            if st.session_state.studio_filters.get(studio, True):
                fitness_centers = get_fitness_centers_by_name_from_df(studio, st.session_state.fitness_centers)
                if not fitness_centers.empty:
                    for _, fitness_row in fitness_centers.iterrows():
                        fitness_dict = fitness_row.to_dict()
                        if "latitude" in fitness_dict and "longitude" in fitness_dict:
                            try:
                                lat = float(fitness_dict["latitude"])
                                lon = float(fitness_dict["longitude"])
                                
                                if lat != 0 and lon != 0:
                                    distance_text = ""
                                    if "distance_km" in fitness_dict and pd.notna(fitness_dict["distance_km"]):
                                        distance_text = f" ({fitness_dict['distance_km']:.1f}km)"
                                    
                                    folium.Marker(
                                        location=[lat, lon],
                                        tooltip=(f"🏋️‍♂️ {fitness_dict.get('name', 'Fitness Center')}{distance_text}"
                                                f"<br>📍 {fitness_dict.get('addr:street', '')} {fitness_dict.get('addr:housenumber', '')}"
                                                ),
                                        icon=folium.Icon(**ICONS["fitness"]),
                                    ).add_to(m)
                                    fitness_count += 1
                            except (ValueError, TypeError) as e:
                                logger.error(f"Invalid coordinates for fitness center: {e}")
        
        logger.info(f"Added {fitness_count} fitness center markers to map")
    
    # Add selected fitness and charging stations if applicable
    if st.session_state.selected_fitness:
        selected = st.session_state.selected_fitness
        
        if "latitude" in selected and "longitude" in selected:
            try:
                sel_lat = float(selected["latitude"])
                sel_lon = float(selected["longitude"])
                
                if sel_lat != 0 and sel_lon != 0:
                    # Add special marker for selected fitness
                    distance_text = ""
                    if "distance_km" in selected and pd.notna(selected["distance_km"]):
                        distance_text = f" ({selected['distance_km']:.1f}km)"
                    
                    folium.Marker(
                        location=[sel_lat, sel_lon],
                        tooltip=(f"⭐🏋️‍♂️ {selected.get('name', 'Selected Fitness')}{distance_text}"
                                f"<br>📍 {selected.get('addr:street', '')} {selected.get('addr:housenumber', '')}"
                                ),
                        icon=folium.Icon(**ICONS["selected_fitness"]),
                    ).add_to(m)

                    # Draw a radius around the selected fitness studio
                    current_search_radius = st.session_state.get("search_radius_km", DEFAULT_SEARCH_RADIUS_KM)
                    folium.Circle(
                        location=[sel_lat, sel_lon],
                        radius=current_search_radius * 1000,  # Convert km to meters
                        color="blue",
                        weight=2,
                        fill=True,
                        fill_color="blue",
                        fill_opacity=0.2,
                        tooltip=f"Suchradius: {current_search_radius} km"
                    ).add_to(m)

                    # Add charging station markers
                    charging_stations = st.session_state.get("charging_stations", [])
                    logger.info(f"Attempting to add {len(charging_stations)} charging stations to map")
                    
                    if charging_stations:
                        add_charging_station_markers(m, charging_stations)
                        # Show success message after adding markers
                        if st.session_state.get("debug_mode"):
                            st.success(f"🔌 {len(charging_stations)} Ladestationen auf der Karte angezeigt")
                    else:
                        logger.warning("No charging stations available to add to map")
                        
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid coordinates for selected fitness: {e}")
                st.error("Fehler bei den Koordinaten des ausgewählten Studios")

    # Render the full-width map
    st_folium(m, width=None, height=700, use_container_width=True)


# Check if UI needs to be refreshed
if st.session_state.get("refresh_ui", False):
    st.session_state.refresh_ui = False  # Reset flag
    st.rerun()

if __name__ == "__main__":
    main()