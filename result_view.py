import streamlit as st
import pandas as pd
import numpy as np

image_url = "https://t3.ftcdn.net/jpg/01/01/17/76/360_F_101177628_I1DfitC3zR8p9c618oWfYjAuWXK5KDxS.jpg"




def clean_data(value, default="N/A"):
    return default if (pd.isna(value) or value in [None, ""]) else str(value)


def show_container_veiw(title, description, address, action_handler):
    container = st.container(border=True, key=description)
    with container:
        cols = st.columns([1, 2, 1])
        with cols[0]:
            st.image(image_url, width=50)
        with cols[1]:
            with st.popover(title):
                st.markdown(f"**{title}**")
                st.markdown(description.replace("\n", "  \n"))
            st.write(address)
        with cols[2]:
            if st.button("🗺️ auf der Karte", key=f"btn_{description}"):
                action_handler()
    return container

 

def get_card_view_fitness(fitness_data, action_handler):
    if not fitness_data:
        return st.warning("Keine Daten verfügbar")
    
    title = clean_data(fitness_data["name"], "Unbekanntes Studio")
    address_parts = [
        clean_data(fitness_data.get("addr:street")),
        clean_data(fitness_data.get("addr:housenumber")),
        clean_data(fitness_data.get("addr:country"))
    ]
    address = " ".join(filter(None, address_parts))
    
    details = [
        f"📍 {address}",
        f"⏰ {clean_data(fitness_data.get('opening_hours'), 'Keine Angabe')}",
        f"📞 {clean_data(fitness_data.get('contact:phone'))}",
        f"🌍 {clean_data(fitness_data.get('website'))}"
    ]
    
    show_container_veiw(
        title=title,
        description="\n".join(details),
        address=address,
        action_handler=action_handler
    )