from flask import Flask, render_template
import RPi.GPIO as GPIO

app = Flask(__name__)

# Set up GPIO pins
RELAY_PINS = {"solar": 17, "battery": 27, "grid": 22}
GPIO.setmode(GPIO.BCM)
for pin in RELAY_PINS.values():
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)  # All off initially

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/switch/<source>')
def switch_source(source):
    if source in RELAY_PINS:
        for s, pin in RELAY_PINS.items():
            GPIO.output(pin, GPIO.HIGH if s == source else GPIO.LOW)
    return render_template('index.html', active=source)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
