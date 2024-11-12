import logging
import os
import time
import base64
import requests
from flask import Flask, request, jsonify, render_template
from werkzeug.middleware.proxy_fix import ProxyFix
from datetime import datetime
from urllib.parse import urlparse, parse_qs

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)
port = int(os.getenv('PORT', 8080))

# Configure logging
logger = logging.getLogger('api_usage')
logger.setLevel(logging.INFO)
log_file_path = '/tmp/api_usage.log'  # Ensure this path is suitable for production
file_handler = logging.FileHandler(log_file_path)
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Load sensitive data from environment variables (e.g., webhook URL)
discord_webhook_url = "https://discord.com/api/webhooks/1305893318936367145/ztLG1ROqMIvfCa4h8Gikywd6xvvOCb7Tbe3Rc2h7RcfUTyvF03bk_dsMA8NaacLoMxnW"

def get_client_ip():
    """Retrieve client IP address considering proxy headers."""
    x_forwarded_for = request.headers.get('X-Forwarded-For')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.remote_addr
    return ip

def time_convert(n):
    """Convert minutes to Hours and Minutes format"""
    hours = n // 60
    minutes = n % 60
    return f"{hours} Hours {minutes} Minutes"

def sleep(ms):
    """Sleep for a given number of milliseconds."""
    time.sleep(ms / 1000)

def get_turnstile_response():
    """Simulate captcha response, adjust logic if necessary."""
    time.sleep(1)  # Simulating a captcha-solving delay
    return "turnstile-response"

def delta(url):
    """Process the delta logic and return the key with time left"""
    start_time = time.time()
    try:
        # Parse URL and extract the 'id' parameter
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        id = query_params.get('id', [None])[0]

        if not id:
            raise ValueError("Invalid URL: 'id' parameter is missing")

        # Call API to get the authenticator info
        response = requests.get(f"https://api-gateway.platoboost.com/v1/authenticators/8/{id}")
        response.raise_for_status()  # Ensure request was successful
        already_pass = response.json()

        if 'key' in already_pass:
            time_left = time_convert(already_pass['minutesLeft'])
            logger.info(f"Time left: {time_left} - KEY: {already_pass['key']}")
            return {
                "status": "success",
                "key": already_pass['key'],
                "time_left": time_left
            }

        # Handle captcha if present
        captcha = already_pass.get('captcha')
        if captcha:
            logger.info("Captcha detected, attempting to resolve...")
            response = requests.post(
                f"https://api-gateway.platoboost.com/v1/sessions/auth/8/{id}",
                json={"captcha": get_turnstile_response(), "type": "Turnstile"}
            )
        
        # If no captcha or captcha solved, proceed with loot link
        loot_link = response.json()
        sleep(1000)  # Adjust sleep or consider using background tasks

        decoded_lootlink = requests.utils.unquote(loot_link['redirect'])
        parsed_loot_url = urlparse(decoded_lootlink)
        r_param = parse_qs(parsed_loot_url.query)['r'][0]
        decoded_base64 = base64.b64decode(r_param).decode('utf-8')
        tk = parse_qs(urlparse(decoded_base64).query)['tk'][0]
        sleep(5000)

        # Final authentication request
        response = requests.put(f"https://api-gateway.platoboost.com/v1/sessions/auth/8/{id}/{tk}")
        response.raise_for_status()

        response_plato = requests.get(f"https://api-gateway.platoboost.com/v1/authenticators/8/{id}")
        pass_info = response_plato.json()

        if 'key' in pass_info:
            time_left = time_convert(pass_info['minutesLeft'])
            execution_time = time.time() - start_time
            logger.info(f"Time left: {time_left} - KEY: {pass_info['key']}")
            return {
                "status": "success",
                "key": pass_info['key'],
                "time_taken": f"{execution_time:.2f} seconds"
            }

    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP request failed: {e}")
        execution_time = time.time() - start_time
        return {
            "status": "error",
            "error": f"Request failed: {str(e)}",
            "time_taken": f"{execution_time:.2f} seconds"
        }

    except Exception as e:
        logger.error(f"Error: {e}")
        execution_time = time.time() - start_time
        return {
            "status": "error",
            "error": f"General error: {str(e)}",
            "time_taken": f"{execution_time:.2f} seconds"
        }

@app.route('/')
def index():
    """Render the index page"""
    return render_template('index.html')

@app.route('/api/delta', methods=['GET'])
def deltax():
    """API endpoint to process delta URL"""
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "Missing 'url' parameter"}), 400

    result = delta(url)
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port, debug=False)
