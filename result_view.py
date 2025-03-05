import streamlit as st
import pandas as pd
import numpy as np
import time

image_url = "https://t3.ftcdn.net/jpg/01/01/17/76/360_F_101177628_I1DfitC3zR8p9c618oWfYjAuWXK5KDxS.jpg"


def clean_data(value, default="N/A"):
    return default if (pd.isna(value) or value in [None, ""]) else str(value)


def show_container_veiw(title, description, address, id, action_handler):
    id = str(time.time_ns() * 1000)
    id = description + "" + id
    container = st.container(border=True, key=id)
    with container:
        cols = st.columns([2, 1, 1])
        with cols[0]:
            with st.popover(title):
                st.markdown(f"**{title}**")
                st.markdown(description.replace("\n", "  \n"))
        with cols[1]:
            st.write(address)
        with cols[2]:
            st.button(
                "🗺️",
                key=f"btn_{id}",
                help="Auf der karte anzeigen",
                on_click=action_handler,
            )

    return container


def show_details_of_fitness(title, description):
    with st.container(border=True):
        st.markdown(f"**{title}**")
        st.markdown(description.replace("\n", "  \n"))


def get_show_details_fitness(fitness_data):
    # Check if fitness_data is None before trying to access its attributes
    if fitness_data is None:
        st.info("Kein Fitnessstudio ausgewählt.")
        return
        
    title = clean_data(fitness_data.get("name", ""), "Unbekanntes Studio")
    address_parts = [
        clean_data(fitness_data.get("addr:street", "")),
        clean_data(fitness_data.get("addr:housenumber", "")),
    ]
    address = " ".join(filter(None, address_parts))

    details = [
        f"📍 {address}",
        f"⏰ {clean_data(fitness_data.get('opening_hours', ''), 'Keine Angabe')}",
        f"📞 {clean_data(fitness_data.get('contact:phone', ''), 'Keine Angabe')}",
        f"🌍 {clean_data(fitness_data.get('website', ''), 'Keine Angabe')}",
    ]

    show_details_of_fitness(title, "\n".join(details))


def get_card_view_fitness(fitness_data, action_handler):
    if not fitness_data:  # Check if dictionary is empty
        return st.warning("Keine Daten verfügbar")

    title = clean_data(fitness_data.get("name", ""), "Unbekanntes Studio")
    address_parts = [
        clean_data(fitness_data.get("addr:street", "")),
        clean_data(fitness_data.get("addr:housenumber", "")),
    ]
    address = " ".join(filter(None, address_parts))

    details = [
        f"📍 {address}",
        f"⏰ {clean_data(fitness_data.get('opening_hours', ''), 'Keine Angabe')}",
        f"📞 {clean_data(fitness_data.get('contact:phone', ''), 'Keine Angabe')}",
        f"🌍 {clean_data(fitness_data.get('website', ''), 'Keine Angabe')}",
    ]

    show_container_veiw(
        title=title,
        description="\n".join(details),
        address=address,
        id=fitness_data.get("id"),
        action_handler=action_handler,
    )