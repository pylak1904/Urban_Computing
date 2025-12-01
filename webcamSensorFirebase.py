import cv2
import numpy as np
import csv
import os
from datetime import datetime
import time
import firebase_admin
from firebase_admin import credentials, db

class MotionSensorFirebase:
    
    def __init__(self, firebase_config_path='firebase_config.json'):
        self.cap = None
        self.previous_frame = None
        self.data_points = []
        self.is_collecting = False
        self.frame_count = 0
        self.firebase_enabled = False
        self.db_ref = None
        self.initialize_firebase(firebase_config_path)
    
    def initialize_firebase(self, config_path):
        try:
            if not os.path.exists(config_path):
                print(f"Firebase config not found: {config_path}")
                print("Will save data locally only")
                return False
            
            cred = credentials.Certificate(config_path)
            firebase_admin.initialize_app(cred, {
                'databaseURL': 'https://cs7ns4-assignment3-pylak-default-rtdb.europe-west1.firebasedatabase.app/'
            })
            
            self.db_ref = db.reference('sensor_data')
            self.firebase_enabled = True
            return True
            
        except Exception as e:
            print(f"Firebase initialization failed: {e}")
            print("Will save data locally only")
            return False
    
    def initialize_camera(self):
        self.cap = cv2.VideoCapture(0)
        
        if not self.cap.isOpened():
            print("Error: Could not open webcam")
            return False
        
        time.sleep(2)
        
        ret, frame = self.cap.read()
        if ret:
            self.previous_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            self.previous_frame = cv2.GaussianBlur(self.previous_frame, (21, 21), 0)
            return True
        else:
            print("Error: Could not read from webcam")
            return False
    
    def detect_motion(self):
        ret, frame = self.cap.read()
        if not ret:
            return None
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        
        frame_delta = cv2.absdiff(self.previous_frame, gray)
        threshold = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
        threshold = cv2.dilate(threshold, None, iterations=2)
        
        contours, _ = cv2.findContours(
            threshold.copy(), 
            cv2.RETR_EXTERNAL, 
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        motion_detected = 0
        total_motion_area = 0
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > 500:
                motion_detected = 1
                total_motion_area += area
                (x, y, w, h) = cv2.boundingRect(contour)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        
        frame_area = frame.shape[0] * frame.shape[1]
        motion_intensity = min(100, (total_motion_area / frame_area) * 1000)
        brightness = np.mean(gray)
        
        status_color = (0, 255, 0) if self.firebase_enabled else (0, 165, 255)
        
        cv2.putText(frame, f"Motion: {'YES' if motion_detected else 'NO'}", 
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(frame, f"Intensity: {motion_intensity:.1f}", 
                    (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(frame, f"Points: {len(self.data_points)}", 
                    (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        firebase_status = "Firebase: CONNECTED" if self.firebase_enabled else "Firebase: LOCAL ONLY"
        cv2.putText(frame, firebase_status, 
                    (10, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
        
        cv2.imshow('Motion Sensor', frame)
        
        self.previous_frame = gray
        
        return motion_detected, motion_intensity, total_motion_area, brightness
    
    def upload_to_firebase(self, data_point):
        if not self.firebase_enabled:
            return False
        
        try:
            date_key = data_point['timestamp'][:10]
            self.db_ref.child(date_key).push(data_point)
            return True
            
        except Exception as e:
            print(f"Firebase upload failed: {e}")
            return False
    
    def collect_data(self, target_points=1200, upload_interval=1):
        self.is_collecting = True
        upload_counter = 0
        
        while self.is_collecting:
            result = self.detect_motion()
            
            if result is not None:
                motion_detected, motion_intensity, motion_area, brightness = result
                
                timestamp = datetime.now().isoformat()
                data_point = {
                    'timestamp': timestamp,
                    'unix_time': int(datetime.now().timestamp()),
                    'motion_detected': motion_detected,
                    'motion_intensity': round(motion_intensity, 2),
                    'motion_area': int(motion_area),
                    'brightness': round(brightness, 2),
                    'sensor_type': 'webcam_motion',
                    'device_id': 'webcam_001'
                }
                
                self.data_points.append(data_point)
                upload_counter += 1
                
                if self.firebase_enabled and upload_counter >= upload_interval:
                    self.upload_to_firebase(data_point)
                    upload_counter = 0
                
                if len(self.data_points) >= target_points:
                    print(f"Target reached: {len(self.data_points)} points")
                    self.is_collecting = False
            
            key = cv2.waitKey(30) & 0xFF
            if key == ord('q') or key == ord('Q'):
                self.is_collecting = False
            elif key == ord('s') or key == ord('S'):
                self.save_data()
    
    def save_data(self):
        if not self.data_points:
            print("No data to save")
            return
        
        data_dir = 'data'
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = os.path.join(data_dir, f'motion_sensor_data_{timestamp}.csv')
        
        with open(filename, 'w', newline='') as csvfile:
            fieldnames = [
                'timestamp', 'unix_time', 'motion_detected', 
                'motion_intensity', 'motion_area', 
                'brightness', 'sensor_type', 'device_id'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.data_points)
        
        print("Data saved")
        print(f"File: {filename}")
        print(f"Points: {len(self.data_points)}")
        
        return filename
    
    def cleanup(self):
        if self.cap is not None:
            self.cap.release()
        cv2.destroyAllWindows()


def main():
    FIREBASE_CONFIG = 'firebase_config.json'
    TARGET_POINTS = 1200
    UPLOAD_INTERVAL = 5
    
    collector = MotionSensorFirebase(FIREBASE_CONFIG)
    
    if not collector.initialize_camera():
        print("Failed to initialize webcam")
        return
    
    try:
        collector.collect_data(
            target_points=TARGET_POINTS,
            upload_interval=UPLOAD_INTERVAL
        )
        
        if collector.data_points:
            print(f"Total data points collected: {len(collector.data_points)}")
            
            save_choice = input("Save final data to CSV? (Y/n): ").strip().lower()
            if save_choice != 'n':
                collector.save_data()
        else:
            print("No data collected")
    
    except KeyboardInterrupt:
        if collector.data_points:
            collector.save_data()
    
    except Exception as e:
        import traceback
        traceback.print_exc()
    
    finally:
        collector.cleanup()


if __name__ == '__main__':
    main()
