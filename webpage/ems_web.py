from flask import Flask, render_template, jsonify, request
from gpiozero import OutputDevice # type: ignore
import time
import threading

app = Flask(__name__)

# GPIO Setup (BCM numbering)
RELAYS = {
    "solar": OutputDevice(17, active_high=False),
    "grid": OutputDevice(18, active_high=False),
    "battery": OutputDevice(27, active_high=False),
    "load": OutputDevice(22, active_high=False)
}

# System state
system_state = {
    "mode": "auto",
    "power_source": "solar",
    "battery_voltage": 12.4,
    "relay_status": {name: device.value for name, device in RELAYS.items()}
}

# Simulation parameters (replace with real sensors)
def simulate_system():
    while True:
        # Simulate battery drain/charge
        if system_state["power_source"] == "solar":
            system_state["battery_voltage"] = min(12.8, system_state["battery_voltage"] + 0.01)
        else:
            system_state["battery_voltage"] = max(10.5, system_state["battery_voltage"] - 0.02)
        
        time.sleep(5)

# Start simulation thread
sim_thread = threading.Thread(target=simulate_system, daemon=True)
sim_thread.start()

@app.route('/')
def dashboard():
    return render_template('dashboard.html', state=system_state)

@app.route('/status')
def get_status():
    system_state["relay_status"] = {name: device.value for name, device in RELAYS.items()}
    return jsonify(system_state)

@app.route('/control', methods=['POST'])
def control():
    data = request.json
    
    if "mode" in data:
        system_state["mode"] = data["mode"]
    
    if "relay" in data and "state" in data:
        relay_name = data["relay"]
        state = data["state"]
        
        if relay_name in RELAYS:
            RELAYS[relay_name].value = state
            system_state["power_source"] = relay_name if state else "none"
    
    return jsonify(success=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)