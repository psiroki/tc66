#!/usr/bin/env python3
from time import sleep
from Crypto.Cipher import AES
import itertools
import serial
import sys
import argparse
from datetime import datetime

tsv = False
hex = False
diff = False
start = datetime.now()

def decrypt(data):
    AESKeySource = [
        0x58, 0x21, -0x6, 0x56, 0x1, -0x4e, -0x10, 0x26, -0x79, -0x1, 0x12,
        0x4, 0x62, 0x2a, 0x4f, -0x50, -0x7a, -0xc, 0x2, 0x60, -0x7f, 0x6f,
        -0x66, 0xb, -0x59, -0xf, 0x6, 0x61, -0x66, -0x48, 0x72, -0x78
    ]

    AESKey = []
    for b in AESKeySource:
        AESKey.append(b & 0xFF)  # Handle negative numbers
    AESKey = bytes(AESKey)
    cipher = AES.new(bytes(AESKey), AES.MODE_ECB)
    rawData = cipher.decrypt(bytes(data))
    return rawData


def printHex(array):
    output = 'Hex: '
    for b in array:
        output = output + '%2.2X' % b
    print(output)

lastData = []
def handleDataPacket(data):
    # Thing to note is that all data is send as int32_t's packed end to end
    # I propose that their firmware is using a C packed struct and they are dumping it out directly
    # first 4 are the chars "pac1"
    # followed by the model "TC66"
    # followed by 4 digits for the firmware version as a string
    # The data between 12-47 inclusive is unknown at the moment
    # Data that is expected but not found : 
    # -> Runtime counter
    # -> Uptime of this run
    # -> Serial Number
    # -> Detected protocol
    # -> Means of changing settings
    if hex:
        if diff:
            global lastData
            print(' '.join((f'{x:02x}' if n >= len(lastData) or lastData[n] != x else '  ') for n,x in enumerate(data)))
            lastData = data
        else:
            print(' '.join(f'{x:02x}' for x in data))
        return
    rawReadings=[]
    for index in range(48,101,4):
        # Unpack an int from here
        value = int.from_bytes(data[index:index+4:1],"little")
        rawReadings.append(value)
    # Index's that are known so far:
    # Array Index, Byte index, Name, Format
    # 00  -> 48   -> Voltage  -> mV*10000
    # 01  -> 52   -> Current  -> mA*100000
    # 02  -> 56   -> Watts    -> W*10000
    # 03  -> 60   -> ??
    # 04  -> 64   -> ??
    # 05  -> 68   -> Ohms     -> Ohms*10
    # 06  -> 72   -> mAh 0    -> mAh
    # 07  -> 76   -> mWh 0    -> mWh
    # 08  -> 80   -> mAh 1    -> mAh
    # 09  -> 84   -> mWh 1    -> mWh
    # 10  -> 88   -> Temp flag-> 1= -ve temp, 0=+ve temp
    # 11  -> 92   -> Temp     -> Deg C
    # 12  -> 96   -> D+ Volt  -> V*100
    # 13  -> 100  -> D- Volt  -> V*100
    
    
    voltage         = float(rawReadings[0])/10000
    current         = float(rawReadings[1])/100000
    power           = float(rawReadings[2])/10000
    # 3?
    # 4?
    ohms            = float(rawReadings[5])/10
    mAh0            = float(rawReadings[6])
    mWh0            = float(rawReadings[7])
    mAh1            = float(rawReadings[8])
    mWh1            = float(rawReadings[9])
    tempFlag        = float(rawReadings[10])
    temperature     = float(rawReadings[11])
    dataPlus        = float(rawReadings[12])/100
    dataMinus       = float(rawReadings[13])/100
    
    if(tempFlag==1):
        temperature=-temperature
    
    if tsv:
        elapsed = datetime.now() - start
        print(f'{elapsed}\t{voltage}\t{current}\t{power}\t{ohms}\t{mAh0}\t{mWh0}\t{mAh1}\t{mWh1}\t{temperature}\t{dataPlus}\t{dataMinus}')
    else:
        print(f'V: {voltage}\tI: {current}\tW: {power}\tΩ: {ohms}\tmAh: {mAh0}\tmWh: {mWh0}\tmAh: {mAh1}\tmWh: {mWh1}\tTemp: {temperature}\tD+: {dataPlus}\tD-: {dataMinus}')
    


def decodeDataBuffer(incomingBuffer):
    while len(incomingBuffer) >= 192:
        #decode the readings
        buffer = incomingBuffer[0:192]  # grab the first 192
        searchpattern = [112, 97, 99, 49]
        aeskeything = buffer[48:64]
        # printHex(aeskeything)
        decodedData = decrypt(buffer)

        # First 4 bytes of the message are always 'pac1'
        # This is hinted by a consant of 'pac1TC66' in the apk
        if (decodedData[0] == 112 and decodedData[1] == 97 and decodedData[2] == 99 and decodedData[3] == 49):
            handleDataPacket(decodedData)
            incomingBuffer = incomingBuffer[192:]
        else:
            incomingBuffer = incomingBuffer[1:]
    return incomingBuffer


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

# Main
parser = argparse.ArgumentParser(
                    prog='tc66_poll',
                    description='Polls the connected TC66/TC66C device via USB')
parser.add_argument('tty_dev', help='Path to the serial TTY device');
parser.add_argument('-t', '--tsv', action='store_true', help='Output a nice table in TSV format')
parser.add_argument('-x', '--hex', action='store_true', help='Dump the raw packets in hex')
parser.add_argument('-d', '--diff', action='store_true', help='Hex dump contains only changed values')
args = parser.parse_args()

tsv = args.tsv
hex = args.hex
diff = args.diff
ser = serial.Serial(args.tty_dev, 19200)

if ser != None:
    # eprint('Connected')

    if tsv:
        print(f'Time\tVoltage (V)\tCurrent (A)\tPower (W)\tResistance (Ω)\tmAh0\tmWh0\tmAh1\tmWh1\tTemperature\tD+ (V)\tD- (V)')


    # Setup polling loop
    rotateScreen = bytearray.fromhex('726f7461740d0a')
    backScreen = bytearray.fromhex('6c617374700d0a')
    forwScreen = bytearray.fromhex('6e657874700d0a')
    askForData = bytearray.fromhex('67657476610d0a')
    # eprint(backScreen)
    # eprint(rotateScreen)
    # eprint(forwScreen)
    # eprint(askForData)
    # eprint(bytearray.fromhex(
    #     '706163315443363631'))  # This appears to be the message marker?

    incomingBuffer = []
    while True:
        # eprint('Polling')
        ser.write(askForData)
        while (len(incomingBuffer) < 192):
            block = ser.read(64)
            incomingBuffer.extend(block)

        incomingBuffer = decodeDataBuffer(incomingBuffer)
        sys.stdout.flush()

else:
    eprint('No Devices Found')
