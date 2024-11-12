import logging
import os
from flask import Flask, request, jsonify, render_template
from werkzeug.middleware.proxy_fix import ProxyFix
import requests
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import time 
import base64

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)

# Get the port from environment or default to 8080
port = int(os.getenv('PORT', 8080))

# Get the log file path from environment or default to '/tmp/api_usage.log'
log_file_path = os.getenv('LOG_FILE_PATH', '/tmp/api_usage.log')

# Configure logging
logger = logging.getLogger('api_usage')
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(log_file_path)
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Get the Discord webhook URL from environment variable
discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

if not discord_webhook_url:
    raise ValueError("Discord webhook URL is not set in environment variables!")

# Define the main route
@app.route('/')
def index():
    return render_template('index.html')

# Convert minutes to hours and minutes
def time_convert(n):
    hours = n // 60
    minutes = n % 60
    return f"{hours} Hours {minutes} Minutes"

# Sleep function in milliseconds
def sleep(ms):
    time.sleep(ms / 1000)

# Function to simulate turnstile response
def get_turnstile_response():
    time.sleep(1)
    return "turnstile-response"

# Delta processing function
def delta(url):
    start_time = time.time()
    try:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        id = query_params.get('id', [None])[0]

        if not id:
            raise ValueError("Invalid URL: 'id' parameter is missing")

        # Request authenticator info
        response = requests.get(f"https://api-gateway.platoboost.com/v1/authenticators/8/{id}")
        response.raise_for_status()
        already_pass = response.json()

        if 'key' in already_pass:
            time_left = time_convert(already_pass['minutesLeft'])
            print(f"INFO - Time left: {time_left} - KEY: {already_pass['key']}")
            return {
                "status": "success",
                "key": already_pass['key'],
                "time_left": time_left
            }

        # If captcha is detected
        captcha = already_pass.get('captcha')
        if captcha:
            print("INFO - hCaptcha detected! Trying to resolve...")
            response = requests.post(
                f"https://api-gateway.platoboost.com/v1/sessions/auth/8/{id}",
                json={"captcha": get_turnstile_response(), "type": "Turnstile"}
            )
        else:
            # Continue without captcha
            response = requests.post(f"https://api-gateway.platoboost.com/v1/sessions/auth/8/{id}", json={})

        if response.status_code != 200:
            raise Exception("Security Check Detected! Notified on Discord!")

        loot_link = response.json()
        sleep(1000)
        decoded_lootlink = requests.utils.unquote(loot_link['redirect'])
        parsed_loot_url = urlparse(decoded_lootlink)
        r_param = parse_qs(parsed_loot_url.query)['r'][0]
        decoded_base64 = base64.b64decode(r_param).decode('utf-8')
        tk = parse_qs(urlparse(decoded_base64).query)['tk'][0]
        sleep(5000)

        response = requests.put(f"https://api-gateway.platoboost.com/v1/sessions/auth/8/{id}/{tk}")
        response.raise_for_status()

        # Get the final authenticator info
        response_plato = requests.get(f"https://api-gateway.platoboost.com/v1/authenticators/8/{id}")
        pass_info = response_plato.json()

        if 'key' in pass_info:
            time_left = time_convert(pass_info['minutesLeft'])
            execution_time = time.time() - start_time
            print(f"INFO - Time left: {time_left} - KEY: {pass_info['key']}")
            return {
                "status": "success",
                "key": pass_info['key'],
                "time_taken": f"{execution_time:.2f} seconds"
            }

    except Exception as error:
        execution_time = time.time() - start_time
        print(f"ERROR - Error: {error}")
        return {
            "status": "error",
            "error": "hCaptcha = no bypass",
            "time_taken": f"{execution_time:.2f} seconds"
        }

# API endpoint for delta
@app.route('/api/delta', methods=['GET'])
def deltax():
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "Missing 'url' parameter"}), 400

    result = delta(url)
    return jsonify(result)

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False  # Ensure debug=False in production environment
    )
