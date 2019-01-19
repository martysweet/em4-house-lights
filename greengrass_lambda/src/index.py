import json
import greengrasssdk
from time import sleep
from pyModbusTCP.client import ModbusClient

client = greengrasssdk.client('iot-data')
c = ModbusClient(host="192.168.69.11", auto_open=True, auto_close=True)


def lambda_handler(event, context):

    print(event)

    # event = json.loads(e)
    action = event.get("action")
    light_id = event.get("light_id")
    correlation_token = event.get("correlation_token")
    scope = event.get("scope")
    request_value = event.get("value")

    print(event)

    l = int(light_id)

    current_light_brightness = c.read_holding_registers(26, 16)[l - 1]

    if l < 0 or l > 16:
        print("Out of range")
        exit()

    if action == "ReportState":
        # Get on/off and get brightness
        bin_val = c.read_holding_registers(50, 1)[0]
        bin_str = (bin(bin_val)[2:].zfill(16))[::-1]
        setpoint_bin = bin_str[l-1]
        setpoint_bin = "OFF" if (setpoint_bin == "0") else "ON"

        resp = {"brightness": current_light_brightness, "powerState": setpoint_bin}
        send_response("lighting/response", action, light_id, resp, scope, correlation_token)
        return

    elif action == "PowerController":
        if request_value == "TurnOn":
            # Get current brightness for the light_id
            setpoint_value = current_light_brightness
        elif request_value == "TurnOff":
            setpoint_value = 0
        else:
            print("Unknown PowerControl request")
            exit()
    elif action == "BrightnessController.Adjust":
        # Add the delta
        setpoint_value = current_light_brightness + int(request_value)

        if setpoint_value < 0 or setpoint_value > 100:
            print("Request value out of range")
            exit()

    elif action == "BrightnessController.Set":

        current_light_brightness = c.read_holding_registers(26, 16)
        current_light_brightness = int(current_light_brightness[l - 1])

        if request_value < 0 or request_value > 100:
            print("Request value out of range")
            exit()

        setpoint_value = request_value
    else:
        print("Unknown Action")
        exit()


    # Set the light brightness
    a = c.write_multiple_registers(1, [l, setpoint_value])
    sleep(0.05)


    # Reset the registers
    b = c.write_multiple_registers(1, [0, 0])

    # Send the response
    if a and b:
        if setpoint_value == 0:
            resp = {"brightness": current_light_brightness, "powerState": "OFF"}
        else:
            resp = {"brightness": setpoint_value, "powerState": "ON"}
        send_response("lighting/response", action, light_id, resp, scope, correlation_token)
    else:
        print("a or b TCP Modbus failed")


def send_response(topic, action, light_id, value, scope, correlation_token):
    body = {
        "action": action,
        "light_id": light_id,
        "value": value,
        "scope": scope,
        "correlation_token": correlation_token
    }

    client.publish(topic=topic, payload=json.dumps(body))