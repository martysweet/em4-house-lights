import json
import requests
import datetime
import boto3
import os
import time
from uuid import uuid4

ddb_client = boto3.client('dynamodb')
# Takes IOT message and generates an async response to the Alexa event gateway

# Get LWA secrets
r = ddb_client.get_item(
    TableName=os.environ['TOKEN_TABLE'],
    Key={
        'bearer': {
            'S': 'LWA_AUTH'
        }
    }
)

LWA_id = r['Item']['id']['S']
LWA_secret = r['Item']['secret']['S']


def lambda_handler(event, context):
    print(event)

    action = event.get("action")
    light_id = event.get("light_id")
    light_value = event.get("value")
    correlation_token = event.get("correlation_token")
    client_id = event.get("scope")

    if action == "ReportState":
        event_name = "StateReport"
    else:
        event_name = "Response"

    body = {
        "event": {
            "header": {
                "namespace": "Alexa",
                "name": event_name,
                "payloadVersion": "3",
                "messageId": str(uuid4()),
                "correlationToken": correlation_token
            },
            "endpoint": {
                # "scope": scope, # IS SET LATER
                "endpointId": str(light_id)
            },
            "payload": {}
        }
    }

    if action == "PowerController" or action == "ReportState" or action == "BrightnessController.Set" or action == "BrightnessController.Adjust":
        power_state = light_value.get("powerState")
        brightness = light_value.get("brightness")
        body['context'] = {
            "properties": [
                {
                    "namespace": "Alexa.PowerController",
                    "name": "powerState",
                    "value": str(power_state),
                    "timeOfSample": datetime.datetime.now().isoformat() + "Z",
                    "uncertaintyInMilliseconds": 1000
                },
                {
                    "namespace": "Alexa.BrightnessController",
                    "name": "brightness",
                    "value": str(brightness),
                    "timeOfSample": datetime.datetime.now().isoformat() + "Z",
                    "uncertaintyInMilliseconds": 1000
                }
            ]
        }

    else:
        print("Unknown action")
        exit()

    # Check if we have a valid access_token
    r = ddb_client.get_item(
        TableName=os.environ['TOKEN_TABLE'],
        Key={
            'bearer': {
                'S': client_id
            }
        }
    )

    print(r)

    if int(r['Item']['access_expiry']["N"]) < int(time.time() - 3):
        # Get new token
        body = {
            "grant_type": "refresh_token",
            "refresh_token": r['Item']['refresh_token']["S"],
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

        access_token = j.get("access_token")
    else:
        access_token = r['Item']['access_token']["S"]

    body['event']['endpoint']['scope'] = {
        "type": "BearerToken",
        "token": access_token
    }

    print(body)

    # Compose response
    headers = {'Content-type': 'application/json', "Authorization": "Bearer " + access_token}
    r = requests.post('https://api.eu.amazonalexa.com/v3/events', json=body, headers=headers)

    print("Response:" + str(r))
    print(r.text)

    req = r.request

    print('{}\n{}\n{}\n\n{}'.format(
        '-----------START-----------',
        req.method + ' ' + req.url,
        '\n'.join('{}: {}'.format(k, v) for k, v in req.headers.items()),
        req.body,
    ))

    pass
