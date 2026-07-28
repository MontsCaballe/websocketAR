import threading
import logging
import time
import sllurp
from sllurp.llrp import LLRPReaderClient, LLRPReaderConfig, C1G2Read
import requests
import tornado
from server.websocket import tag_queue  # 👈 Importamos la cola para SSE
from sllurp import llrp
from server import rfid_manager
import os
from dotenv import load_dotenv
load_dotenv()

# 🔥 Buffer global para EPCs
buffer_tags = {}
TTL_SEGUNDOS = 3600

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
        # 🧹 Limpiar tags viejos antes de procesar nuevos
        now = time.time()
        for tag_epc in list(buffer_tags.keys()):
            last_sent = buffer_tags[tag_epc]['last_sent']
            if last_sent and (now - last_sent) > (TTL_SEGUNDOS * 2):
                logging.info(f"🧹 Eliminando tag expirado {tag_epc.hex()}")
                del buffer_tags[tag_epc]
        for tag in tag_reports:
            logging.info(f"📡 Tag detectado en {self.ip}: {tag}")

            epc = tag.get('EPC-96') or tag.get('EPC')
            vin, folio = None, None

            if epc:
                folio, msg = self.parse_epc_folio(epc)
                logging.info(msg)
                # 📝 Si el EPC no existe en buffer, agregarlo
                if epc not in buffer_tags:
                    buffer_tags[epc] = {'vin': None, 'folio': None, 'enviado': False,'last_sent': None}

                # Actualiza folio si lo obtuviste
                if folio:
                    buffer_tags[epc]['folio'] = folio

            result = tag.get('C1G2ReadOpSpecResult')
            if result and result.get('Result') == 0 and result.get('ReadData'):
                user_memory = result['ReadData']
                vin, msg = self.parse_user_memory(user_memory)
                logging.info(msg)
                 # Actualiza vin si lo obtuviste
                if vin:
                    buffer_tags[epc]['vin'] = vin
            else:
                logging.warning("⚠️ No se obtuvo User Memory o hubo error en lectura")

            data = {
                "ip": self.ip,
                "epc": epc.hex() if epc else None,
                "vin": vin,
                "folio": folio
            }

            logging.info(f"📡 Tag listo para enviar a la api {data}")

            # 🔥 Si ya tenemos VIN y Folio y no se ha enviado
            if (buffer_tags[epc]['vin'] and buffer_tags[epc]['folio'] 
                    and not buffer_tags[epc]['enviado']):
                
                should_send = False
                # 📌 Si nunca se ha enviado, envía
                if not buffer_tags[epc]['enviado']:
                    should_send = True
                else:
                    # 📌 Si ya se envió, verifica si ha pasado el TTL
                    last_sent = buffer_tags[epc]['last_sent']
                    if last_sent and (now - last_sent) > TTL_SEGUNDOS:
                        logging.info(f"⏳ Tag {epc.hex()} expiró TTL, reenviando...")
                        should_send = True

                if should_send:
                    data = {
                    "ip": self.ip,
                    "epc": epc.hex() if epc else None,
                    "vin": buffer_tags[epc]['vin'],
                    "folio": buffer_tags[epc]['folio']
                    }

                    logging.info(f"📡 Enviando tag completo: {data}")

                    # ✅ Enviar a SSE
                    from server.websocket import tag_queue
                    tag_queue.put_nowait(data)
                    logging.info(f"📡 Enviado a SSE: {data}")

                    # ✅ Enviar a WebSocket
                    from server.websocket import RFIDWebSocket
                    RFIDWebSocket.send_tag_to_clients({"type": "tag_read", "tag": data})

                    # ✅ Enviar a API
                    self.enviar_a_api(data, tag, vin , folio)

                    # 🔥 Marcar como enviado
                    buffer_tags[epc]['enviado'] = True
            

            

           

    def run(self):
        try:
            self.running = True
            logging.info(f"📡 Iniciando lector en {self.ip}")

            config = LLRPReaderConfig()
            config.antennas = self.antennas
            config.tx_power = {ant: 91 for ant in self.antennas}
            config.impinj_search_mode = 2
            config.start_inventory = True
            config.reset_on_connect = True
            config.rx_sensitivity = -80
            config.mode_identifier = 4

        #    # 🔥 CONFIGURACIÓN OPTIMIZADA PARA ENLACES UBIQUITI
            config.connect_timeout = 30      # 30 segundos (Ubiquiti es más rápido que Mikrotik)
            config.socket_timeout = 60       # 60 segundos para operaciones
            config.response_timeout = 15     # 15 segundos para respuestas
            config.keepalive = True
            config.keepalive_interval = 20   # Keep-alive cada 20 segundos
            # # 🔥 CONFIGURACIÓN ESPECÍFICA PARA ENLACES MIKROTIK
            # config.connect_timeout = 45      # 45 segundos (Mikrotik puede ser lento)
            # config.socket_timeout = 90       # 90 segundos para operaciones
            # config.response_timeout = 20     # 20 segundos para respuestas
            # config.keepalive = True
            # config.keepalive_interval = 25   # Keep-alive cada 25 segundos
            # 🔥 TIMEOUTS ESPECÍFICOS PARA ENLACES INALÁMBRICOS
            # config.connect_timeout = 60      # 1 minuto para conectar
            # config.socket_timeout = 120      # 2 minutos para operaciones
            # config.response_timeout = 30     # 30 segundos para respuestas
            # config.keepalive = True
            # config.keepalive_interval = 30   # Keep-alive cada 30 segundos
            # 🔥 Timeouts para WAN
            # config.connect_timeout = 30
            # config.socket_timeout = 60

            self.reader = LLRPReaderClient(self.ip, config=config)
            self.reader.add_tag_report_callback(self.tag_report_callback)
            
            # logging.info(f"📡 Desconectando lector {self.ip}")
            
            # self.reader.disconnect()
            logging.info(f"📡 Conectando lector {self.ip}")
            self.reader.connect()
            # self.limpiar_reader(self.reader)
            # self.borrar_specs(self.reader)



            time.sleep(5)  # pequeña pausa para AccessSpec

            read_op = C1G2Read(
                OpSpecID=1,
                AccessPassword=0,
                MB=3,          # User Memory Bank
                WordPtr=0,     # Desde la posición 0
                WordCount=13   # Leer 16 palabras (32 bytes por si acaso)
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
    def enviar_a_api(self, data, tag, vin, folio):
        # ======================
            # 🔥 Paso final: Consumo API
            # ======================
            try:               

                url = "https://192.168.0.200/tramites/lecturas-arcos/"
                antenna_index = tag.get('AntennaID', 1) - 1  # Ajusta a índice 0-based

                # Reconstruir arcos y antenas en caliente
                arco_id = None
                antenna_id = None

                for device in self.devices_with_data:
                    if device.get("ip").strip() == self.ip.strip():
                        logging.info(f"✅ Dispositivo encontrado en devices_with_data: {device}")
                        antennas = device.get("antenas", [])
                        if 0 <= antenna_index < len(antennas):
                            antenna = antennas[antenna_index]
                            if isinstance(antenna, dict):
                                antenna_id = antenna.get("id")
                                arco_id = device.get("id")  # Usa el id del device como arco
                                logging.info(f"✅ Antena dict encontrada: {antenna}")
                            else:
                                # Si es solo un número, asumimos id=posicion
                                antenna_id = antenna
                                arco_id = device.get("id")  # Usa el id del device como arco
                                logging.info(f"✅ Antena simple encontrada (id={antenna_id})")
                        else:
                            logging.warning(f"⚠️ Antenna index {antenna_index} fuera de rango para {self.ip}")


                if arco_id is None or antenna_id is None:
                    logging.warning(f"⚠️ No se pudo determinar arco/antena para IP {self.ip}")
                
                rango_inicio = int(os.getenv("RANGOINI", 0))
                rango_fin = int(os.getenv("RANGOFIN", 1))
                # Validar si el folio está dentro del rango
                if rango_inicio is not None and rango_fin is not None:
                    # Asumiendo que el folio es numérico
                    try:
                        folio_num = int(folio)
                        if rango_inicio <= folio_num <= rango_fin:
                            tipo_tag = "morado"
                        else:
                            tipo_tag = "azul"
                    except (ValueError, TypeError):
                        # Si el folio no es numérico, asignar azul por defecto
                        tipo_tag = "azul"
                else:
                    # Si no hay rango definido, asignar azul por defecto
                    tipo_tag = "azul"

                payload = {
                    "vin": vin,
                    "folio": folio,
                    "arco": arco_id,
                    "antena": antenna_id,
                    "tipo_tag": tipo_tag
                }
               
                # ✅ Enviar a SSE (sin bloquear hilo)
                from server.websocket import tag_queue
               
                tag_queue.put_nowait(data)
                logging.info(f"📡 Enviado a SSE (tag_queue): {data}")

                # ✅ Enviar a WebSocket también
                from server.websocket import RFIDWebSocket
                RFIDWebSocket.send_tag_to_clients({"type": "tag_read", "tag": data})
                
                time.sleep(0.1)
                logging.info(f"🌐 Enviando POST a {url} con payload: {payload}")
                response = requests.post(url, json=payload, verify=False, timeout=6)

                if response.status_code == 200:
                    logging.info(f"✅ API respuesta para {vin}: {response.json()}")
                else:
                    logging.warning(f"⚠️ API respondió código {response.status_code}")
                 
            except Exception as e:
                logging.error(f"❌ Error al consumir API: {e}")

    # def run(self):
    #     while not self.stop_event.is_set():
    #         try:
    #             self.running = True
    #             logging.info(f"📡 Iniciando lector en {self.ip}")

    #             config = LLRPReaderConfig()
    #             config.antennas = self.antennas
    #             config.tx_power = {ant: 31 for ant in self.antennas}
    #             config.impinj_search_mode = 2
    #             config.start_inventory = True
    #             config.reset_on_connect = True

    #             self.reader = LLRPReaderClient(self.ip, config=config)
    #             self.reader.add_tag_report_callback(self.tag_report_callback)

    #             logging.info(f"📡 Conectando lector {self.ip}")
    #             self.reader.connect()

    #             # 💥 Limpiar specs después de conexión exitosa
    #             # self.borrar_specs(self.reader)

    #             time.sleep(2)  # Pequeña pausa para estabilidad

    #             read_op = C1G2Read(
    #                 OpSpecID=1,
    #                 AccessPassword=0,
    #                 MB=3,          # User Memory Bank
    #                 WordPtr=0,     # Desde la posición 0
    #                 WordCount=16   # Leer 16 palabras (32 bytes)
    #             )

    #             # Inicia lectura con AccessSpec
    #             self.reader.start_access_spec(op_spec=read_op, stop_after_count=0)

    #             self.reader.join()  # Esperar mientras esté corriendo
    #         except Exception as e:
    #             logging.error(f"❌ Error en lector {self.ip}: {e}")
    #             logging.info(f"🔁 Reintentando conexión en 5 segundos...")
    #             time.sleep(5)  # Espera antes de intentar de nuevo
    #         finally:
    #             if self.reader:
    #                 self.reader.disconnect()
    #                 logging.info(f"🔌 Lector desconectado {self.ip}")
    #             self.running = False

    def stop(self):
        self.running = False
        if self.reader:
            self.reader.disconnect()

    # def limpiar_reader(self, reader):
    #     """Elimina todos los ROSpecs y AccessSpecs activos en el lector."""
    #     try:
    #         delete_rospec = sllurp.llrp.messages.DELETE_ROSPEC(rospecID=0) # type: ignore
    #         delete_accessspec = sllurp.llrp.messages.DELETE_ACCESSSPEC(accessSpecID=0) # type: ignore

    #         response_rospec = reader._conn.transact(delete_rospec, timeout=2)
    #         logging.info(f"♻️ ROSpecs eliminados en {self.ip}: {response_rospec}")

    #         response_accessspec = reader._conn.transact(delete_accessspec, timeout=2)
    #         logging.info(f"♻️ AccessSpecs eliminados en {self.ip}: {response_accessspec}")

    #     except Exception as e:
    #         logging.warning(f"⚠️ No se pudieron eliminar specs en {self.ip}: {e}")

    # def borrar_specs(self, client):
    #     """Elimina todos los ROSpecs y AccessSpecs activos en el lector."""
    #     try:
    #         # 🗑 Borrar todos los ROSpecs
    #         delete_rospec = llrp.LLRPMessage(0x0C, {'ROSpecID': 0})
    #         response_rospec = client.transact_message(delete_rospec, timeout=2)

    #         if response_rospec == 0:
    #             logging.info(f"✅ ROSpecs eliminados en {self.ip}")
    #         else:
    #             logging.warning(f"⚠️ Fallo al eliminar ROSpecs en {self.ip} (código {response_rospec})")

    #         # 🗑 Borrar todos los AccessSpecs
    #         delete_accessspec = llrp.LLRPMessage(0x1D, {'AccessSpecID': 0})
    #         response_accessspec = client.transact_message(delete_accessspec, timeout=2)

    #         if response_accessspec == 0:
    #             logging.info(f"✅ AccessSpecs eliminados en {self.ip}")
    #         else:
    #             logging.warning(f"⚠️ Fallo al eliminar AccessSpecs en {self.ip} (código {response_accessspec})")

    #     except Exception as e:
    #         logging.warning(f"⚠️ No se pudieron eliminar specs en {self.ip}: {e}")




    



