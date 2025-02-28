import streamlit as st
import folium
import pandas as pd
from dotenv import load_dotenv
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from fitness_center_data import get_fitness_data_by_country_code
from streamlit_option_menu import option_menu

from openmapapi import get_charging_stations
from result_view import get_card_view_fitness, show_container_veiw

default_country_code = "DE"
DEFAULT_CITY = "Germany"
DEFAULT_LAT = 51.1657
DEFAULT_LON = 10.4515


# Initialisation du session_state
keys_to_init = [
    "selected_country_code",
    "fitness_centers",
    "charging_stations",
    "selected_fitness",
    "map_center",
    "zoom_start",
    "selected_studios",
    "studios_name",
    "selected_items",
]

for key in keys_to_init:
    if key not in st.session_state:
        if key == "selected_items":
            st.session_state[key] = {}
        elif key == "map_center":
            st.session_state[key] = [DEFAULT_LAT, DEFAULT_LON]
        elif key == "zoom_start":
            st.session_state[key] = 5
        elif key == "fitness_centers":
            st.session_state[key] = []
        else:
            st.session_state[key] = None if "selected" in key else []

# Configuration de la page
st.set_page_config(page_title="Green & Fitness", layout="wide")
st.sidebar.title("Filters und Einstellungen")


def load_css(file_path):
    with open(file_path) as f:
        st.html(f"<style>{f.read()}</style>")


load_css("styles.css")
# Barre de recherche
col1, col2 = st.columns([3, 1])
with col1:
    location = st.text_input("Ihre Stadt:", DEFAULT_CITY)
with col2:
    search_button = st.button("Suchen")

# Slider de rayon
radius_km = st.sidebar.slider(
    "🔄 Adjust Proximity Radius (km):", min_value=1, max_value=20, value=5
)

# Gestion de la recherche
if search_button:
    try:
        geolocator = Nominatim(user_agent="geoapi")
        location_data = geolocator.geocode(location)

        if location_data:
            st.session_state.map_center = [
                location_data.latitude,
                location_data.longitude,
            ]
            fitness_centers = get_fitness_data_by_country_code(
                default_country_code, city=location
            )
            st.session_state.fitness_centers = fitness_centers.to_dict(orient="records")

            # Réinitialiser les sélections
            st.session_state.update(
                {
                    "selected_fitness": None,
                    "charging_stations": [],
                    "selected_studios": [],
                    "studios_name": list(
                        {f["name"] for f in st.session_state.fitness_centers}
                    ),
                    "selected_items": {
                        name: "" for name in st.session_state.studios_name
                    },
                }
            )

    except Exception as e:
        st.error(f"Fehler bei der Suche: {str(e)}")

# Filtrage des studios
st.sidebar.header("Suche Begrenzen in : ")
country_code = st.sidebar.radio(
    "Land der Suche für die Lade-stations:",
    ["DE", "FR"],
    captions=["Deutschland", "Frankreich"],
)
if country_code == "DE":
    default_country_code = "DE"
else:
    default_country_code = "FR"


# Sidebar: Liste des studios
if st.session_state.fitness_centers:
    st.sidebar.header("🏋️‍♂️ Fitnessstudiokette")


# Création de la carte
m = folium.Map(
    location=st.session_state.map_center, zoom_start=st.session_state.zoom_start
)

# Ajout des marqueurs
for fitness in st.session_state.fitness_centers:
    folium.Marker(
        location=[fitness["latitude"], fitness["longitude"]],
        popup=fitness["name"],
        icon=folium.Icon(color="green", icon="dumbbell"),
        key=f"mkr_{fitness['name']}",
    ).add_to(m)

# Gestion de la sélection
def action_by_click_on_fitness(f):
    st.session_state.update(
        {
            "selected_fitness": f["name"],
            "zoom_start": 13,
            "map_center": [f["latitude"], f["longitude"]],
        }
    )
    print(st.session_state.selected_fitness)
    print(st.session_state.zoom_start)
    print(st.session_state.map_center)
    st.session_state.selectedfitness=f
    if f:
        folium.Marker(
            location=[f["latitude"], f["longitude"]],
            popup=f"⭐ {f['name']}",
            icon=folium.Icon(color="red", icon="star"),
        ).add_to(m)

        stations = get_charging_stations(
            f["latitude"],
            f["longitude"],
            radius_km,
            country_code=default_country_code,
        )
        for station in stations:
            folium.Marker(
                location=[station["latitude"], station["longitude"]],
                popup=f"🔌 {station['name']}",
                icon=folium.Icon(color="blue", icon="star"),
            ).add_to(m)

# Affichage principal
st.title(f"📍 {location} - Fitness & Auto-Lade Stationen")
col1, col2, col3 = st.columns((1, 1, 2))


with col3:
    st_folium(m, width=None, height=600, use_container_width=True)

if st.session_state.fitness_centers:
    with col1:
        st.header("Studios")
        for fitness in st.session_state.fitness_centers:
            st.text(fitness["name"] + "  " + fitness["addr:street"])

    with col2:
        for fitness in st.session_state.fitness_centers:
            container = get_card_view_fitness(
                fitness, lambda f=fitness: (action_by_click_on_fitness(f))
            )


