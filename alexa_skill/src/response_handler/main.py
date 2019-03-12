import requests
import datetime
import boto3
import os
import time
from uuid import uuid4

ddb_client = boto3.client('dynamodb')

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


def lambda_handler(event, context):
    """ Handle the incoming response event from the IOT. """
    print("Incoming event: {}".format(event))

    # Parse the event
    action = event.get("action")
    light_id = event.get("light_id")
    light_value = event.get("value")
    correlation_token = event.get("correlation_token")
    client_id = event.get("client_id")

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

    valid_actions = ['PowerController', 'ReportState', 'BrightnessController.Set', 'BrightnessController.Adjust']
    if action in valid_actions:
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
        print("Unknown action. Event: {}".format(event))
        return False

    # Get valid access_token for the client
    response_access_token = get_access_token(client_id)

    body['event']['endpoint']['scope'] = {
        "type": "BearerToken",
        "token": response_access_token
    }

    # Compose response
    headers = {'Content-type': 'application/json', "Authorization": "Bearer " + response_access_token}
    alexa_event_post = requests.post('https://api.eu.amazonalexa.com/v3/events', json=body, headers=headers)

    if alexa_event_post.status_code != 202:
        print("Event update failed. Request: {} Response: {} {}".format(body,
                                                                        alexa_event_post.status_code,
                                                                        alexa_event_post.text))
        raise Exception("Event update failed")

    return True


def get_access_token(client_id):
    """ Gets an access token for the client to report back to the Alexa Service"""
    user_token = ddb_client.get_item(
        TableName=os.environ['TOKEN_TABLE'],
        Key={
            'client_id': {
                'S': client_id
            }
        }
    )

    if not user_token['Item']:
        print("Could not find record for {}".format(client_id))
        raise Exception()

    if user_token['Item'] and int(user_token['Item']['access_expiry']["N"]) > int(time.time() - 3):
        return user_token['Item']['access_token']["S"]
    else:
        # Get new token
        body = {
            "grant_type": "refresh_token",
            "refresh_token": user_token['Item']['refresh_token']["S"],
            "client_id": LWA_id,
            "client_secret": LWA_secret
        }

        headers = {'Content-type': 'application/x-www-form-urlencoded;charset=UTF-8'}
        user_token = requests.post('https://api.amazon.com/auth/o2/token', data=body, headers=headers)
        j = user_token.json()

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

        return j.get("access_token")
