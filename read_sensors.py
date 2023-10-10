import time
import logging
import configparser
import json
import pandas as pd
import requests  
import RPi.GPIO as GPIO  

# Configuracion
config = configparser.ConfigParser()
config.read('config.ini')
API_URL = config['API']['URL']
ID_REFUGIO = config['API']['ID_REFUGIO']  
PASSWORD = config['API']['PASSWORD'] 


logging.basicConfig(level=logging.INFO)

class SensorLog:
    def __init__(self):
        self.df = pd.DataFrame(columns=['timestamp', 'status', 'sensor_id'])
        self.failed_requests = []  # Lista para almacenar solicitudes fallidas

    def add_entry(self, sensor_id, status):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        new_entry = pd.DataFrame([[timestamp, status, sensor_id]], columns=self.df.columns)
        self.df = pd.concat([self.df, new_entry], ignore_index=True)

    def send_to_api(self):
        data_dict = self.df.to_dict(orient='records')
        endpoint = f"{API_URL}/sensor/"

        for entry in data_dict:
            entry['id_refugio'] = ID_REFUGIO
            entry['password'] = PASSWORD

            try:
                response = requests.post(endpoint, json=entry)
                if response.status_code != 200:
                    logging.warning(f"Error en la API: {response.content}")
                    self.failed_requests.append(entry)
            except requests.exceptions.RequestException as e:
                logging.warning(f"Fallo al conectar con la API: {e}")
                self.failed_requests.append(entry)

        # Guarda las solicitudes fallidas en un archivo log
        if self.failed_requests:
            with open("failed_requests.log", "a") as f:
                for failed_entry in self.failed_requests:
                    f.write(f"{json.dumps(failed_entry)}\n")

        # Intenta reenviar las solicitudes fallidas
        for failed_entry in self.failed_requests:
            try:
                response = requests.post(endpoint, json=failed_entry)
                if response.status_code == 200:
                    self.failed_requests.remove(failed_entry)
            except requests.exceptions.RequestException:
                pass

def setup_gpio(pins):
    GPIO.setmode(GPIO.BCM)
    for pin in pins:
        GPIO.setup(pin, GPIO.IN)

def read_sensor(pin):
    return GPIO.input(pin)


def main():
    GPIO_PINS = [20, 21]
    sensor_log = SensorLog()
    setup_gpio(GPIO_PINS)
    
    last_sensor_values = {pin: None for pin in GPIO_PINS} 

    try:
        while True:
            for i, pin in enumerate(GPIO_PINS):
                sensor_value = read_sensor(pin)

                if sensor_value != last_sensor_values[pin]:
                    last_sensor_values[pin] = sensor_value  

                    if sensor_value == 1:
                        logging.info(f"Sensor {i+1}: Ningún obstáculo detectado")
                        sensor_log.add_entry(i+1, "No obstacle")
                    else:
                        logging.warning(f"Sensor {i+1}: Obstáculo detectado")
                        sensor_log.add_entry(i+1, "Obstacle")

                    sensor_log.send_to_api()  
                    sensor_log.df = sensor_log.df.iloc[0:0] 

            time.sleep(1)

    except KeyboardInterrupt:
        logging.info("Programa interrumpido")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()

