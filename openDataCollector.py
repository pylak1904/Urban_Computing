import requests
import json
import time
import random
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, db

class OpenDataCollector:
    
    def __init__(self, firebase_config_path, weather_api_key=None, jcdecaux_api_key=None):
        try:
            if not firebase_admin._apps:
                cred = credentials.Certificate(firebase_config_path)
                firebase_admin.initialize_app(cred, {
                    'databaseURL': 'https://cs7ns4-assignment3-pylak-default-rtdb.europe-west1.firebasedatabase.app/'
                })
        except ValueError:
            pass
        
        self.db_ref = db.reference('open_data')
        self.map_ref = db.reference('live_map_stations') 
        
        self.weather_api_key = weather_api_key or 'e134970c8051ece1251fdc280a62154f'
        self.jcdecaux_api_key = jcdecaux_api_key
        
        self.location = {
            'city': 'Dublin',
            'country': 'IE',
            'lat': 53.3498,
            'lon': -6.2603
        }
    
    def fetch_weather_data(self):
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            'lat': self.location['lat'], 
            'lon': self.location['lon'], 
            'appid': self.weather_api_key, 
            'units': 'metric'
        }
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return {
                'timestamp': datetime.now().isoformat(),
                'unix_time': int(datetime.now().timestamp()),
                'location': self.location,
                'temperature': data['main']['temp'],
                'feels_like': data['main']['feels_like'],
                'humidity': data['main']['humidity'],
                'weather': data['weather'][0]['main'],
                'weather_description': data['weather'][0]['description'],
                'wind_speed': data['wind']['speed'],
                'data_source': 'OpenWeatherMap API'
            }
        except:
            return None
    
    def fetch_air_quality_data(self):
        url = "https://api.openweathermap.org/data/2.5/air_pollution"
        params = {
            'lat': self.location['lat'], 
            'lon': self.location['lon'], 
            'appid': self.weather_api_key
        }
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return {
                'timestamp': datetime.now().isoformat(),
                'unix_time': int(datetime.now().timestamp()),
                'location': self.location,
                'aqi': data['list'][0]['main']['aqi'],
                'pm2_5': data['list'][0]['components']['pm2_5'],
                'pm10': data['list'][0]['components']['pm10'],
                'data_source': 'OpenWeatherMap Air Pollution API'
            }
        except:
            return None
    
    def fetch_dublin_bikes_data(self):
        url = "https://api.jcdecaux.com/vls/v1/stations"
        params = {'contract': 'Dublin', 'apiKey': self.jcdecaux_api_key}
        
        try:
            if not self.jcdecaux_api_key or "YOUR_" in self.jcdecaux_api_key:
                raise ValueError("Invalid API Key")

            response = requests.get(url, params=params, timeout=10)

            if response.status_code in (401, 403):
                raise ValueError("API Key Rejected")
                
            response.raise_for_status()
            data = response.json()

            total_stations = len(data)
            total_bikes = sum(st.get('available_bikes', 0) for st in data)
            total_stands = sum(st.get('available_bike_stands', 0) for st in data)
            
            map_stations = []
            for st in data:
                map_stations.append({
                    'name': st.get('name'),
                    'lat': st.get('position', {}).get('lat'),
                    'lng': st.get('position', {}).get('lng'),
                    'bikes': st.get('available_bikes', 0),
                    'status': st.get('status')
                })

            return {
                'summary': {
                    'timestamp': datetime.now().isoformat(),
                    'unix_time': int(datetime.now().timestamp()),
                    'total_stations': total_stations,
                    'total_bikes_available': total_bikes,
                    'total_stands_available': total_stands,
                    'data_source': 'JCDecaux (LIVE)'
                },
                'stations': map_stations
            }
            
        except:
            mock_stations = []
            center_lat, center_lng = 53.3498, -6.2603
            
            for i in range(25):
                lat = center_lat + random.uniform(-0.03, 0.03)
                lng = center_lng + random.uniform(-0.05, 0.05)
                bikes = random.randint(0, 40)
                
                mock_stations.append({
                    'name': f"Mock Station #{i+1}",
                    'lat': lat,
                    'lng': lng,
                    'bikes': bikes,
                    'status': 'OPEN' if bikes > 0 else 'CLOSED'
                })
            
            total_bikes = sum(s['bikes'] for s in mock_stations)
            
            return {
                'summary': {
                    'timestamp': datetime.now().isoformat(),
                    'unix_time': int(datetime.now().timestamp()),
                    'total_stations': 25,
                    'total_bikes_available': total_bikes,
                    'total_stands_available': 500,
                    'data_source': 'Simulated (Mock)'
                },
                'stations': mock_stations
            }
    
    def upload_to_firebase(self, data, data_type):
        if data is None:
            return False
        try:
            date_key = data['timestamp'][:10]
            self.db_ref.child(data_type).child(date_key).push(data)
            return True
        except:
            return False

    def update_live_map(self, stations_data):
        if not stations_data:
            return
        try:
            self.map_ref.set(stations_data)
        except:
            pass

    def collect_continuous(self, interval=300, duration=3600):
        end_time = time.time() + duration
        
        while time.time() < end_time:
            w = self.fetch_weather_data()
            self.upload_to_firebase(w, 'weather')
            
            a = self.fetch_air_quality_data()
            self.upload_to_firebase(a, 'air_quality')
            
            b_data = self.fetch_dublin_bikes_data()
            if b_data:
                self.upload_to_firebase(b_data['summary'], 'dublin_bikes')
                self.update_live_map(b_data['stations'])
            
            time.sleep(interval)

def main():
    FIREBASE_CONFIG = 'firebase_config.json'
    OPENWEATHER_KEY = 'e134970c8051ece1251fdc280a62154f'
    JCDECAUX_KEY = '395978e6740936870577ec05f5de4bd53693e2cc'
    
    collector = OpenDataCollector(FIREBASE_CONFIG, OPENWEATHER_KEY, JCDECAUX_KEY)
    
    try:
        collector.collect_continuous(interval=300, duration=3600)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
