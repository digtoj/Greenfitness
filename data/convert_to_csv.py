
import json
import pandas as pd

# Load the GeoJSON file
geojson_file = "fitness_centers_france.geojson"  # Change this to your file name
csv_file = "fitness_centers_france.csv"  # Output file

with open(geojson_file, "r", encoding="utf-8") as f:
    data = json.load(f)

# Extract features
features = data.get("features", [])

# Convert to a DataFrame
rows = []
for feature in features:
    props = feature.get("properties", {})  # Handle missing properties safely
    
    # Check if the geometry is a Point
    geometry = feature.get("geometry", {})
    if geometry.get("type") == "Point":
        coords = geometry.get("coordinates", [None, None])
        props["longitude"] = coords[0]
        props["latitude"] = coords[1]
        rows.append(props)

# Create a DataFrame
df = pd.DataFrame(rows)

# Save to CSV
df.to_csv(csv_file, index=False, encoding="utf-8")

print(f"Conversion complete! CSV saved as '{csv_file}'.")
