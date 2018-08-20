# em4-house-lights
Dimmer House Lighting using an EM4 controller and Modbus Dimmers

You can downlad Crouzet Soft for free from http://automation.crouzet.com/products/software/em4-soft/.

## House Light Controller Features
- 16 dimmable inputs and outputs using retractive "push" switches to control dimming
- 3 switched relay outputs
- Fire input (which turns on all dimmable lights)
- Sunset detection (dims all lights at sunset)
- Solar pulse counter
- Water pulse counter

### Future Work
- RPi Integration, built ontop of the AWS Greengrass platform

## Hardware
- 4x Modbus Dimmers https://www.aliexpress.com/item/4-way-thyristor-dimming-module-RS485-Modbus/32827560823.html
- 1x EM4 Ethernet http://automation.crouzet.com/products/em4-nano-plc/on-site-management/ethernet/
- 1x EM4 Master Modbus Adapter http://automation.crouzet.com/products/accessories/em4-accessories/
- 1x EM4 Digital Expansion http://automation.crouzet.com/products/expansion-modules/em4-expansions/digital-expansions/
- 1x RPi
- 1x USB Network Adapter
- 1x 5v PSU
- 1x 24v PSU
- 4x 10A MCB (One per dimmer unit)
- 1x 3A MCB (5v + 24v PSU)

## Wiring Schematic
![Wiring Schematic](https://github.com/martysweet/em4-house-lights/blob/master/dimmer-schematic.png?raw=true)

# Setup

## Assigning a Modbus address to HD4504 Dimmers

### Crash course on Modbus
First, if you are new to Modbus, lets pop over a couple of basics. A request and response is made up from multiple bytes, as you can see in the examples below, these are all represented in Hexadecimal.

- 60 - Slave ID, from 1 (01) - 255 (FF)
- 03 - Modbus mode, for most cases, 03 reads registers, 06 is used to write
- 00 - Register to address
- 00 - Register to address
- 00 - Value to write / Number of registers to read
- 01 - Value to write / Number of registers to read
- 8C - Checksum
- 7B - Checksum

Holding registers (mode 03 and 06) start a decimal 40001, so the first holding register is 40001 - 40001 = 0x0000, which can be seen in the above example. Often, documentation will give the hexadecimal value of the register, in which case it goes into the request directly. If your Modbus client requires a decimal register and you wanted to read register 0x0200, you would have to convert 0x0200 to decimal, which gives 512, add this to 40001, to give 40513. When you client subtracts the offset, it results in 512, which is then converted back into 0x0200 for the request.

### Setup
Setup your Modbus RS-485 connection to the dimmer and connect using the following settings
- Default Slave ID: 96
- Default Baud: 9600
- Data bit: 8
- Stop bit: 1
- Parity: Even


Test connection by reading the first register, if circuit 1 and 2 are off, we expect to see bytes of `0000`.
- Request: 60 03 00 00 00 01 8C 7B 
- Response: 60 03 02 00 00 05 8C 

Next, read the device ID from the holding registers, which is located in register 0x200.
- Request: 60 03 02 00 00 01 8D C3 
- Response: 60 03 02 60 03 6D 8D 

The response here is `6003`, showing a device ID of 0x60 (96) and a connect register value of 0x03, which is default.
Next, we are going to change this device ID to decimal 2, thus we need to write 0x0203 back into the register.
- Request: 60 06 02 00 02 03 C1 62 
- Response: Probably will fail

Now lets check the device is responding to the new slave ID.
- Request: 02 06 02 00 00 01 49 81 
- Response: 02 06 02 00 00 01 49 81 

Great! Now we can have multiple dimmers on the same Modbus network!
