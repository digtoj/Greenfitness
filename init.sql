-- Create the table
CREATE TABLE fitness_centers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    operator VARCHAR(255),
    sport VARCHAR(255),
    city VARCHAR(255),
    coordinates GEOMETRY(Point, 4326),
    address VARCHAR(255),
    contact VARCHAR(255)
);

-- Load the data from the CSV file
COPY fitness_centers (name, operator, sport, city, coordinates, address, contact)
FROM './fitness_centers.csv'
WITH (FORMAT csv, HEADER true);