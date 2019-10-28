import json
import greengrasssdk
from time import sleep
from pyModbusTCP.client import ModbusClient

client = greengrasssdk.client('iot-data')
c = ModbusClient(host="192.168.69.11", auto_open=True, auto_close=True)


def lambda_handler(event, context):

    print("Incoming event: {}".format(event))
    action = event.get("action")
    light_id = event.get("light_id")
    correlation_token = event.get("correlation_token")
    client_id = event.get("client_id")
    request_value = event.get("value")

    l = int(light_id)

    current_light_brightness = c.read_holding_registers(26, 16)[l - 1]

    if l < 0 or l > 16:
        print("ERROR: Light Out of range")
        return False

    if action == "ReportState":
        # Get on/off and get brightness
        bin_val = c.read_holding_registers(50, 1)[0]
        bin_str = (bin(bin_val)[2:].zfill(16))[::-1]
        setpoint_bin = bin_str[l-1]
        setpoint_bin = "OFF" if (setpoint_bin == "0") else "ON"

        if l < 16:
            resp = {"brightness": current_light_brightness, "powerState": setpoint_bin}
        else:
            resp = {"powerState": setpoint_bin}

        send_response("lighting/response", action, light_id, resp, client_id, correlation_token)
        return True

    elif action == "PowerController":
        if request_value == "TurnOn":
            # Get current brightness for the light_id
            if l < 16:
                setpoint_value = current_light_brightness
            else:
                setpoint_value = 1
        elif request_value == "TurnOff":
            setpoint_value = 0
        else:
            print("ERROR: Unknown PowerControl request")
            return False

    elif action == "BrightnessController.Adjust":
        # Add the delta
        setpoint_value = current_light_brightness + int(request_value)

        if setpoint_value < 0 or setpoint_value > 100:
            print("ERROR: Request value out of range")
            return False

    elif action == "BrightnessController.Set":

        current_light_brightness = c.read_holding_registers(26, 16)
        current_light_brightness = int(current_light_brightness[l - 1])

        if request_value < 0 or request_value > 100:
            print("ERROR: Request value out of range")
            return False

        setpoint_value = request_value
    else:
        print("ERROR: Unknown Action")
        return False

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
        send_response("lighting/response", action, light_id, resp, client_id, correlation_token)
    else:
        print("a or b TCP Modbus failed")


def send_response(topic, action, light_id, value, client_id, correlation_token):
    body = {
        "action": action,
        "light_id": light_id,
        "value": value,
        "client_id": client_id,
        "correlation_token": correlation_token
    }

    print("Sending response for {}".format(action))
    client.publish(topic=topic, payload=json.dumps(body))
