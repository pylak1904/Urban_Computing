import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataFusionAnalyzer import DataFusionAnalyzer
import requests
import json

class OutdoorForecastPredictor:
    
    def __init__(self, firebase_config_path='firebase_config.json', api_key=None):
        self.analyzer = DataFusionAnalyzer(firebase_config_path)
        self.api_key = api_key or 'e134970c8051ece1251fdc280a62154f'
        
        self.location = {
            'lat': 53.3498,
            'lon': -6.2603
        }
    
    def fetch_weather_forecast(self, hours=48):
        url = "https://api.openweathermap.org/data/2.5/forecast"
        
        params = {
            'lat': self.location['lat'],
            'lon': self.location['lon'],
            'appid': self.api_key,
            'units': 'metric',
            'cnt': min(hours // 3, 40)
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            forecasts = []
            
            for item in data['list']:
                forecast = {
                    'timestamp': datetime.fromtimestamp(item['dt']),
                    'unix_time': item['dt'],
                    'temperature': item['main']['temp'],
                    'feels_like': item['main']['feels_like'],
                    'humidity': item['main']['humidity'],
                    'weather': item['weather'][0]['main'],
                    'weather_description': item['weather'][0]['description'],
                    'wind_speed': item['wind']['speed'],
                    'clouds': item['clouds']['all'],
                    'pop': item.get('pop', 0) * 100
                }
                forecasts.append(forecast)
            
            return forecasts
            
        except:
            return self._generate_mock_forecast(hours)
    
    def _generate_mock_forecast(self, hours):
        base_time = datetime.now()
        forecasts = []
        
        for i in range(hours // 3):
            timestamp = base_time + timedelta(hours=i*3)
            hour_of_day = timestamp.hour
            temp = 12 + 6 * np.sin((hour_of_day - 6) * np.pi / 12)
            
            forecast = {
                'timestamp': timestamp,
                'unix_time': int(timestamp.timestamp()),
                'temperature': round(temp, 1),
                'feels_like': round(temp - 2, 1),
                'humidity': 70,
                'weather': np.random.choice(['Clear', 'Clouds', 'Rain'], p=[0.5, 0.3, 0.2]),
                'weather_description': 'Simulated forecast',
                'wind_speed': round(np.random.uniform(3, 8), 1),
                'clouds': np.random.randint(0, 100),
                'pop': round(np.random.uniform(0, 50), 1)
            }
            forecasts.append(forecast)
        
        return forecasts
    
    def fetch_air_quality_forecast(self):
        url = "https://api.openweathermap.org/data/2.5/air_pollution"
        
        params = {
            'lat': self.location['lat'],
            'lon': self.location['lon'],
            'appid': self.api_key
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            current_aqi = data['list'][0]['main']['aqi']
            return current_aqi
            
        except:
            return 2
    
    def predict_outdoor_scores(self, forecast_data, baseline_aqi=2):
        predictions = []
        
        aqi_to_pm25 = {1: 12, 2: 35, 3: 55, 4: 150, 5: 250}
        estimated_aqi_value = aqi_to_pm25.get(baseline_aqi, 50)
        
        for forecast in forecast_data:
            hour_of_day = forecast['timestamp'].hour
            
            if 7 <= hour_of_day <= 9 or 17 <= hour_of_day <= 19:
                bikes_available = np.random.randint(800, 1000)
            elif 22 <= hour_of_day or hour_of_day <= 6:
                bikes_available = np.random.randint(1200, 1500)
            else:
                bikes_available = np.random.randint(1000, 1300)
            
            temp_score = self.analyzer.score_temperature(forecast['temperature'])
            aqi_score = self.analyzer.score_air_quality(estimated_aqi_value)
            weather_score = self.analyzer.score_weather(forecast['weather'])
            bikes_score = self.analyzer.score_bikes(bikes_available)
            
            if forecast['pop'] > 50:
                weather_score *= 0.6
            
            outdoor_score = (
                temp_score * self.analyzer.weights['temperature'] +
                aqi_score * self.analyzer.weights['air_quality'] +
                weather_score * self.analyzer.weights['weather'] +
                bikes_score * self.analyzer.weights['bikes']
            )
            
            hours_ahead = (forecast['timestamp'] - datetime.now()).total_seconds() / 3600
            confidence = max(0.5, 1.0 - (hours_ahead / 48) * 0.4)
            
            prediction = {
                'timestamp': forecast['timestamp'],
                'hour_label': forecast['timestamp'].strftime('%a %H:%M'),
                'temperature': forecast['temperature'],
                'weather': forecast['weather'],
                'weather_description': forecast['weather_description'],
                'pop': forecast['pop'],
                'temp_score': round(temp_score, 1),
                'aqi_score': round(aqi_score, 1),
                'weather_score': round(weather_score, 1),
                'bikes_score': round(bikes_score, 1),
                'outdoor_score': round(outdoor_score, 1),
                'confidence': round(confidence, 2),
                'bikes_estimated': bikes_available
            }
            
            predictions.append(prediction)
        
        df = pd.DataFrame(predictions)
        return df
    
    def identify_optimal_windows(self, predictions, min_score=70, min_duration_hours=2):
        if predictions.empty:
            return []
        
        predictions['is_good'] = predictions['outdoor_score'] >= min_score
        
        windows = []
        current_window = None
        
        for idx, row in predictions.iterrows():
            if row['is_good']:
                if current_window is None:
                    current_window = {
                        'start_time': row['timestamp'],
                        'start_score': row['outdoor_score'],
                        'scores': [row['outdoor_score']],
                        'hours': [row['hour_label']],
                        'conditions': [row['weather']]
                    }
                else:
                    current_window['scores'].append(row['outdoor_score'])
                    current_window['hours'].append(row['hour_label'])
                    current_window['conditions'].append(row['weather'])
            else:
                if current_window is not None:
                    current_window['end_time'] = predictions.iloc[idx-1]['timestamp']
                    current_window['duration_hours'] = len(current_window['scores']) * 3
                    current_window['avg_score'] = np.mean(current_window['scores'])
                    current_window['max_score'] = max(current_window['scores'])
                    
                    if current_window['duration_hours'] >= min_duration_hours:
                        windows.append(current_window)
                    
                    current_window = None
        
        if current_window is not None:
            current_window['end_time'] = predictions.iloc[-1]['timestamp']
            current_window['duration_hours'] = len(current_window['scores']) * 3
            current_window['avg_score'] = np.mean(current_window['scores'])
            current_window['max_score'] = max(current_window['scores'])
            
            if current_window['duration_hours'] >= min_duration_hours:
                windows.append(current_window)
        
        windows.sort(key=lambda x: x['avg_score'], reverse=True)
        
        return windows
    
    def generate_forecast_report(self, predictions, windows):
        if predictions.empty:
            return {
                'summary': 'No forecast data available',
                'windows': [],
                'overall_outlook': 'Unknown'
            }
        
        avg_score = predictions['outdoor_score'].mean()
        
        if avg_score >= 70:
            outlook = "Excellent - Multiple good opportunities ahead"
        elif avg_score >= 55:
            outlook = "Good - Several favorable windows expected"
        elif avg_score >= 40:
            outlook = "Mixed - Some opportunities but watch conditions"
        else:
            outlook = "Poor - Limited favorable conditions expected"
        
        best_time = predictions.loc[predictions['outdoor_score'].idxmax()]
        worst_time = predictions.loc[predictions['outdoor_score'].idxmin()]
        
        report = {
            'summary': {
                'avg_score': round(avg_score, 1),
                'outlook': outlook,
                'best_time': {
                    'when': best_time['hour_label'],
                    'score': best_time['outdoor_score'],
                    'conditions': f"{best_time['temperature']:.1f}°C, {best_time['weather']}"
                },
                'worst_time': {
                    'when': worst_time['hour_label'],
                    'score': worst_time['outdoor_score'],
                    'conditions': f"{worst_time['temperature']:.1f}°C, {worst_time['weather']}"
                }
            },
            'windows': windows,
            'hourly_predictions': predictions.to_dict('records')
        }
        
        return report
    
    def run_prediction(self, forecast_hours=48):
        forecast_data = self.fetch_weather_forecast(forecast_hours)
        baseline_aqi = self.fetch_air_quality_forecast()
        predictions = self.predict_outdoor_scores(forecast_data, baseline_aqi)
        windows = self.identify_optimal_windows(predictions, min_score=70, min_duration_hours=3)
        report = self.generate_forecast_report(predictions, windows)
        return predictions, windows, report
    
    def print_report(self, report):
        summary = report['summary']
        
        print(f"Overall Outlook: {summary['outlook']}")
        print(f"Average Score: {summary['avg_score']}/100\n")
        
        print(f"Best Time: {summary['best_time']['when']}")
        print(f"  Score: {summary['best_time']['score']}/100")
        print(f"  Conditions: {summary['best_time']['conditions']}\n")
        
        print(f"Worst Time: {summary['worst_time']['when']}")
        print(f"  Score: {summary['worst_time']['score']}/100")
        print(f"  Conditions: {summary['worst_time']['conditions']}\n")
        
        if report['windows']:
            print(f"Optimal Outdoor Windows ({len(report['windows'])} found):")
            for i, window in enumerate(report['windows'], 1):
                print(f"\n{i}. {window['start_time'].strftime('%a %d %b, %H:%M')} - "
                      f"{window['end_time'].strftime('%H:%M')}")
                print(f"   Duration: {window['duration_hours']} hours")
                print(f"   Avg Score: {window['avg_score']:.1f}/100")
                print(f"   Max Score: {window['max_score']:.1f}/100")
                print(f"   Conditions: {', '.join(set(window['conditions']))}")
        else:
            print("No optimal windows found.")
    
def main():
    try:
        predictor = OutdoorForecastPredictor('firebase_config.json')
        predictions, windows, report = predictor.run_prediction(forecast_hours=48)
        predictor.print_report(report)
        predictions.to_csv('outdoor_forecast_predictions.csv', index=False)
        
        with open('forecast_report.json', 'w') as f:
            json_report = report.copy()
            if 'hourly_predictions' in json_report:
                for pred in json_report['hourly_predictions']:
                    if 'timestamp' in pred:
                        pred['timestamp'] = pred['timestamp'].isoformat()
            json.dump(json_report, f, indent=2, default=str)
        
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
