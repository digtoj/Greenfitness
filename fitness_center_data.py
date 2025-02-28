import csv
import pandas as pd

from data import (
    french_country_code,
    french_fitness_centers,
    german_country_code,
    german_fitness_centers,
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


# Function to read fitness centers from CSV
def get_fitness_centers(file_data_path, city):
    df = pd.read_csv(file_data_path)  # Load fitness centers data
    df_filtered = df[df["addr:city"].str.contains(city, case=False, na=False)]
    return df_filtered


def get_fitness_data_by_country_code(country_code=german_country_code, city="Bremen"):
    print("Country Code :" + country_code)
    if country_code == german_country_code:
        fitness_centers = get_fitness_centers(german_fitness_centers, city)
        convert_coordinate(fitness_centers)
        return fitness_centers
    elif country_code == french_country_code:
        fitness_centers = get_fitness_centers(french_country_code, city)
        convert_coordinate(fitness_centers)
        return fitness_centers
