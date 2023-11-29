import time
import logging
import configparser
import json
import pandas as pd
import requests
import RPi.GPIO as GPIO

# Configuración
config = configparser.ConfigParser()
config.read('config.ini')
API_URL = config['API']['URL']
ID_REFUGIO = config['API']['ID_REFUGIO']
PASSWORD = config['API']['PASSWORD']

logging.basicConfig(level=logging.INFO)

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
        if self.failed_requests:
            with open("failed_requests.log", "a") as f:
                for failed_entry in self.failed_requests:
                    f.write(f"{json.dumps(failed_entry)}\n")

def setup_gpio(pin):
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin, GPIO.IN)
    
def read_sensor(pin):
    return GPIO.input(pin)

def main():
    GPIO_PIN = 21  
    sensor_log = SensorLog()
    setup_gpio(GPIO_PIN)

    last_sensor_value = None

    try:
        while True:
            sensor_value = read_sensor(GPIO_PIN)

            if sensor_value != last_sensor_value:
                last_sensor_value = sensor_value

                status = "No obstacle" if sensor_value == 1 else "Obstacle"
                logging.info(f"Sensor: {status}")
                sensor_log.add_entry(GPIO_PIN, status)

                sensor_log.send_to_api(sensor_log.df.iloc[-1].to_dict())
                sensor_log.df = sensor_log.df.iloc[0:0]

            time.sleep(1)

    except KeyboardInterrupt:
        logging.info("Programa interrumpido")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()