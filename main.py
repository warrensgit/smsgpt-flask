import os
import requests
from flask import Flask, request, jsonify
from openai import OpenAI
import logging
from xml.etree import ElementTree as ET
import base64
from urllib.parse import quote_plus 

app = Flask(__name__)

# Set up the OpenAI client
client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

# Configure logging to log to a file
logging.basicConfig(filename='incoming_messages.log', level=logging.INFO, format='%(asctime)s:%(levelname)s:%(message)s')

@app.route('/')
def index():
  return app.send_static_file('test.html')


@app.route('/process_shortcode', methods=['GET'])
def process_shortcode():
    try:
        # Extracting the parameters from the query string
        sender_num = request.args.get('from')
        incoming_message = request.args.get('incoming_message')

        # Basic error handling for missing parameters
        if not all([sender_num, incoming_message]):
            return jsonify({"error": "Some parameters are missing!"}), 400

        # OpenAI API call with the user's message
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Please keep your responses under 480 characters for SMS purposes."
                },
                {
                    "role": "user",
                    "content": incoming_message
                }
            ],
            max_tokens=200
        )

        # Extracting the assistant's response
        try:
            assistant_message = response.choices[0].message.content
        except Exception as e:
            print(f"Error extracting message: {e}")
            assistant_message = "Error in processing response."

        # Construct the authorization header for Basic Auth
        username = os.environ.get('OCEP_SMS_USERNAME')
        password = os.environ.get('OCEP_SMS_PASSWORD')
        credentials = f"{username}:{password}"
        encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')

        # Construct the headers for the request
        headers = {
            'Authorization': 'Basic ' + encoded_credentials,
            'Content-Type': 'application/json',
            'User-Agent': 'PostmanRuntime/7.36.0',
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive'
        }

        # Construct the JSON payload for the POST request
        payload = {
            "to": sender_num,
            "message": assistant_message[:480],
            "ems": 0,
            "userref": "unique_reference"
        }

        # REST API endpoint for sending SMS
        rest_api_url = "https://qa-sms.umsg.co.za/send/sms"

        # Make the POST request to the SMS gateway to send the SMS
        sms_response = requests.post(rest_api_url, json=payload, headers=headers)

        # Prepare a response object
        response_data = {
            "openai_response": assistant_message,  # This is the assistant's response
            "sms_gateway_response": sms_response.json() if sms_response.status_code == 200 else "Failed to send SMS"
        }

        # Determine the overall success
        if sms_response.status_code == 200 and response_data["sms_gateway_response"].get("Action") == "enqueued":
            return jsonify({"success": True, "message": "SMS enqueued for delivery", "data": response_data}), 200
        else:
            return jsonify({"success": False, "error": "Failed to send SMS", "data": response_data}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e), "data": {}}), 500


@app.route('/delivery_report', methods=['GET'])
def delivery_report():
  try:
    # Extracting the parameters from the query string
    from_number = request.args.get('FN')
    to_number = request.args.get('TN')
    success_code = request.args.get('SC')
    smsc_status = request.args.get('ST')
    reference_number = request.args.get('RF')
    timestamp = request.args.get('TS')

    # Basic error handling for missing parameters
    #if not all([
    #    from_number, to_number, success_code, smsc_status, reference_number,
    #    timestamp
    #]):
    #  return jsonify({"error": "Missing parameters"}), 400

    #Log the delivery report data
    logging.info(
        f'Delivery report received - From: {from_number}, To: {to_number}, '
        f'Success: {success_code}, SMSC Status: {smsc_status}, '
        f'Reference: {reference_number}, Timestamp: {timestamp}')

    # TODO: Update message status in a database or another storage system if necessary

    # Respond with a success message
    return jsonify({"message": "Delivery report received"}), 200

  except Exception as e:
    # Log the exception
    logging.error(f'Error processing delivery report: {e}')
    # Respond with an error message
    return jsonify({"error": "Error processing delivery report"}), 500


@app.route('/process_incoming_message', methods=['GET'])
def process_incoming_message():
    try:
        # Extracting parameters from the query string
        from_number = request.args.get('FN')
        to_number = request.args.get('TN')
        message_text = request.args.get('MS')
        timestamp = request.args.get('TS')

        # Log the incoming message details
        logging.info(f'Incoming message received - From: {from_number}, To: {to_number}, Message: {message_text}, Timestamp: {timestamp}')
      
        # OpenAI API call with the user's message
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Please keep your responses under 480 characters for SMS purposes."
                },
                {
                    "role": "user",
                    "content": message_text
                }
            ],
            max_tokens=200
        )

        # Extracting the assistant's response
        try:
            assistant_message = response.choices[0].message.content
        except Exception as e:
            print(f"Error extracting message: {e}")
            assistant_message = "Error in processing response."

        # Truncate and URL encode the message
        encoded_message = quote_plus(assistant_message[:480])

        # Construct the authorization header for Basic Auth
        username = os.environ.get('OCEP_SMS_USERNAME')
        password = os.environ.get('OCEP_SMS_PASSWORD')
        credentials = f"{username}:{password}"
        encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        
        # Construct the headers for the request
        headers = {
            'Authorization': 'Basic ' + encoded_credentials,
            'Content-Type': 'application/json',
            'User-Agent': 'PostmanRuntime/7.36.0',
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive'
        }

        # Log the Authorization header for inspection
        print(f"Authorization Header: {headers['Authorization']}")
        
        # Construct the JSON payload for the POST request
        payload = {
            "to": from_number,
            "message": assistant_message[:480],  # Truncate the message to 480 c's,
            "ems": 1,  # Assuming EMS is enabled; adjust as necessary
            "userref": "unique_reference_w"  # Replace with an actual unique reference if needed
        }

        # REST API endpoint for sending SMS
        rest_api_url = "https://qa-sms.umsg.co.za/send/sms"

        # Make the POST request to the SMS gateway to send the SMS
        sms_response = requests.post(rest_api_url, json=payload, headers=headers)
        print(f"SMS Gateway Response: {sms_response.status_code}, {sms_response.text}")

        # Check if the SMS was successfully enqueued
        if sms_response.status_code == 200:
            response_data = sms_response.json()
            if response_data.get("Action") == "enqueued":
                return jsonify({"success": True, "message": "SMS enqueued for delivery"}), 200
            else:
                return jsonify({"success": False, "error": response_data.get("Error", "Unknown error")}), 200
        else:
            return jsonify({"success": False, "error": "Failed to send SMS"}), sms_response.status_code

    except Exception as e:
        print(f"Error in process_incoming_message: {e}")
        return jsonify({"error": str(e)}), 500



app.run(host='0.0.0.0', port=81)
