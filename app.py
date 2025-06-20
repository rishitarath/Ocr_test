import os    #interacts with the operating system
import json  #To encode and decode JSON data
import re  #regex   powerful pattern matching in text.
from flask import Flask, render_template, request, jsonify   #main class to create the app 
from google.cloud import vision #Google Cloud Vision API client
from google.oauth2 import service_account  #authentication using a service account JSON key.

app = Flask(__name__) #making your new web app and calling it app

# Initialize Google Cloud Vision client
try:
    credentials_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON") #uses to extract from the environment from Render 
    if not credentials_json:
        raise ValueError("Environment variable GOOGLE_APPLICATION_CREDENTIALS_JSON not set")

    credentials_dict = json.loads(credentials_json) #takes string and returns it as python dict 
    credentials = service_account.Credentials.from_service_account_info(credentials_dict)
    client = vision.ImageAnnotatorClient(credentials=credentials) #gives you a client that you can use to send images for OCR.
    print("✅ Google Cloud Vision client initialized.")
except Exception as e:
    print(f"❌ Error initializing Vision client: {e}")
    client = None

@app.route('/')  #when someone opens your app and then is directed to the index.html  
def index():
    return render_template('index.html')

@app.route('/upload_and_ocr', methods=['POST']) #This is like the hidden back room of your app
def upload_and_ocr(): #When a user sends an image, this function gets called
    if client is None:
        return jsonify({'error': 'Google Cloud Vision not initialized'}), 500 #If the Vision API client isn't initialized, return a 500 error.

    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400  #If the form doesn't contain an image file, return a 400 error.
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400 #If an empty file was submitted, return another 400 error.

    try:
        content = file.read()
        if len(content) == 0: 
            raise Exception("Uploaded file is empty") #Read the contents of the image file. If it's empty, raise an error.
        
        #Send the image to Google Cloud Vision for OCR. Store the returned text annotations
        image = vision.Image(content=content)
        response = client.text_detection(image=image)
        texts = response.text_annotations


        #Set up empty variables to store the values we’ll extract.
        extracted_text = ""
        device_name = ""
        serial_number = ""
        reading = ""

        #If text was found, store the full text (from texts[0].description) and split it line-by-line.
        if texts:
            extracted_text = texts[0].description
            lines = extracted_text.splitlines()

            #Use regex to look for a number (like 5.000 or 44.7) followed by optional units like %, g, etc.
            reading_match = re.search(r'\b(\d+(?:\.\d+)?)(?:\s*)(%|g|mg|kg)?\b', extracted_text, re.IGNORECASE)
            #Save the found number and unit in the reading variable.
            if reading_match:
                reading = f"{reading_match.group(1)} {reading_match.group(2) or ''}".strip()


            # === Device name: Line with METTLER or Analyzer ===
            for line in lines:
                if "METTLER" in line.upper() or "ANALYZER" in line.upper() or "SELEC" in line.upper():
                    device_name = line.strip()
                    break

            # === Serial number: Match patterns like HE73 or A 150 ===
            serial_match = re.search(r'\b([A-Z]{2,3}\s?\d{2,4})\b', extracted_text)
            if serial_match:
                serial_number = serial_match.group(1)

            #Log the values in the server’s terminal for debugging purposes.    
            print("🔎 Extracted Fields:")
            print(f"Device Name: {device_name}")
            print(f"Serial Number: {serial_number}")
            print(f"Reading: {reading}")
        else:
            print("⚠️ No text detected.")

        #If the Vision API returned an error message, raise it as an exception
        if response.error.message:
            raise Exception(response.error.message)

        #Send the results (text + extracted fields) back to the frontend in JSON format
        return jsonify({
            'status': 'success',
            'extracted_text': extracted_text,
            'device_name': device_name,
            'serial_number': serial_number,
            'reading': reading
        })

    except Exception as e:   #If any error occurs during processing, return an error message and log it.
        print(f"🔥 Error during OCR: {e}")
        return jsonify({'error': f'Failed to process image: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)  #If you're running this script directly (not importing it), start the web app
