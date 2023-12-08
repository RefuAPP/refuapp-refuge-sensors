import time
import logging
import configparser
import json
import pandas as pd
import requests
import RPi.GPIO as GPIO
import board
import busio
import numpy as np
import adafruit_mlx90640


config = configparser.ConfigParser()
config.read('config.ini')
API_URL = config['API']['URL']
ID_REFUGIO = config['API']['ID_REFUGIO']
PASSWORD = config['API']['PASSWORD']

logging.basicConfig(level=logging.INFO)
UMBRAL_CAMBIO_TEMPERATURA = 5.0
class SensorLog:
    def __init__(self):
        self.df = pd.DataFrame(columns=['timestamp', 'status', 'sensor_id'])
        self.failed_requests = []

    def add_entry(self, sensor_id, status):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        new_entry = pd.DataFrame([[timestamp, status, sensor_id]], columns=self.df.columns)
        self.df = pd.concat([self.df, new_entry], ignore_index=True)

    def send_to_api(self, sensor_entry):
        data = {
            "id_refugio": ID_REFUGIO,
            "password": PASSWORD,
            "timestamp": sensor_entry['timestamp'],
            "status": sensor_entry['status'],
            "sensor_id": sensor_entry['sensor_id']
        }

        try:
            response = requests.post(f"{API_URL}/refugio/", json=data)
            if response.status_code != 200:
                logging.warning(f"Error en la API: {response.content}")
                self.failed_requests.append(data)
        except requests.exceptions.RequestException as e:
            logging.warning(f"Fallo al conectar con la API: {e}")
            self.failed_requests.append(data)

def setup_gpio(pin):
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin, GPIO.IN)

def read_sensor(pin):
    return GPIO.input(pin)


i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)
mlx = adafruit_mlx90640.MLX90640(i2c)
mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_2_HZ

def detect_movement_from_thermal_camera(temperatura_fondo):
    frame = np.zeros((24*32,))
    try:
        mlx.getFrame(frame)
        temperatura_actual = np.mean(frame)
        if abs(temperatura_actual - temperatura_fondo) > UMBRAL_CAMBIO_TEMPERATURA:
            return True
    except ValueError:
        pass
    return False

def main():
    temperatura_fondo = 20.0
    INFRARED_SENSOR_PIN = 21
    sensor_log = SensorLog()
    setup_gpio(INFRARED_SENSOR_PIN)

    last_sensor_value = None

    try:
        while True:

            sensor_value = read_sensor(INFRARED_SENSOR_PIN)
            if sensor_value != last_sensor_value:
                last_sensor_value = sensor_value
                status = "No obstacle" if sensor_value == 1 else "Obstacle"
                logging.info(f"Sensor infrarrojo: {status}")
                sensor_log.add_entry(INFRARED_SENSOR_PIN, status)
                sensor_log.send_to_api(sensor_log.df.iloc[-1].to_dict())

            if detect_movement_from_thermal_camera(temperatura_fondo):
                logging.info("Movimiento detectado por la cámara térmica")
                sensor_log.add_entry(2, "Thermal movement")
                sensor_log.send_to_api(sensor_log.df.iloc[-1].to_dict())

            time.sleep(1)

    except KeyboardInterrupt:
        logging.info("Programa interrumpido")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()