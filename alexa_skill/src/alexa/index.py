from uuid import uuid4
import datetime
import boto3
import requests
import os
import json
import time
import urllib.request
from jose import jwk, jwt
from jose.utils import base64url_decode

client = boto3.client('iot-data')
ddb_client = boto3.client('dynamodb')

btn = 50

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
        'bearer': {  # TODO: client_id might be better
            'S': 'LWA_AUTH'
        }
    }
)

LWA_id = r['Item']['id']['S']
LWA_secret = r['Item']['secret']['S']

r = ddb_client.get_item(
    TableName=os.environ['TOKEN_TABLE'],
    Key={
        'bearer': {  # TODO: client_id might be better
            'S': 'COGNITO_POOL'
        }
    }
)

keys_url = 'https://cognito-idp.{}.amazonaws.com/{}/.well-known/jwks.json'.format(r['Item']['region']['S'],
                                                                                  r['Item']['id']['S'])
# instead of re-downloading the public keys every time
# we download them only on cold start
# https://aws.amazon.com/blogs/compute/container-reuse-in-lambda/
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
    devices = []

    for l in LIGHTS:
        d = dict(DEVICE_TEMPLATE)
        d['endpointId'] = str(l[0])
        d['friendlyName'] = str(l[1])
        devices.append(d)

    return devices


def generate_deferred_response(correlationToken):
    return {
        "event": {
            "header": {
                "namespace": "Alexa",
                "name": "DeferredResponse",
                "messageId": str(uuid4()),
                "correlationToken": correlationToken,
                "payloadVersion": "3"
            },
            "payload": {
                "estimatedDeferralInSeconds": 2
            }
        }
    }


def lambda_handler(event, context):
    global btn
    print(event)

    scope = event.get("directive", {}).get("endpoint", {}).get("scope", {})
    namespace = event.get("directive", {}).get("header", {}).get("namespace")
    name = event.get("directive", {}).get("header", {}).get("name")
    correlationToken = event.get("directive", {}).get("header", {}).get("correlationToken")
    endpointId = event.get("directive", {}).get("endpoint", {}).get("endpointId")

    if namespace == "Alexa.Authorization" and name == "AcceptGrant":
        print("Accepting Authorization Request")

        # https://developer.amazon.com/docs/smarthome/authenticate-a-customer-permissions.html#steps-for-asynchronous-message-authentication

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
        r = requests.post('https://api.amazon.com/auth/o2/token', data=body, headers=headers)

        print(r.text)
        j = r.json()

        ddb_client.put_item(
            TableName=os.environ['TOKEN_TABLE'],
            Item={
                'bearer': {
                    'S': event.get("directive").get("payload").get("grantee").get("token")
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

        #
        # bearer str
        # access_token str
        # access_expiry unix
        # refresh_token str
        #

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
    authed, client_id = simple_jwt_validation(scope['token'])
    if authed is False:
        print("Invalid incoming token")
        exit()

    if namespace == "Alexa.Discovery":
        response = {
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
        return response
    elif namespace == "Alexa" and name == "ReportState":
        # Send the message
        send_iot_message("lighting/request", "ReportState", endpointId, None, client_id, correlationToken)

        # Returned async response
        return generate_deferred_response(correlationToken)
    elif namespace == "Alexa.PowerController":

        # Send the request via IOT
        send_iot_message("lighting/request", "PowerController", endpointId, name, client_id, correlationToken)

        # Returned async response
        return generate_deferred_response(correlationToken)
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
            return

        # Send the message
        send_iot_message("lighting/request", action, endpointId, val, client_id, correlationToken)

        # Returned async response
        return generate_deferred_response(correlationToken)


def send_iot_message(topic, action, light_id, value, scope, correlation_token):
    body = {
        "action": action,
        "light_id": light_id,
        "value": value,
        "scope": scope,
        "correlation_token": correlation_token
    }

    client.publish(topic=topic, payload=json.dumps(body))
