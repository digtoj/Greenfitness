import csv
import pandas as pd
from geopy.geocoders import Nominatim

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



