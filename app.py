from flask import Flask, request, jsonify, render_template
import requests, os

app = Flask(__name__, template_folder='templates')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/weather')
def get_weather():
    city = request.args.get('city', 'Delhi')
    url = f'https://wttr.in/{city}?format=j1'
    resp = requests.get(url, timeout=10)
    if resp.status_code != 200:
        return jsonify({"error": "Failed to fetch weather"}), resp.status_code
    return jsonify(resp.json())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
