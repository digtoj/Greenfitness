# Green & Fitness

A web application that helps users find fitness centers and nearby electric vehicle charging stations.

## Description

Green & Fitness is an application that allows users to search for fitness centers in various cities across Germany and France, while also showing nearby electric vehicle charging stations. This makes it easier for environmentally conscious users to charge their vehicles while working out.

## Features

- Search for fitness centers in any city in Germany or France
- View fitness centers on an interactive map with heatmap visualization
- Filter fitness centers by chain/brand
- View detailed information about each fitness center
- Find nearby electric vehicle charging stations
- Adjust search radius for charging stations
- Interactive and responsive UI

## Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package installer)

### Setup

1. Copy the repository:
```bash
cd green-fitness
```

2. Activate the virtual environment:
   - On Windows:
   ```bash
   venv\Scripts\activate
   ```
   - On macOS/Linux:
   ```bash
   source venv/bin/activate
   ```

## Running the Application

After setting up the environment, you can start the application with:

```bash
streamlit run streamlit_app.py
```

The application will be available in your web browser at `http://localhost:8501`.

## Project Structure

```
green-fitness/
├── data/
│   ├── fitness_centers_germany.csv
│   └── fitness_centers_france.csv
├── image/
│   ├── logo.png
│   └── auto.png
├── streamlit_app.py       # Main application file
├── openmapapi.py          # Integration with Open Charge Map API
├── fitness_center_data.py # Data processing for fitness centers
├── result_view.py         # UI components for results
├── custom_icon.py         # Custom map icons
├── data.py                # Data constants and paths
├── requirements.txt       # Project dependencies
├── .env                   # API keys (not tracked in git)
└── README.md              # This file
```

## Troubleshooting

If you encounter issues with the application:

1. Make sure your `.env` file is correctly set up with a valid API key
2. Check that all required dependencies are installed
3. Ensure that the data files exist in the correct locations
4. Verify that you have an active internet connection for API calls

## Contributors

- Olivia Nguimdo Dongmo
- Oscar Junior Tsakam

## License

This project is part of a university project at Hochschule Bremen, Faculty 4 – Electrical Engineering and Computer Science.