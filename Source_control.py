import lgpio
import time
from flask import Flask, request, jsonify
from threading import Lock

app = Flask(__name__)
gpio_lock = Lock()

# GPIO Setup with descriptive naming
RELAY_CONFIG = {
    'inputs': {
        'ac_supply': {'pin': 18, 'id': 1, 'name': 'AC Supply Input'},
        'battery': {'pin': 19, 'id': 2, 'name': 'Battery Input'}
    },
    'outputs': {
        'output_1': {'pin': 20, 'id': 3, 'name': 'Output 1'},
        'output_2': {'pin': 21, 'id': 4, 'name': 'Output 2'}
    }
}

ALL_PINS = [18, 19, 20, 21]
gpio_handle = None

def init_gpio():
    global gpio_handle
    try:
        gpio_handle = lgpio.gpiochip_open(0)
        for pin in ALL_PINS:
            lgpio.gpio_claim_output(gpio_handle, pin, 1)  # Initial state HIGH (relays off)
        print("GPIO initialized successfully")
        print("All relays initialized to OFF state")
    except Exception as e:
        print(f"GPIO initialization failed: {e}")
        raise

def cleanup_gpio():
    global gpio_handle
    if gpio_handle is not None:
        # Turn off all relays for safety
        for pin in ALL_PINS:
            lgpio.gpio_write(gpio_handle, pin, 1)
        lgpio.gpiochip_close(gpio_handle)
        gpio_handle = None
        print("All relays turned OFF and GPIO cleaned up")

def get_relay_info_by_id(relay_id):
    """Get relay information by ID"""
    for category in RELAY_CONFIG.values():
        for relay_name, info in category.items():
            if info['id'] == relay_id:
                return relay_name, info, 'input' if relay_id <= 2 else 'output'
    return None, None, None

def get_relay_states():
    """Get current state of all relays"""
    states = {'inputs': {}, 'outputs': {}}
    
    for category_name, category in RELAY_CONFIG.items():
        for relay_name, info in category.items():
            gpio_value = lgpio.gpio_read(gpio_handle, info['pin'])
            state = 'on' if gpio_value == 0 else 'off'  # Active low
            states[category_name][relay_name] = {
                'id': info['id'],
                'name': info['name'],
                'state': state,
                'pin': info['pin']
            }
    
    return states

@app.route('/api/relay', methods=['POST'])
def control_relay():
    global gpio_handle
    if gpio_handle is None:
        return jsonify({'error': 'GPIO not initialized'}), 500
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400
    
    relay_id = data.get('relay_id')
    state = data.get('state')
    
    if relay_id not in range(1, 5):
        return jsonify({'error': 'Invalid relay ID. Use 1-4'}), 400
    
    if state not in ['on', 'off']:
        return jsonify({'error': 'Invalid state. Use "on" or "off"'}), 400
    
    relay_name, relay_info, relay_type = get_relay_info_by_id(relay_id)
    
    try:
        with gpio_lock:
            # Safety check: Don't allow both input sources to be on simultaneously
            if relay_type == 'input' and state == 'on':
                current_states = get_relay_states()
                if relay_name == 'ac_supply' and current_states['inputs']['battery']['state'] == 'on':
                    return jsonify({
                        'error': 'Safety interlock: Cannot turn on AC supply while battery input is active'
                    }), 400
                elif relay_name == 'battery' and current_states['inputs']['ac_supply']['state'] == 'on':
                    return jsonify({
                        'error': 'Safety interlock: Cannot turn on battery input while AC supply is active'
                    }), 400
            
            pin = relay_info['pin']
            gpio_value = 0 if state == 'on' else 1  # Active low
            lgpio.gpio_write(gpio_handle, pin, gpio_value)
        
        return jsonify({
            'success': True,
            'relay': {
                'id': relay_id,
                'name': relay_info['name'],
                'type': relay_type,
                'state': state
            }
        })
    except Exception as e:
        return jsonify({'error': f'GPIO operation failed: {str(e)}'}), 500

@app.route('/api/input', methods=['POST'])
def control_input():
    """Control input relays with source switching logic"""
    global gpio_handle
    if gpio_handle is None:
        return jsonify({'error': 'GPIO not initialized'}), 500
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400
    
    source = data.get('source')  # 'ac', 'battery', or 'off'
    
    if source not in ['ac', 'battery', 'off']:
        return jsonify({'error': 'Invalid source. Use "ac", "battery", or "off"'}), 400
    
    try:
        with gpio_lock:
            ac_pin = RELAY_CONFIG['inputs']['ac_supply']['pin']
            battery_pin = RELAY_CONFIG['inputs']['battery']['pin']
            
            if source == 'ac':
                lgpio.gpio_write(gpio_handle, battery_pin, 1)  # Turn off battery
                time.sleep(0.1)  # Small delay for safety
                lgpio.gpio_write(gpio_handle, ac_pin, 0)      # Turn on AC
                active_source = 'AC Supply'
            elif source == 'battery':
                lgpio.gpio_write(gpio_handle, ac_pin, 1)      # Turn off AC
                time.sleep(0.1)  # Small delay for safety
                lgpio.gpio_write(gpio_handle, battery_pin, 0) # Turn on battery
                active_source = 'Battery'
            else:  # source == 'off'
                lgpio.gpio_write(gpio_handle, ac_pin, 1)      # Turn off AC
                lgpio.gpio_write(gpio_handle, battery_pin, 1) # Turn off battery
                active_source = 'None'
        
        return jsonify({
            'success': True,
            'active_source': active_source,
            'inputs': {
                'ac_supply': 'on' if source == 'ac' else 'off',
                'battery': 'on' if source == 'battery' else 'off'
            }
        })
    except Exception as e:
        return jsonify({'error': f'Input switching failed: {str(e)}'}), 500

@app.route('/api/output', methods=['POST'])
def control_output():
    """Control output relays"""
    global gpio_handle
    if gpio_handle is None:
        return jsonify({'error': 'GPIO not initialized'}), 500
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400
    
    output = data.get('output')  # 1 or 2
    state = data.get('state')    # 'on' or 'off'
    
    if output not in [1, 2]:
        return jsonify({'error': 'Invalid output. Use 1 or 2'}), 400
    
    if state not in ['on', 'off']:
        return jsonify({'error': 'Invalid state. Use "on" or "off"'}), 400
    
    try:
        with gpio_lock:
            output_key = f'output_{output}'
            pin = RELAY_CONFIG['outputs'][output_key]['pin']
            gpio_value = 0 if state == 'on' else 1  # Active low
            lgpio.gpio_write(gpio_handle, pin, gpio_value)
        
        return jsonify({
            'success': True,
            'output': {
                'number': output,
                'name': RELAY_CONFIG['outputs'][output_key]['name'],
                'state': state
            }
        })
    except Exception as e:
        return jsonify({'error': f'Output control failed: {str(e)}'}), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    global gpio_handle
    if gpio_handle is None:
        return jsonify({'error': 'GPIO not initialized'}), 500
    
    try:
        states = get_relay_states()
        
        # Determine active input source
        active_source = 'none'
        if states['inputs']['ac_supply']['state'] == 'on':
            active_source = 'ac_supply'
        elif states['inputs']['battery']['state'] == 'on':
            active_source = 'battery'
        
        return jsonify({
            'system': 'online',
            'timestamp': int(time.time()),
            'active_input_source': active_source,
            'relays': states
        })
    except Exception as e:
        return jsonify({'error': f'Status read failed: {str(e)}'}), 500

@app.route('/api/emergency-off', methods=['POST'])
def emergency_off():
    """Emergency shutdown - turn off all relays"""
    global gpio_handle
    if gpio_handle is None:
        return jsonify({'error': 'GPIO not initialized'}), 500
    
    try:
        with gpio_lock:
            for pin in ALL_PINS:
                lgpio.gpio_write(gpio_handle, pin, 1)  # Turn off all relays
        
        return jsonify({
            'success': True,
            'message': 'All relays turned OFF (emergency shutdown)',
            'timestamp': int(time.time())
        })
    except Exception as e:
        return jsonify({'error': f'Emergency shutdown failed: {str(e)}'}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'gpio_initialized': gpio_handle is not None,
        'relay_configuration': {
            'inputs': ['AC Supply (Pin 18)', 'Battery (Pin 19)'],
            'outputs': ['Output 1 (Pin 20)', 'Output 2 (Pin 21)']
        },
        'timestamp': int(time.time())
    })

if __name__ == '__main__':
    try:
        init_gpio()
        print("\n=== Relay Controller Started ===")
        print("Input Sources:")
        print("  - AC Supply: Relay 1 (Pin 18)")
        print("  - Battery:   Relay 2 (Pin 19)")
        print("Output Channels:")
        print("  - Output 1:  Relay 3 (Pin 20)")
        print("  - Output 2:  Relay 4 (Pin 21)")
        print("================================\n")
        
        app.run(host='0.0.0.0', port=8080, debug=False)
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Application error: {e}")
    finally:
        cleanup_gpio()
        print("Shutdown complete")