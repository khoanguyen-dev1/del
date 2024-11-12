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
port = int(os.getenv('PORT', 8))
# Configure logging
logger = logging.getLogger('api_usage')
logger.setLevel(logging.INFO)

log_file_path = '/tmp/api_usage.log'
file_handler = logging.FileHandler(log_file_path)
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

def get_client_ip():
    """Retrieve client IP address considering proxy headers."""
    x_forwarded_for = request.headers.get('X-Forwarded-For')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.remote_addr
    return ip
i = 0
platoboost = "https://gateway.platoboost.com/a/8?id="
discord_webhook_url = "https://discord.com/api/webhooks/1305893318936367145/ztLG1ROqMIvfCa4h8Gikywd6xvvOCb7Tbe3Rc2h7RcfUTyvF03bk_dsMA8NaacLoMxnW" # enter your webhook if security check detected
@app.route('/')
def index():
    return render_template('index.html')

def time_convert(n):
    hours = n // 60
    minutes = n % 60
    return f"{hours} Hours {minutes} Minutes"



def sleep(ms):
    time.sleep(ms / 1000)

def get_turnstile_response():
    time.sleep(1)
    return "turnstile-response"

def delta(url):
    start_time = time.time()
    try:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        id = query_params.get('id', [None])[0]

        if not id:
            raise ValueError("Invalid URL: 'id' parameter is missing")

        response = requests.get(f"https://api-gateway.platoboost.com/v1/authenticators/8/{id}")
        response.raise_for_status()
        already_pass = response.json()

        if 'key' in already_pass:
            time_left = time_convert(already_pass['minutesLeft'])
            print(f"\033[32m INFO \033[0m Time left:  \033[32m{time_left}\033[0m - KEY: \033[32m{already_pass['key']}\033[0m")
            return {
                "status": "success",
                "key": already_pass['key'],
                "time_left": time_left
            }

        captcha = already_pass.get('captcha')

        if captcha:
            print("\033[32m INFO \033[0m hCaptcha detected! Trying to resolve...")
            # If captcha exists, make sure to solve it before continuing
            response = requests.post(
                f"https://api-gateway.platoboost.com/v1/sessions/auth/8/{id}",
                json={
                    "captcha": get_turnstile_response(),
                    "type": "Turnstile"
                }
            )
        else:
            # if no captcha, continue without it
            response = requests.post(
                f"https://api-gateway.platoboost.com/v1/sessions/auth/8/{id}",
                json={}
            )

        if response.status_code != 200:
            security_check_link = f"{platoboost}{id}"
          
            raise Exception("Có link delta có capcha")

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

        response_plato = requests.get(f"https://api-gateway.platoboost.com/v1/authenticators/8/{id}")
        pass_info = response_plato.json()

        if 'key' in pass_info:
            time_left = time_convert(pass_info['minutesLeft'])
            execution_time = time.time() - start_time
            print(f"\033[32m INFO \033[0m Time left:  \033[32m{time_left}\033[0m - KEY: \033[32m{pass_info['key']}\033[0m")
            return {
                "status": "success",
                "key": pass_info['key'],
                
                "time taken": f"{execution_time:.2f} seconds"
            }

    except Exception as error:
        print(f"\033[31m ERROR \033[0m Error: {error}")
        execution_time = time.time() - start_time
        return {
            "status": "error",
            "error": "hcapcha = no bypass",
            "time taken": f"{execution_time:.2f} seconds"
        }

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
