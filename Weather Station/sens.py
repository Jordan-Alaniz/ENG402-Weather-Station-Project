from bme680 import *
from machine import I2C, Pin
import machine
import time

# define the I2C interface for BME680
i2c0 = I2C(0, scl=Pin(9), sda=Pin(8), freq=100000)
# initialize BME680 sensor
bme680 = BME680_I2C(i2c0)

def getTime():
    rtc = machine.RTC()
    currentDateTime = rtc.datetime()
    year = currentDateTime[0]
    month = currentDateTime[1]
    day = currentDateTime[2]
    hour = currentDateTime[4]
    minutes = currentDateTime[5]
    seconds = currentDateTime[6]
    return(f"{year}-{month:0>2}-{day:0>2}T{hour:0>2}:{minutes:0>2}:{seconds:0>2}")

def sens():
    temperature = bme680.temperature
    humidity = bme680.humidity
    pressure = bme680.pressure
    return [temperature, humidity, pressure, getTime()]

print(sens())
