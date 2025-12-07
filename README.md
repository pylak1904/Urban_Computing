Urban Advisor - Assignment 4

Overview

"Urban Advisor" is an intelligent outdoor activity recommendation system developed for CS7NS4 (Urban Computing). It fuses real-time sensor data from a webcam (motion detection) with open data from APIs (Weather, Air Quality, Dublin Bikes) to calculate an "Outdoor Suitability Score" (0-100). The system features a live dashboard with geospatial visualization and predictive forecasting.

Installation & Setup

Unzip the submission folder to your desired location.

Install Dependencies:
Open a terminal/command prompt in the project folder and run:

pip install -r requirements.txt


Ensure you have Python 3.8+ installed.

Verify Configuration:
Ensure firebase_config.json is present in the root directory. This file contains the credentials required to connect to the Firebase Realtime Database.

Running the Application

To start the full system, you need to run the web server.

Start the Backend Server:
In your terminal, run:

python app.py


You should see output indicating the server is running on http://127.0.0.1:5000.

Access the Dashboard:
Open your web browser (Chrome/Firefox recommended) and go to:
http://127.0.0.1:5000

Login:
Enter any valid email address to access the dashboard.

Using the System (Demonstration Steps)

Once logged in, follow these steps to demonstrate the full functionality:

Start Data Collection (Actuation):

On the left sidebar ("Control Center"), click the "Start Stream" button.

Wait ~5-10 seconds. You will see the "Live Bike Stations" map populate with green/red markers, and the metric cards (Temp, AQI) will update with live data.

Optional: Click "Start Camera" to activate the motion sensor (webcam).

View Recommendations:

Observe the large colored banner at the top. It will display a score (0-100) and a clear recommendation ("GO OUTSIDE" or "STAY INSIDE") based on the fused data.

Map Interaction:

Click the Crosshairs Icon (top-left of map) to zoom to your current location.

Click on any Bike Station marker to see the number of available bikes.

Click "Get Directions" in the popup to draw a route from your location to the station.

View Forecast (Extra Task):

Scroll down to the "AI Analysis" section or view the generated forecast_report.json to see the 48-hour predictive analysis.

File Structure

app.py: Main Flask web server and backend logic.

templates/index.html: The frontend dashboard (React + Leaflet Maps).

dataFusionAnalyzer.py: Core logic for data fusion, scoring algorithms, and pattern detection.

openDataCollector.py: Script to fetch live data from APIs (Weather, Bikes) and upload to Firebase.

webcamSensorFirebase.py: Script for motion detection using the webcam.

predictiveForecaster.py: Module for generating 48-hour outdoor suitability forecasts.

requirements.txt: Python library dependencies.

Troubleshooting

Map shows "0 Stations": Ensure you clicked "Start Stream". If the API key fails, the system will automatically switch to generating mock data after a short timeout.

"Connection Error" on Login: Ensure app.py is running in your terminal.

Webcam not starting: Check if another application (like Zoom/Teams) is using your camera.

Credits

Student: Keshwith Pyla (25352427)
Module: CS7NS4 Urban Computing