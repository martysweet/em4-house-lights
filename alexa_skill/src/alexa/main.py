from uuid import uuid4
import boto3
import requests
import os
import json
import time
import urllib.request
from jose import jwk, jwt
from jose.utils import base64url_decode

# Setup the AWS clients
client = boto3.client('iot-data')
ddb_client = boto3.client('dynamodb')

# Define the lights available
LIGHTS = [
    [2, "Lounge Rear Light"],
    [3, "Lounge Lobby Light"],
    [4, "Hallway Light"],
    [5, "Kitchen Ceiling Light"],
    [6, "Kitchen Island Light"],
    [7, "Kitchen Table Light"],
    [9, "Landing Light"],
    [10, "Bathroom Light"],
    [11, "Office Light"],
    [12, "Spare Room Light"],
    [13, "Bedroom Light"],
    [14, "Lounge Front Light"],
    [15, "Side Light"]
]

DEVICE_TEMPLATE = {
    # "endpointId": "light-OVERRIDE",
    # "friendlyName": "Living Room Light",
    "description": "Smart Light by Marty",
    "manufacturerName": "Marty",
    "displayCategories": [
        "LIGHT"
    ],
    "cookie": {},
    "capabilities": [
        {
            "type": "AlexaInterface",
            "interface": "Alexa.PowerController",
            "version": "3",
            "properties": {
                "supported": [{
                    "name": "powerState"
                }],
                "proactivelyReported": False,
                "retrievable": True
            }
        },
        {
            "type": "AlexaInterface",
            "interface": "Alexa",
            "version": "3"
        },
        {
            "type": "AlexaInterface",
            "interface": "Alexa.BrightnessController",
            "version": "3",
            "properties": {
                "supported": [{
                    "name": "brightness"
                }],
                "proactivelyReported": False,
                "retrievable": True
            }
        },
    ]
}

# Get LWA secrets
r = ddb_client.get_item(
    TableName=os.environ['TOKEN_TABLE'],
    Key={
        'client_id': {
            'S': 'LWA_AUTH'
        }
    }
)

if not r['Item']:
    raise Exception("LWA_AUTH not present in database.")

LWA_id = r['Item']['id']['S']
LWA_secret = r['Item']['secret']['S']

# Get the cognito pool id
r = ddb_client.get_item(
    TableName=os.environ['TOKEN_TABLE'],
    Key={
        'client_id': {
            'S': 'COGNITO_POOL'
        }
    }
)

keys_url = 'https://cognito-idp.{}.amazonaws.com/{}/.well-known/jwks.json'.format(r['Item']['region']['S'],
                                                                                  r['Item']['id']['S'])
# Download the keys for Cognito once
with urllib.request.urlopen(keys_url) as url:
    response = url.read()
keys = json.loads(response.decode('utf-8'))['keys']


def simple_jwt_validation(token):
    # https://github.com/awslabs/aws-support-tools/blob/master/Cognito/decode-verify-jwt/decode-verify-jwt.py
    # get the kid from the headers prior to verification
    headers = jwt.get_unverified_headers(token)
    kid = headers['kid']
    # search for the kid in the downloaded public keys
    key_index = -1
    for i in range(len(keys)):
        if kid == keys[i]['kid']:
            key_index = i
            break
    if key_index == -1:
        print('Public key not found in jwks.json')
        return False
    # construct the public key
    public_key = jwk.construct(keys[key_index])
    # get the last two sections of the token,
    # message and signature (encoded in base64)
    message, encoded_signature = str(token).rsplit('.', 1)
    # decode the signature
    decoded_signature = base64url_decode(encoded_signature.encode('utf-8'))
    # verify the signature
    if not public_key.verify(message.encode("utf8"), decoded_signature):
        print('Signature verification failed')
        return False
    print('Signature successfully verified')
    claims = jwt.get_unverified_claims(token)
    return True, claims['client_id']
    # TODO: Possibly implement claims


def generate_devices():
    """ Create a list of devices for discovery. """
    devices = []

    for l in LIGHTS:
        d = dict(DEVICE_TEMPLATE)
        d['endpointId'] = str(l[0])
        d['friendlyName'] = str(l[1])
        devices.append(d)

    return devices


def generate_deferred_response(correlation_token):
    """ Generate a deferred response, the response handler will return the value later. """
    return {
        "event": {
            "header": {
                "namespace": "Alexa",
                "name": "DeferredResponse",
                "messageId": str(uuid4()),
                "correlationToken": correlation_token,
                "payloadVersion": "3"
            },
            "payload": {
                "estimatedDeferralInSeconds": 2
            }
        }
    }


def lambda_handler(event, context):

    print(event)

    scope = event.get("directive", {}).get("endpoint", {}).get("scope", None)

    if scope is None:
        scope = event.get("payload", {}).get("scope", None)

    namespace = event.get("directive", {}).get("header", {}).get("namespace")
    name = event.get("directive", {}).get("header", {}).get("name")
    correlation_token = event.get("directive", {}).get("header", {}).get("correlationToken")
    endpoint_id = event.get("directive", {}).get("endpoint", {}).get("endpointId")

    if namespace == "Alexa.Authorization" and name == "AcceptGrant":
        # Handle an authentication setup
        print("Accepting Authorization Request")

        # Store Token, grantee -> token represents the user
        # Use the grant > code
        # Store bearer and refresh token, use access_token to send requests

        # Call auth to get tokens
        body = {
            "grant_type": "authorization_code",
            "code": event.get("directive").get("payload").get("grant").get("code"),
            "client_id": LWA_id,
            "client_secret": LWA_secret
        }

        headers = {'Content-type': 'application/x-www-form-urlencoded;charset=UTF-8'}
        token_request = requests.post('https://api.amazon.com/auth/o2/token', data=body, headers=headers)

        _, client_id = simple_jwt_validation(event.get("directive").get("payload").get("grantee").get("token"))
        j = token_request.json()
        ddb_client.put_item(
            TableName=os.environ['TOKEN_TABLE'],
            Item={
                'client_id': {
                    'S': client_id
                },
                'access_token': {
                    'S': j.get("access_token"),
                },
                'access_expiry': {
                    'N': str(int(time.time()) + int(j.get("expires_in"))),
                },
                'refresh_token': {
                    'S': j.get("refresh_token"),
                }
            }
        )

        # Return the Auth response
        return {
            "event": {
                "header": {
                    "messageId": str(uuid4()),
                    "namespace": "Alexa.Authorization",
                    "name": "AcceptGrant.Response",
                    "payloadVersion": "3"
                },
                "payload": {
                }
            }
        }

    # Authorise the request against our pool
    if scope is None:
        print("Failed to get a valid scope from incoming event, not attempting authentication")
        return False

    authed, client_id = simple_jwt_validation(scope['token'])
    if authed is False:
        print("Invalid incoming token")
        return False

    if namespace == "Alexa.Discovery":
        return {
            "event": {
                "header": {
                    "namespace": "Alexa.Discovery",
                    "name": "Discover.Response",
                    "payloadVersion": "3",
                    "messageId": str(uuid4())
                },
                "payload": {
                    "endpoints": generate_devices()
                }
            }
        }
    elif namespace == "Alexa" and name == "ReportState":
        # Send the message
        send_iot_message("lighting/request", "ReportState", endpoint_id, None, client_id, correlation_token)
        return generate_deferred_response(correlation_token)
    elif namespace == "Alexa.PowerController":
        # Send the request via IOT
        send_iot_message("lighting/request", "PowerController", endpoint_id, name, client_id, correlation_token)
        return generate_deferred_response(correlation_token)
    elif namespace == "Alexa.BrightnessController":
        # Send the request via IOT
        if name == "AdjustBrightness":
            action = "BrightnessController.Adjust"
            val = int(event.get("directive").get("payload").get("brightnessDelta"))
        elif name == "SetBrightness":
            action = "BrightnessController.Set"
            val = int(event.get("directive").get("payload").get("brightness"))
        else:
            print("Unknown Brightness Action")
            return False

        # Send the message
        send_iot_message("lighting/request", action, endpoint_id, val, client_id, correlation_token)

        # Returned async response
        return generate_deferred_response(correlation_token)


def send_iot_message(topic, action, light_id, value, client_id, correlation_token):
    body = {
        "action": action,
        "light_id": light_id,
        "value": value,
        "client_id": client_id,
        "correlation_token": correlation_token
    }

    client.publish(topic=topic, payload=json.dumps(body))
