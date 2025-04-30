from flask import Flask, render_template, jsonify, request, send_file
import sqlite3
import subprocess
from datetime import datetime
import csv

# Flask app
app = Flask(__name__)

# Constants
REFERENCE_RSSI = -50  # dBm (RSSI at 1m distance)
PATH_LOSS_EXPONENT = 2  # Path loss exponent (adjust for obstructions)
DB_FILE = "wifi_signal_log.db"

def setup_database():
    """Set up SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wifi_signal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            ssid TEXT,
            rssi INTEGER,
            distance REAL
        )
    ''')
    conn.commit()
    conn.close()

def get_wifi_signal():
    """Fetch WiFi signal strength and SSID."""
    try:
        result = subprocess.check_output(["nmcli", "-t", "-f", "SSID,SIGNAL", "device", "wifi"], text=True)
        lines = result.strip().split("\n")
        wifi_info = []
        for line in lines:
            ssid, signal = line.split(":")
            wifi_info.append((ssid, int(signal)))
        return wifi_info
    except Exception as e:
        print(f"Error fetching WiFi signal: {e}")
        return []

def calculate_distance(rssi):
    """Calculate distance based on RSSI."""
    try:
        # Normalize RSSI if positive
        if rssi > 0:
            rssi = rssi - 100  # Adjusting to typical negative range
        
        # Calculate distance in meters
        exponent = (REFERENCE_RSSI - rssi) / (10 * PATH_LOSS_EXPONENT)
        distance_meters = 10 ** exponent
        
        # Convert meters to feet
        distance_feet = distance_meters * 3.28084
        
        print(f"DEBUG: RSSI={rssi}, Exponent={exponent}, Distance (meters)={distance_meters}, Distance (feet)={distance_feet}")
        return round(distance_feet, 2)
    except Exception as e:
        print(f"Error in distance calculation: {e}")
        return 0



def log_to_database(ssid, rssi, distance):
    """Log the WiFi signal data to the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('INSERT INTO wifi_signal (timestamp, ssid, rssi, distance) VALUES (?, ?, ?, ?)', 
                   (timestamp, ssid, rssi, distance))
    conn.commit()
    conn.close()

def fetch_logs(filter_ssid=None):
    """Fetch logs from the database with optional SSID filter."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if filter_ssid:
        cursor.execute('SELECT * FROM wifi_signal WHERE ssid = ? ORDER BY timestamp DESC', (filter_ssid,))
    else:
        cursor.execute('SELECT * FROM wifi_signal ORDER BY timestamp DESC')
    rows = cursor.fetchall()
    conn.close()
    return rows

def export_logs_to_csv():
    """Export logs to a CSV file."""
    logs = fetch_logs()
    csv_file = "wifi_signal_logs.csv"
    with open(csv_file, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["ID", "Timestamp", "SSID", "RSSI (dBm)", "Distance (m)"])
        writer.writerows(logs)
    return csv_file

@app.route('/')
def index():
    """Render the main page."""
    filter_ssid = request.args.get('ssid', None)
    logs = fetch_logs(filter_ssid=filter_ssid)
    return render_template('index.html', logs=logs, filter_ssid=filter_ssid)

@app.route('/scan')
def scan():
    """Scan for WiFi signals and log them."""
    wifi_signals = get_wifi_signal()
    if wifi_signals:
        for ssid, rssi in wifi_signals:
            # Filter out weak signals
            if rssi < -80:
                continue
            distance = calculate_distance(rssi)
            log_to_database(ssid, rssi, distance)
    return jsonify({"status": "Scan complete"})

@app.route('/export')
def export_logs():
    """Export logs to CSV and provide download link."""
    csv_file = export_logs_to_csv()
    return send_file(csv_file, as_attachment=True)

@app.route('/logs')
def logs():
    """Return logs as JSON."""
    filter_ssid = request.args.get('ssid', None)
    logs = fetch_logs(filter_ssid=filter_ssid)
    log_list = [{"id": row[0], "timestamp": row[1], "ssid": row[2], "rssi": row[3], "distance": row[4]} for row in logs]
    return jsonify(log_list)

@app.route('/debug')
def debug_logs():
    """Debug route to fetch current WiFi data with distance calculations."""
    wifi_signals = get_wifi_signal()
    debug_data = []
    for ssid, rssi in wifi_signals:
        if rssi < -80:  # Filter weak signals
            continue
        distance = calculate_distance(rssi)
        debug_data.append({"SSID": ssid, "RSSI": rssi, "Distance": distance})
    return jsonify(debug_data)

if __name__ == "__main__":
    setup_database()
    app.run(debug=True)
