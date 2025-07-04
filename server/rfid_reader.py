import threading
import logging
import time
from sllurp.llrp import LLRPReaderClient, LLRPReaderConfig, C1G2Read
import requests

# devices_with_data = []
class RFIDReaderThread(threading.Thread):
    def __init__(self, ip, antennas, broadcast_callback, devices_with_data):
        super().__init__()
        self.ip = ip
        self.antennas = antennas or [1]
        self.broadcast_callback = broadcast_callback
        self.running = False
        self.reader = None
        self.devices_with_data = devices_with_data  # 👈 Guardamos la lista
        self.stop_event = threading.Event()
        

    def parse_user_memory(self, raw_bytes):
        try:
            if not raw_bytes or len(raw_bytes) < 25:
                return None, "❌ Memoria insuficiente para extraer VIN"
            vin_start = 8
            vin_end = vin_start + 17
            vin_bytes = raw_bytes[vin_start:vin_end]
            vin = vin_bytes.decode('ascii', errors='ignore').strip()
            return vin, f"✅ VIN desde User Memory: {vin}"
        except Exception as e:
            return None, f"❌ Error parseando memoria: {e}"

    def parse_epc_folio(self, epc_bytes):
        try:
            hex_string = epc_bytes.decode('ascii', errors='ignore')
            ascii_bytes = bytes.fromhex(hex_string)
            folio = ascii_bytes.decode('ascii', errors='ignore').strip()
            return folio, f"✅ Folio desde EPC: {folio}"
        except Exception as e:
            return None, f"❌ Error al parsear EPC: {e}"

    def tag_report_callback(self, reader, tag_reports):
        for tag in tag_reports:
            logging.info(f"📡 Tag detectado en {self.ip}: {tag}")

            epc = tag.get('EPC-96') or tag.get('EPC')
            vin, folio = None, None

            if epc:
                folio, msg = self.parse_epc_folio(epc)
                logging.info(msg)

            result = tag.get('C1G2ReadOpSpecResult')
            if result and result.get('Result') == 0 and result.get('ReadData'):
                user_memory = result['ReadData']
                vin, msg = self.parse_user_memory(user_memory)
                logging.info(msg)
            else:
                logging.warning("⚠️ No se obtuvo User Memory o hubo error en lectura")

            data = {
                "ip": self.ip,
                "epc": epc.hex() if epc else None,
                "vin": vin,
                "folio": folio
            }

            logging.info(f"📡 Tag listo para enviar a la api {data}")
            

            # ======================
            # 🔥 Paso final: Consumo API
            # ======================
            try:
                

                url = "https://192.168.0.200/tramites/lecturas-arcos/"
                antenna_index = tag.get('AntennaID', 1) - 1  # Ajusta a índice 0-based

                # Reconstruir arcos y antenas en caliente
                arco_id = None
                antenna_id = None

                # 🔥 Aquí defines manualmente (o reconstruyes) el mapping IP -> arco y antenas
                # Por ejemplo:
                arco_mapping = {
                    "192.168.1.20": {
                        "arco": 6,  # ID del arco
                        "antenas": [
                            {"id": 1, "posicion": 1},
                            {"id": 2, "posicion": 2}
                        ]
                    },
                    # Agrega otros arcos si es necesario
                }

                arco_info = arco_mapping.get(self.ip)
                if arco_info:
                    arco_id = arco_info["arco"]
                    antenas = arco_info.get("antenas", [])
                    if 0 <= antenna_index < len(antenas):
                        antenna = antenas[antenna_index]
                        antenna_id = antenna.get("id")
                        logging.info(f"✅ Antena reconstruida: {antenna}")
                    else:
                        logging.warning(f"⚠️ Antenna index {antenna_index} fuera de rango para {self.ip}")
                else:
                    logging.warning(f"⚠️ No se encontró configuración para IP {self.ip}")

                payload = {
                    "vin": vin,
                    "folio": folio,
                    "arco": arco_id,
                    "antena": antenna_id
                }

                logging.info(f"🌐 Enviando POST a {url} con payload: {payload}")
                response = requests.post(url, json=payload, verify=False, timeout=6)

                if response.status_code == 200:
                    logging.info(f"✅ API respuesta para {vin}: {response.json()}")
                else:
                    logging.warning(f"⚠️ API respondió código {response.status_code}")

            except Exception as e:
                logging.error(f"❌ Error al consumir API: {e}")
            self.broadcast_callback(data)


    def run(self):
        try:
            self.running = True
            logging.info(f"📡 Iniciando lector en {self.ip}")

            config = LLRPReaderConfig()
            config.antennas = self.antennas
            config.tx_power = {ant: 31 for ant in self.antennas}
            config.impinj_search_mode = 2
            config.start_inventory = True
            config.reset_on_connect = True

            self.reader = LLRPReaderClient(self.ip, config=config)
            self.reader.add_tag_report_callback(self.tag_report_callback)
            self.reader.connect()

            time.sleep(2)  # pequeña pausa para AccessSpec

            read_op = C1G2Read(
                OpSpecID=1,
                AccessPassword=0,
                MB=3,          # User Memory Bank
                WordPtr=0,     # Desde la posición 0
                WordCount=16   # Leer 16 palabras (32 bytes por si acaso)
            )
            self.reader.start_access_spec(op_spec=read_op, stop_after_count=0)

            self.reader.join()
        except Exception as e:
            logging.error(f"❌ Error en lector {self.ip}: {e}")
        finally:
            self.running = False
            if self.reader:
                self.reader.disconnect()
                logging.info(f"🔌 Lector desconectado {self.ip}")

    def stop(self):
        self.running = False
        if self.reader:
            self.reader.disconnect()
