from flask import Flask, render_template, request, redirect, url_for,jsonify
import requests
import os
from gtts import gTTS
import re  # To strip HTML tags
import speech_recognition as sr
from geopy.distance import geodesic
from fuzzywuzzy import process,fuzz
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_session import Session
app = Flask(__name__)

# Google Maps API Key (replace with your actual key)
GMAPS_API_KEY = 'AIzaSyDCKAHNisordYQoxRIWv6x7sQjXUWdYr1Y'
app.secret_key = 'mysecretkey123'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)
# List of destinations with only 10 entries
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

@app.route('/chat', methods=['POST'])

def chat():
    user_message = request.json.get("message", "").lower()

    # Use fuzzy matching to find the closest destination
    destination_name = None
    match, score = process.extractOne(user_message, DESTINATIONS.keys(), scorer=fuzz.partial_ratio)
    
    if score > 70:  # Confidence threshold
        destination_name = match

    if destination_name:
        # Retrieve coordinates for the destination
        destination_coords = DESTINATIONS[destination_name]
        session['destination'] = destination_name
        session['destination_coords'] = destination_coords

        if 'origin' not in session:
            session['origin'] = "12.823216,80.042685"  # Default origin

        # Construct Google Maps URL for redirection
        maps_url = f"https://www.google.com/maps/dir/?api=1&origin={session['origin']}&destination={destination_coords['lat']},{destination_coords['lon']}&travelmode=walking"

        return jsonify({
            "response": f"Got it! Navigating to {destination_name}...",
            "redirect_url": maps_url  # Redirect automatically
        })

    return jsonify({
        "response": "I'm sorry, I couldn't understand your request. Try again!"
    })


@app.route('/')
def index():
    return render_template('index.html', destinations=DESTINATIONS)

def strip_html_tags(text):
    """Removes HTML tags from the given text."""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)
def find_nearby_locations(current_coords, radius_km=1):
    """Find destinations within a specified radius (in km)."""
    nearby = []
    for name, coords in DESTINATIONS.items():
        distance = geodesic((current_coords['lat'], current_coords['lon']), (coords['lat'], coords['lon'])).km
        if distance <= radius_km:
            nearby.append({"name": name, "distance": round(distance, 2)})
    return nearby

@app.route('/recommendations', methods=['POST'])
def get_recommendations():
    data = request.json
    user_location = data.get('origin')

    if not user_location:
        return jsonify({"error": "Current location not provided."})

    # Find nearby destinations
    nearby_places = find_nearby_locations(user_location)

    if not nearby_places:
        return jsonify({"response": "No nearby destinations found."})

    recommendations = [
        f"{place['name']} ({place['distance']} km away)"
        for place in nearby_places
    ]
    return jsonify({"response": "Nearby destinations:\n" + "\n".join(recommendations)})

def get_directions_text(origin, destination):
    """Fetches step-by-step directions text from Google Maps Directions API."""
    directions_url = (
        f"https://maps.googleapis.com/maps/api/directions/json"
        f"?origin={origin}&destination={destination}&key={GMAPS_API_KEY}"
    )
    
    response = requests.get(directions_url)
    data = response.json()
    
    if data['status'] != 'OK':
        return None, "Failed to get directions. Please try again."

    steps = []
    for leg in data['routes'][0]['legs']:
        for step in leg['steps']:
            instructions = strip_html_tags(step['html_instructions'])
            distance = step['distance']['text']
            step_text = f"{instructions} ({distance})"
            steps.append(step_text)
    
    return steps, None


@app.route('/voice_input', methods=['POST'])
def voice_input():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        try:
            print("Listening for voice input...")
            audio = recognizer.listen(source)
            user_message = recognizer.recognize_google(audio)
            print(f"Recognized: {user_message}")

            return jsonify({"message": user_message})  # Return text properly
        except sr.UnknownValueError:
            return jsonify({"error": "Could not understand the audio"})
        except sr.RequestError:
            return jsonify({"error": "Could not process audio input"})




@app.route('/directions', methods=['POST', 'GET'])
def directions():
    if request.method == 'POST':
        origin_name = request.form.get("origin")  
        destination_name = request.form.get("destination")

        # Store names in session
        session['origin'] = origin_name
        session['destination'] = destination_name

    # Fetch stored names
    origin_name = session.get('origin', None)
    destination_name = session.get('destination', None)

    print(f"Selected Origin: {origin_name}")
    print(f"Selected Destination: {destination_name}")

    # Convert names to coordinates
    origin_coords = DESTINATIONS.get(origin_name)
    destination_coords = DESTINATIONS.get(destination_name)

    if not origin_coords or not destination_coords:
        return "Error: Destination or Origin not found in predefined locations."

    origin = f"{origin_coords['lat']},{origin_coords['lon']}"
    destination = f"{destination_coords['lat']},{destination_coords['lon']}"

    print(f"Resolved Origin Coordinates: {origin}")
    print(f"Resolved Destination Coordinates: {destination}")

    # Construct Google Maps API URL
    directions_url = (
        f"https://maps.googleapis.com/maps/api/directions/json"
        f"?origin={origin}&destination={destination}&key={GMAPS_API_KEY}&mode=walking"
    )

    response = requests.get(directions_url)
    data = response.json()

    print("Google Maps API Response:", data)  # Debugging

    if data['status'] != 'OK':
        return f"Failed to retrieve directions. Error: {data.get('error_message', 'Unknown error')}"

    steps = [
        re.sub('<[^<]+?>', '', step['html_instructions'])
        for leg in data['routes'][0]['legs']
        for step in leg['steps']
    ]

    return render_template(
        'directions.html',
        embed_url=f"https://www.google.com/maps/embed/v1/directions?key={GMAPS_API_KEY}&origin={origin}&destination={destination}&mode=walking",
        maps_url=f"https://www.google.com/maps/dir/?api=1&origin={origin}&destination={destination}&travelmode=walking",
        steps=steps
    )



if __name__ == '__main__':
    app.run(debug=True)
