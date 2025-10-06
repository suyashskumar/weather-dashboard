from flask import Flask, request, jsonify, render_template
import requests, os

app = Flask(__name__, template_folder='templates')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/weather')
def get_weather():
    city = request.args.get('city', 'London')
    api_key = os.environ.get('OPENWEATHER_API_KEY')
    if not api_key:
        return jsonify({"error": "OPENWEATHER_API_KEY not set on server"}), 500

    url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&units=metric&appid={api_key}'
    resp = requests.get(url, timeout=10)
    if resp.status_code != 200:
        return jsonify({"error": "failed to fetch from OpenWeatherMap", "details": resp.json()}), resp.status_code
    return jsonify(resp.json())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
