from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_session import Session
import requests
import os
from gtts import gTTS
import re
import speech_recognition as sr
from geopy.distance import geodesic
from fuzzywuzzy import process, fuzz
from dotenv import load_dotenv
load_dotenv()


app = Flask(__name__)
app.secret_key = 'mysecretkey123'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

GMAPS_API_KEY = os.getenv('GMAPS_API_KEY')

DESTINATIONS = {
    "University Building (UB)": {"lat": 12.823216, "lon": 80.042685},
    "NRI Hostel": {"lat": 12.823929, "lon": 80.042698},
    "JAVA canteen": {"lat": 12.823538835167044, "lon": 80.04428605656615}, 
    "BEL LAB": {"lat": 12.823258, "lon": 80.043577},
    "Car Parking - 1": {"lat": 12.824232, "lon": 80.043160},                                                  
    "Architecture Block": {"lat": 12.824164, "lon": 80.044258},
    "Bio Tech Block": {"lat": 12.824723, "lon": 80.044285},
    "Tech Park": {"lat": 12.824555, "lon": 80.045098},
    "T.P. Ganesan Auditorium": {"lat": 12.824404921311643, "lon": 80.04660848099508},           
    "SRM Hospital": {"lat": 12.823267575048508, "lon": 80.0477305194682}
}

@app.route('/')
def index():
    return render_template('index.html', destinations=DESTINATIONS)

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get("message", "").lower()
    match, score = process.extractOne(user_message, DESTINATIONS.keys(), scorer=fuzz.partial_ratio)
    
    if score > 70:
        destination_name = match
        destination_coords = DESTINATIONS[destination_name]
        session['destination'] = destination_name
        session['destination_coords'] = destination_coords

        if 'origin' not in session:
            session['origin'] = "12.823216,80.042685"

        # Redirect to internal directions page instead of Google Maps
        return jsonify({
            "response": f"Got it! Navigating to {destination_name}...",
            "redirect_url": url_for('directions')  # This line changed
        })

    return jsonify({
        "response": "I'm sorry, I couldn't understand your request. Try again!"
    })


def strip_html_tags(text):
    return re.sub(re.compile('<.*?>'), '', text)

def find_nearby_locations(current_coords, radius_km=1):
    nearby = []
    for name, coords in DESTINATIONS.items():
        distance = geodesic((current_coords['lat'], current_coords['lon']), (coords['lat'], coords['lon'])).km
        if distance <= radius_km:
            nearby.append({"name": name, "distance": round(distance, 2)})
    return nearby

@app.route('/recommendations', methods=['POST'])
def get_recommendations():
    data = request.json
    origin = data.get('origin')
    if not origin:
        return jsonify({"error": "Current location not provided."})
    
    try:
        lat, lon = map(float, origin.split(','))
        nearby_places = find_nearby_locations({"lat": lat, "lon": lon})
        if not nearby_places:
            return jsonify({"response": "No nearby destinations found."})
        recommendations = [f"{place['name']} ({place['distance']} km away)" for place in nearby_places]
        return jsonify({"response": "Nearby destinations:\n" + "\n".join(recommendations)})
    except:
        return jsonify({"error": "Invalid origin format."})

def get_directions_text(origin, destination):
    directions_url = f"https://maps.googleapis.com/maps/api/directions/json?origin={origin}&destination={destination}&key={GMAPS_API_KEY}"
    response = requests.get(directions_url)
    data = response.json()
    if data['status'] != 'OK':
        return [], "Failed to get directions. Please try again."

    steps = []
    for leg in data['routes'][0]['legs']:
        for step in leg['steps']:
            instructions = strip_html_tags(step['html_instructions'])
            distance = step['distance']['text']
            steps.append(f"{instructions} ({distance})")
    return steps, None

@app.route('/directions', methods=['GET'])
def directions():
    origin_name = request.args.get('origin') or session.get('origin')
    destination_name = request.args.get('destination') or session.get('destination')

    if origin_name:
        session['origin'] = origin_name
    if destination_name:
        session['destination'] = destination_name

    origin_coords = DESTINATIONS.get(origin_name)
    destination_coords = DESTINATIONS.get(destination_name)

    if not origin_coords or not destination_coords:
        return "Invalid origin/destination", 400

    embed_url = f"https://www.google.com/maps/embed/v1/directions?key={GMAPS_API_KEY}&origin={origin_coords['lat']},{origin_coords['lon']}&destination={destination_coords['lat']},{destination_coords['lon']}&mode=walking"
    steps, _ = get_directions_text(f"{origin_coords['lat']},{origin_coords['lon']}", f"{destination_coords['lat']},{destination_coords['lon']}")
    
    return render_template('directions.html', embed_url=embed_url, maps_url=f"https://www.google.com/maps/dir/?api=1&origin={origin_coords['lat']},{origin_coords['lon']}&destination={destination_coords['lat']},{destination_coords['lon']}&travelmode=walking", steps=steps)

@app.route('/voice_input', methods=['POST'])
def voice_input():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        try:
            audio = recognizer.listen(source)
            user_message = recognizer.recognize_google(audio)
            return jsonify({"message": user_message})
        except sr.UnknownValueError:
            return jsonify({"error": "Could not understand the audio"})
        except sr.RequestError:
            return jsonify({"error": "Could not process audio input"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6003, debug=True)

    # app.run(host='0.0.0.0', port=6000, debug=True)
