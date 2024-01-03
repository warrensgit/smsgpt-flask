import os
import requests
from flask import Flask, request, jsonify
from openai import OpenAI
import logging
from xml.etree import ElementTree as ET

app = Flask(__name__)

# Set up the OpenAI client
client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

# Configure logging
#logging.basicConfig(filename='delivery_reports.log', level=logging.INFO,
# format='%(asctime)s:%(levelname)s:%(message)s')


@app.route('/')
def index():
  return app.send_static_file('test.html')


@app.route('/process_shortcode', methods=['GET'])
def process_shortcode():
  try:
    # Extracting the parameters from the query string according to the Short Code API
    sender_num = request.args.get('from')
    incoming_message = request.args.get('incoming_message')

    # Basic error handling for missing parameters
    if not all([sender_num, incoming_message]):
      return jsonify({"error": "Some parameters are missing!"}), 400

    # OpenAI API call with the user's message
    response = client.chat.completions.create(
        model="gpt-4",
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
    message = response.choices[0].message['content']
    # Truncate the message to 480 characters if necessary
    message = message[:480]

    print(f"Generated message: {message}")

    # Construct the authorization header for Basic Auth
    username = os.environ.get('OCEP_SMS_USERNAME')
    password = os.environ.get('OCEP_SMS_PASSWORD')
    credentials = f"{username}:{password}"
    encoded_credentials = base64.b64encode(
        credentials.encode('utf-8')).decode('utf-8')
    headers = {'Authorization': f'Basic {encoded_credentials}'}

    # Construct the URL for sending the SMS
    sms_url = 'https://qa-sms.umsg.co.za/xml/send/?'
    payload = {
        'number': sender_num,  # Sending the response back to the sender
        'message': message,
        'ems': '1',  # Enable EMS if the message is over 160 characters
        'userref':
        'unique_reference'  # Replace with an actual unique reference if needed
    }

    # Make the GET request to the SMS gateway to send the SMS
    sms_response = requests.get(sms_url, params=payload, headers=headers)

    # Check if the SMS was successfully enqueued
    if sms_response.status_code == 200:
      return jsonify({
          "success": True,
          "message": "Response sent via SMS"
      }), 200
    else:
      return jsonify({
          "success": False,
          "error": "Failed to send SMS response"
      }), sms_response.status_code

  except Exception as e:
    # Log the error
    print(f"Error: {e}")
    return jsonify({"error": str(e)}), 500


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
    if not all([
        from_number, to_number, success_code, smsc_status, reference_number,
        timestamp
    ]):
      return jsonify({"error": "Missing parameters"}), 400

    # Log the delivery report data
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


@app.route('/process_incoming_message', methods=['POST'])
def process_incoming_message():

  # This endpoint will handle incoming messages sent to your service's number
  message_xml = request.data  # Assume the incoming message comes in XML

  # Parse the XML to extract the message content and sender number
  root = ET.fromstring(message_xml)
  content = root.find('content').text
  sender = root.find('sender').text

  # Interact with OpenAI API with a character limit of 480
  response = openai.ChatCompletion.create(
      model="gpt-4",
      messages=[
          {
              "role":
              "system",
              "content":
              "You are a helpful assistant. Please keep your responses under 480 characters for SMS purposes."
          },
          {
              "role": "user",
              "content": content  # Using the content from the parsed XML
          },
          {
              "role": "assistant",
              "content": ""  # This will be filled by the OpenAI API response
          }
      ],
      max_tokens=200)

  # Format the response for SMS
  response_message = response.choices[0].message['content']

  # Truncate the response to 480 characters if necessary
  response_message = response_message[:480]

  # Construct the authorization header for Basic Auth
  username = os.environ.get('OCEP_SMS_USERNAME')
  password = os.environ.get('OCEP_SMS_PASSWORD')
  credentials = f"{username}:{password}"
  encoded_credentials = base64.b64encode(
      credentials.encode('utf-8')).decode('utf-8')
  headers = {'Authorization': f'Basic {encoded_credentials}'}

  # Construct the URL for sending the SMS
  sms_url = 'https://qa-sms.umsg.co.za/xml/send/?'
  payload = {
      'number':
      sender,  # Assuming you want to send the response back to the sender
      'message': response_message,
      'ems': 1,
      'userref':
      'unique_reference_w'  # Replace with an actual unique reference if needed
  }

  # Make the GET request to the SMS gateway to send the SMS
  response = requests.get(sms_url, params=payload, headers=headers)

  # Check if the SMS was successfully enqueued
  if response.status_code == 200:
    # Parse the XML response from the SMS gateway
    root = ET.fromstring(response.text)
    action = root.find('action').text
    if action == 'enqueued':
      return jsonify({
          "success": True,
          "message": "SMS enqueued for delivery"
      }), 200
    else:
      error = root.find('error').text
      return jsonify({"success": False, "error": error}), 200
  else:
    return jsonify({
        "success": False,
        "error": "Failed to send SMS"
    }), response.status_code


app.run(host='0.0.0.0', port=81)
