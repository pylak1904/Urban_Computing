import os
import signal
import subprocess
import sys
import time
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify
import firebase_admin
from firebase_admin import credentials, db
from dataFusionAnalyzer import DataFusionAnalyzer

app = Flask(__name__)

running_processes = {
    "webcam": None,
    "opendata": None
}

if not firebase_admin._apps:
    cred = credentials.Certificate('firebase_config.json')
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://cs7ns4-assignment3-pylak-default-rtdb.europe-west1.firebasedatabase.app/'
    })

analyzer = DataFusionAnalyzer('firebase_config.json')

def background_fusion_loop():
    while True:
        try:
            scored, analysis, recommendation = analyzer.run_complete_analysis(hours_back=24)
            if recommendation:
                ref = db.reference('live_dashboard')
                ref.set({
                    'last_updated': datetime.now().strftime('%H:%M:%S'),
                    'score': recommendation['score'],
                    'text': "GO OUTSIDE" if recommendation['should_go_outside'] else "STAY INSIDE",
                    'reason': recommendation['reason'],
                    'metrics': recommendation['details'],
                    'analysis': analysis
                })
            time.sleep(30)
        except Exception as e:
            print(f"Fusion Error: {e}")
            time.sleep(10)

threading.Thread(target=background_fusion_loop, daemon=True).start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    if email:
        db.reference('app_analytics/logins').push({
            'email': email,
            'timestamp': datetime.now().isoformat(),
            'ip': request.remote_addr
        })
        return jsonify({"status": "success", "message": "Logged in"})
    return jsonify({"status": "error"}), 400

@app.route('/api/control', methods=['POST'])
def control_sensor():
    data = request.json
    sensor_type = data.get('type')
    action = data.get('action')
    
    global running_processes
    
    script_map = {
        'webcam': 'webcamSensorFirebase.py',
        'opendata': 'openDataCollector.py'
    }

    if action == 'start':
        if running_processes[sensor_type] is None:
            cmd = [sys.executable, script_map[sensor_type]]
            proc = subprocess.Popen(cmd)
            running_processes[sensor_type] = proc
            return jsonify({"status": "started", "pid": proc.pid})
        else:
            return jsonify({"status": "already_running"})

    elif action == 'stop':
        proc = running_processes[sensor_type]
        if proc:
            proc.terminate()
            running_processes[sensor_type] = None
            return jsonify({"status": "stopped"})
        else:
            return jsonify({"status": "not_running"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
