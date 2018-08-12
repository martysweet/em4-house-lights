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
- 4x 10A MCB

## Wiring Schematic
![Wiring Schematic](https://github.com/martysweet/em4-house-lights/blob/master/Dimmable%20Lighting%20-%20Wiring%20Schematic.png?raw=true)
