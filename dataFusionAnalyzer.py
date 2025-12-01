import firebase_admin
from firebase_admin import credentials, db
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from collections import defaultdict

class DataFusionAnalyzer:
    def __init__(self, firebase_config_path='firebase_config.json'):
        try:
            firebase_admin.get_app()
        except ValueError:
            cred = credentials.Certificate(firebase_config_path)
            firebase_admin.initialize_app(cred, {
                'databaseURL': 'https://cs7ns4-assignment3-pylak-default-rtdb.europe-west1.firebasedatabase.app/'
            })
        
        self.motion_ref = db.reference('sensor_data')
        self.weather_ref = db.reference('open_data/weather')
        self.air_quality_ref = db.reference('open_data/air_quality')
        self.bikes_ref = db.reference('open_data/dublin_bikes')
        
        self.weights = {
            'temperature': 0.30,
            'air_quality': 0.35,
            'weather': 0.20,
            'bikes': 0.15
        }

        self.thresholds = {
            'temp_optimal': (12, 22),
            'temp_acceptable': (5, 28),
            'aqi_good': 50,
            'aqi_acceptable': 100,
            'bikes_good': 5,
            'motion_active': 0.5
        }
    
    def fetch_recent_data(self, hours_back=24):
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours_back)
        start_unix = int(start_time.timestamp())
        
        data = {
            'motion': [],
            'weather': [],
            'air_quality': [],
            'bikes': []
        }

        try:
            for i in range(hours_back // 24 + 2):
                date_key = (end_time - timedelta(days=i)).strftime('%Y-%m-%d')
                date_data = self.motion_ref.child(date_key).get()
                if date_data:
                    for _, point in date_data.items():
                        if point.get('unix_time', 0) >= start_unix:
                            data['motion'].append(point)
        except:
            pass

        try:
            for i in range(hours_back // 24 + 2):
                date_key = (end_time - timedelta(days=i)).strftime('%Y-%m-%d')
                date_data = self.weather_ref.child(date_key).get()
                if date_data:
                    for _, point in date_data.items():
                        if point.get('unix_time', 0) >= start_unix:
                            data['weather'].append(point)
        except:
            pass

        try:
            for i in range(hours_back // 24 + 2):
                date_key = (end_time - timedelta(days=i)).strftime('%Y-%m-%d')
                date_data = self.air_quality_ref.child(date_key).get()
                if date_data:
                    for _, point in date_data.items():
                        if point.get('unix_time', 0) >= start_unix:
                            data['air_quality'].append(point)
        except:
            pass

        try:
            for i in range(hours_back // 24 + 2):
                date_key = (end_time - timedelta(days=i)).strftime('%Y-%m-%d')
                date_data = self.bikes_ref.child(date_key).get()
                if date_data:
                    for _, point in date_data.items():
                        if point.get('unix_time', 0) >= start_unix:
                            data['bikes'].append(point)
        except:
            pass
        
        return data
    
    def aggregate_motion_hourly(self, motion_data):
        if not motion_data:
            return pd.DataFrame()
        
        df = pd.DataFrame(motion_data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['hour'] = df['timestamp'].dt.floor('H')
        
        hourly = df.groupby('hour').agg({
            'motion_detected': 'sum',
            'motion_intensity': 'mean',
            'motion_area': 'mean',
            'brightness': 'mean'
        }).reset_index()
        
        hourly.columns = ['hour', 'motion_events', 'avg_intensity', 
                          'avg_area', 'avg_brightness']
        
        return hourly
    
    def fuse_data_sources(self, raw_data):
        motion_hourly = self.aggregate_motion_hourly(raw_data['motion'])
        
        if motion_hourly.empty:
            return pd.DataFrame()
        
        weather_df = pd.DataFrame(raw_data['weather']) if raw_data['weather'] else pd.DataFrame()
        aqi_df = pd.DataFrame(raw_data['air_quality']) if raw_data['air_quality'] else pd.DataFrame()
        bikes_df = pd.DataFrame(raw_data['bikes']) if raw_data['bikes'] else pd.DataFrame()
        
        if not weather_df.empty:
            weather_df['timestamp'] = pd.to_datetime(weather_df['timestamp'])
            weather_df = weather_df.sort_values('timestamp')
            weather_df['hour'] = weather_df['timestamp'].dt.floor('H')
            weather_df = weather_df.groupby('hour').agg({
                'temperature': 'last',
                'humidity': 'last',
                'wind_speed': 'mean',
                'weather': 'last',
                'weather_description': 'last'
            }).reset_index()
        
        if not aqi_df.empty:
            aqi_df['timestamp'] = pd.to_datetime(aqi_df['timestamp'])
            aqi_df = aqi_df.sort_values('timestamp')
            aqi_df['hour'] = aqi_df['timestamp'].dt.floor('H')
            aqi_df = aqi_df.groupby('hour').agg({
                'aqi': 'last',
                'pm2_5': 'last',
                'pm10': 'last'
            }).reset_index()
        
        if not bikes_df.empty:
            bikes_df['timestamp'] = pd.to_datetime(bikes_df['timestamp'])
            bikes_df = bikes_df.sort_values('timestamp')
            bikes_df['hour'] = bikes_df['timestamp'].dt.floor('H')
            bikes_df = bikes_df.groupby('hour').agg({
                'total_bikes_available': 'last',
                'average_occupancy': 'last'
            }).reset_index()
        
        fused = motion_hourly.copy()
        
        if not weather_df.empty:
            fused = fused.merge(weather_df, on='hour', how='left')
        
        if not aqi_df.empty:
            fused = fused.merge(aqi_df, on='hour', how='left')
        
        if not bikes_df.empty:
            fused = fused.merge(bikes_df, on='hour', how='left')
        
        fused = fused.fillna(method='ffill').fillna(method='bfill')
        
        return fused
    
    def score_temperature(self, temp):
        if pd.isna(temp):
            return 50
        
        optimal_min, optimal_max = self.thresholds['temp_optimal']
        accept_min, accept_max = self.thresholds['temp_acceptable']
        
        if optimal_min <= temp <= optimal_max:
            return 100
        elif accept_min <= temp <= accept_max:
            if temp < optimal_min:
                return 50 + 50 * (temp - accept_min) / (optimal_min - accept_min)
            else:
                return 50 + 50 * (accept_max - temp) / (accept_max - optimal_max)
        else:
            return max(0, 50 - abs(temp - 15) * 5)
    
    def score_air_quality(self, aqi):
        if pd.isna(aqi):
            return 50
        
        if aqi <= self.thresholds['aqi_good']:
            return 100
        elif aqi <= self.thresholds['aqi_acceptable']:
            return 100 - 50 * (aqi - self.thresholds['aqi_good']) / \
                   (self.thresholds['aqi_acceptable'] - self.thresholds['aqi_good'])
        else:
            return max(0, 50 * np.exp(-(aqi - self.thresholds['aqi_acceptable']) / 50))
    
    def score_weather(self, weather_condition):
        if pd.isna(weather_condition):
            return 50
        
        weather_scores = {
            'Clear': 100,
            'Clouds': 80,
            'Mist': 60,
            'Fog': 50,
            'Drizzle': 40,
            'Rain': 20,
            'Thunderstorm': 10,
            'Snow': 30
        }
        
        return weather_scores.get(weather_condition, 50)
    
    def score_bikes(self, bikes_available):
        if pd.isna(bikes_available):
            return 50
        
        if bikes_available >= self.thresholds['bikes_good']:
            return 100
        elif bikes_available > 0:
            return 50 + 50 * (bikes_available / self.thresholds['bikes_good'])
        else:
            return 25
    
    def calculate_outdoor_score(self, fused_data):
        if fused_data.empty:
            return fused_data
        
        df = fused_data.copy()
        
        df['temp_score'] = df['temperature'].apply(self.score_temperature)
        df['aqi_score'] = df['aqi'].apply(self.score_air_quality)
        df['weather_score'] = df['weather'].apply(self.score_weather)
        df['bikes_score'] = df['total_bikes_available'].apply(self.score_bikes)
        
        df['outdoor_score'] = (
            df['temp_score'] * self.weights['temperature'] +
            df['aqi_score'] * self.weights['air_quality'] +
            df['weather_score'] * self.weights['weather'] +
            df['bikes_score'] * self.weights['bikes']
        )
        
        df['outdoor_score'] = df['outdoor_score'].round(1)
        
        return df
    
    def analyze_patterns(self, scored_data):
        if scored_data.empty or len(scored_data) < 2:
            return {}
        
        analysis = {}
        
        if 'outdoor_score' in scored_data.columns and 'motion_events' in scored_data.columns:
            corr = scored_data['motion_events'].corr(scored_data['outdoor_score'])
            analysis['motion_outdoor_correlation'] = round(corr, 3)
            
            if corr < -0.3:
                analysis['pattern_insight'] = "Strong inverse correlation"
            elif corr > 0.3:
                analysis['pattern_insight'] = "Positive correlation"
            else:
                analysis['pattern_insight'] = "Weak correlation"
        
        high_activity = scored_data[scored_data['motion_events'] > scored_data['motion_events'].median()]
        if not high_activity.empty:
            analysis['high_activity_avg_score'] = round(high_activity['outdoor_score'].mean(), 1)
            analysis['high_activity_avg_temp'] = round(high_activity['temperature'].mean(), 1)
        
        good_conditions = scored_data[scored_data['outdoor_score'] >= 70]
        analysis['good_condition_hours'] = len(good_conditions)
        analysis['good_condition_percentage'] = round(len(good_conditions) / len(scored_data) * 100, 1)
        
        if 'motion_events' in scored_data.columns:
            high_motion_threshold = scored_data['motion_events'].quantile(0.75)
            missed = scored_data[
                (scored_data['outdoor_score'] >= 70) & 
                (scored_data['motion_events'] > high_motion_threshold)
            ]
            analysis['missed_opportunities'] = len(missed)
        
        return analysis
    
    def get_current_recommendation(self, scored_data):
        if scored_data.empty:
            return {
                'should_go_outside': False,
                'score': 0,
                'reason': 'No data available',
                'details': {}
            }
        
        latest = scored_data.iloc[-1]
        score = latest['outdoor_score']
        
        if score >= 80:
            recommendation = {
                'should_go_outside': True,
                'score': score,
                'reason': 'Excellent outdoor conditions',
                'urgency': 'high'
            }
        elif score >= 60:
            recommendation = {
                'should_go_outside': True,
                'score': score,
                'reason': 'Good outdoor conditions',
                'urgency': 'medium'
            }
        elif score >= 40:
            recommendation = {
                'should_go_outside': False,
                'score': score,
                'reason': 'Acceptable but not ideal',
                'urgency': 'low'
            }
        else:
            recommendation = {
                'should_go_outside': False,
                'score': score,
                'reason': 'Poor conditions',
                'urgency': 'none'
            }
        
        recommendation['details'] = {
            'temperature': f"{latest['temperature']:.1f}°C",
            'aqi': int(latest['aqi']),
            'weather': latest['weather'],
            'bikes_available': int(latest['total_bikes_available']),
            'timestamp': latest['hour'].strftime('%Y-%m-%d %H:%M')
        }
        
        return recommendation
    
    def run_complete_analysis(self, hours_back=24):
        raw_data = self.fetch_recent_data(hours_back)
        fused_data = self.fuse_data_sources(raw_data)
        
        if fused_data.empty:
            return None, None, None
        
        scored_data = self.calculate_outdoor_score(fused_data)
        analysis = self.analyze_patterns(scored_data)
        recommendation = self.get_current_recommendation(scored_data)
        
        return scored_data, analysis, recommendation


def main():
    try:
        analyzer = DataFusionAnalyzer('firebase_config.json')
        scored_data, analysis, recommendation = analyzer.run_complete_analysis(hours_back=48)
        
        if scored_data is not None:
            print("\nAnalysis Results")
            print(f"Total data points: {len(scored_data)}")
            print("\nPattern Insights:")
            for key, value in analysis.items():
                print(f"{key}: {value}")
            
            print("\nCurrent Recommendation:")
            print(f"Should go outside: {recommendation['should_go_outside']}")
            print(f"Outdoor score: {recommendation['score']}")
            print(f"Reason: {recommendation['reason']}")
            
            print("\nConditions:")
            for key, value in recommendation['details'].items():
                print(f"{key}: {value}")
            
            scored_data.to_csv('fused_data_analysis.csv', index=False)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
