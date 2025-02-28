FROM postgis/postgis:13-3.1

COPY init.sql /docker-entrypoint-initdb.d/
COPY fitness_centers.csv /data/fitness_centers.csv
