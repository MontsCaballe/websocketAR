import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.httpserver
import tornado.platform.asyncio

import httpx
import asyncio
import logging
import warnings
import json
from ping3 import ping

# Se asume que sllurp y sus clases (Reader, R420) están en PYTHONPATH
from sllurp.reader import Reader, R420

# =====================================================
# CONFIGURACIÓN: Endpoints remotos y variables globales
# =====================================================

# Endpoints remotos (ajusta estos valores según tu entorno)
URL_DEVICES = "https://apirepuve.minayarit.gob.mx/recaudacion/arcos-repuve/"
URL_ANTENNAS = "https://apirepuve.minayarit.gob.mx/recaudacion/antenas-repuve/"
API_URL = "https://apirepuve.minayarit.gob.mx/tramites/lecturas-arcos/"

# Listas globales de dispositivos y tareas de conexión
devices_with_data = []    # Lista de dispositivos con datos completos (por ejemplo, con IP)
devices_without_data = [] # Lista de dispositivos incompletos
device_tasks = {}         # Dict: {device_id: asyncio.Task}

# Control manual de conexiones:
# Si manual_control[device_id] es:
#   - True: se fuerza la conexión (incluso si la API indica inactividad)
#   - False: se fuerza la desconexión (la tarea se cancelará)
#   - None (o no existe): se usa el estatus recibido de la API.
manual_control = {}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# =====================================================
# HANDLERS: Servidor HTTP y WebSocket
# =====================================================

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        devices_with_data_html = "<ul>" + "".join(
            f"<li>ID: {device['id']}, IP: {device.get('ip')}, MAC: {device.get('mac_address')}</li>"
            for device in devices_with_data
        ) + "</ul>"

        devices_without_data_html = "<ul>" + "".join(
            f"<li>ID: {device['id']}, Nombre: {device.get('nombre')}</li>"
            for device in devices_without_data
        ) + "</ul>"

        html_content = f"""
        <html>
            <head>
                <title>WebSocket Real-Time Reader</title>
                <style>
                    body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                    h1 {{ color: #333; }}
                </style>
            </head>
            <body>
                <h1>WebSocket Real-Time Reader</h1>
                <div>
                    <h2>Dispositivos con Datos:</h2>
                    {devices_with_data_html}
                    <h2>Dispositivos sin Datos:</h2>
                    {devices_without_data_html}
                </div>
            </body>
        </html>
        """
        self.write(html_content)

class WebSocketHandler(tornado.websocket.WebSocketHandler):
    clients = set()

    def open(self):
        WebSocketHandler.clients.add(self)
        logging.info("Cliente WebSocket conectado")
        self.write_message(json.dumps({"message": "Conexión WebSocket establecida"}))

    def on_message(self, message):
        try:
            data = json.loads(message)
        except Exception as e:
            logging.error("Mensaje inválido recibido, no es JSON")
            self.write_message(json.dumps({"error": "Invalid JSON"}))
            return

        action = data.get("action")
        device_id = data.get("device_id")
        # Mensajes de control para conectar o desconectar dispositivos:
        if action in ["connect", "disconnect"] and device_id:
            if action == "disconnect":
                manual_control[device_id] = False
                if device_id in device_tasks:
                    task = device_tasks[device_id]
                    if not task.done():
                        logging.info(f"Cancelando conexión para dispositivo {device_id} por orden del cliente")
                        task.cancel()
                    del device_tasks[device_id]
                self.write_message(json.dumps({"status": f"Dispositivo {device_id} desconectado manualmente"}))
            elif action == "connect":
                manual_control[device_id] = True
                # Si no hay tarea activa para este dispositivo, se intenta iniciar la conexión
                if device_id not in device_tasks:
                    device = next((d for d in devices_with_data if d.get("id") == device_id), None)
                    if device:
                        logging.info(f"Iniciando conexión manual para dispositivo {device.get('ip')}")
                        task = asyncio.create_task(maintain_device_connection(device))
                        device_tasks[device_id] = task
                        self.write_message(json.dumps({"status": f"Conexión manual iniciada para dispositivo {device_id}"}))
                    else:
                        self.write_message(json.dumps({"error": f"Dispositivo {device_id} no encontrado"}))
            return
        # Solicitud para obtener el estado de los dispositivos
        elif action == "get_status":
            status = {"devices": []}
            for device in devices_with_data:
                d_id = device.get("id")
                connected = d_id in device_tasks and not device_tasks[d_id].done()
                status["devices"].append({
                    "id": d_id,
                    "ip": device.get("ip"),
                    "connected": connected,
                    "manual": manual_control.get(d_id, None)
                })
            self.write_message(json.dumps(status))
        else:
            logging.info(f"Mensaje recibido (no control): {data}")
            self.write_message(json.dumps({"message": "Mensaje recibido"}))

    def on_close(self):
        WebSocketHandler.clients.discard(self)
        logging.info("Cliente WebSocket desconectado")

def broadcast_message(message: dict):
    """
    Envía (broadcast) un mensaje JSON a todos los clientes WebSocket conectados.
    """
    message_json = json.dumps(message)
    for client in list(WebSocketHandler.clients):
        try:
            client.write_message(message_json)
        except Exception as e:
            logging.error(f"Error al enviar mensaje a cliente: {e}")

# =====================================================
# FUNCIONES DE UTILIDAD ASÍNCRONAS
# =====================================================

async def async_ping(ip: str, timeout: int = 2) -> bool:
    """
    Ejecuta un ping a la IP indicada en un executor para no bloquear el event loop.
    Devuelve True si hay respuesta; False en caso contrario.
    """
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, ping, ip, timeout)
        if result is not None:
            logging.info(f"Ping a {ip} respondió en {result} segundos.")
            return True
        else:
            logging.info(f"Ping a {ip} sin respuesta.")
            return False
    except Exception as e:
        logging.error(f"Error al hacer ping a {ip}: {e}")
        return False

async def fetch_device_data():
    """
    Consulta la API remota para obtener la lista de dispositivos y las antenas asociadas.
    Devuelve una lista de dispositivos combinados.
    """
    async with httpx.AsyncClient(verify=False) as client:
        response_devices = await client.get(URL_DEVICES)
        response_devices.raise_for_status()
        devices = response_devices.json()
        if isinstance(devices, list):
            devices = {device['id']: device for device in devices}

        response_antennas = await client.get(URL_ANTENNAS)
        response_antennas.raise_for_status()
        antennas = response_antennas.json()

        devices_with_antennas = []
        for device_id, device in devices.items():
            device_antennas = [antenna for antenna in antennas if antenna['arcos'] == device_id]
            device_with_antennas = {**device, "antenas": device_antennas}
            devices_with_antennas.append(device_with_antennas)
        return devices_with_antennas

def convert_hex(hex_string: str) -> str:
    """
    Convierte una cadena hexadecimal a texto ASCII.
    Si la conversión falla, devuelve cadena vacía.
    """
    try:
        return bytes.fromhex(hex_string).decode('ascii')
    except Exception:
        return ""

# =====================================================
# CONEXIÓN Y LECTURA DE LOS DISPOSITIVOS
# =====================================================

def connect_to_device_blocking(device: dict):
    """
    Función bloqueante (para ejecutarse en un hilo) que:
      - Se conecta al dispositivo (usando la clase R420 de sllurp).
      - Configura la lectura (startAccess) y detecta etiquetas.
      - Para cada tag detectado, llama a process_tag.
    """
    ip = device.get("ip")
    logging.info(f"Iniciando conexión bloqueante para dispositivo {ip}")
    try:
        reader = R420(ip)
        readSpecParam = {
            'OpSpecID': 0,
            'MB': 3,
            'WordPtr': 0,
            'AccessPassword': 0,
            'WordCount': 13
        }
        reader.startAccess(readWords=readSpecParam)
        tags = reader.detectTags()
        logging.info(f"Dispositivo {ip} detectó {len(tags)} etiquetas.")
        for tag in tags:
            process_tag(tag, device)
    except Exception as e:
        logging.error(f"Error en la conexión/lectura del dispositivo {ip}: {e}")

def process_tag(tag: dict, device: dict):
    """
    Procesa la información de un tag:
      - Extrae datos (ej. folio y vin) a partir del campo 'ReadData'.
      - Envía la información a la API mediante una petición HTTP (síncrona).
      - Además, notifica vía WebSocket (se usa add_callback ya que se ejecuta en un hilo).
    """
    try:
        user_data = tag.get('OpSpecResult', {}).get('ReadData')
        if not user_data or len(user_data) < 13:
            logging.warning("Datos insuficientes en el tag.")
            return

        folio = str(int(user_data[:4].hex(), 16))
        vin = convert_hex(user_data[4:34].hex()).replace('\x00', '').strip()

        payload = {
            "vin": vin,
            "folio": folio,
            "arco": None,
            "antena": None,
            "device_ip": device.get("ip")
        }

        logging.info(f"Procesando tag del dispositivo {device.get('ip')}: {payload}")

        # Enviar datos a la API de forma síncrona.
        response = httpx.post(API_URL, json=payload, verify=False, timeout=6)
        if response.status_code == 200:
            logging.info(f"Respuesta API: {response.json()}")
        else:
            logging.error(f"Error en API (código {response.status_code}): {response.text}")

        # Construir el mensaje a enviar vía WebSocket.
        tag_message = {
            "type": "tag_read",
            "device_id": device.get("id"),
            "device_ip": device.get("ip"),
            "folio": folio,
            "vin": vin
        }
        # Debido a que esta función se ejecuta en un hilo, se usa add_callback para enviar el mensaje.
        tornado.ioloop.IOLoop.current().add_callback(broadcast_message, tag_message)
    except Exception as e:
        logging.error(f"Error procesando tag: {e}")

async def maintain_device_connection(device: dict):
    """
    Tarea asíncrona que mantiene la conexión con un dispositivo:
      - Verifica (cada ciclo) que el dispositivo esté activo según la API y/o control manual.
      - Ejecuta un ping; si tiene éxito, llama a la función bloqueante en un hilo.
      - Si la conexión finaliza (por error o desconexión), espera unos segundos y vuelve a intentarlo.
    """
    ip = device.get("ip")
    device_id = device.get("id")
    logging.info(f"Iniciando mantenimiento de conexión para dispositivo {ip}")
    while True:
        # Si se ha forzado desconexión manual, salir.
        if manual_control.get(device_id) is False:
            logging.info(f"Conexión para dispositivo {ip} detenida por control manual.")
            return

        # Si no se ha forzado conexión y la API indica inactividad, esperar.
        if manual_control.get(device_id) is not True and device.get("estatus") != "1":
            logging.info(f"Dispositivo {ip} inactivo según API. Esperando...")
            await asyncio.sleep(5)
            continue

        if not await async_ping(ip):
            logging.info(f"Ping falló para {ip}. Reintentando en 5 segundos...")
            await asyncio.sleep(5)
            continue

        try:
            logging.info(f"Conectando al dispositivo {ip}...")
            await asyncio.to_thread(connect_to_device_blocking, device)
            logging.info(f"Conexión finalizada para {ip}, se reintentará...")
        except Exception as e:
            logging.error(f"Excepción en conexión con {ip}: {e}")
        await asyncio.sleep(5)

# =====================================================
# TAREA DE ACTUALIZACIÓN DE LA LISTA DE DISPOSITIVOS
# =====================================================

async def update_device_lists():
    """
    Tarea que consulta periódicamente la API remota para:
      - Actualizar las listas globales de dispositivos.
      - Crear (o reiniciar) tareas de conexión para cada dispositivo activo
        (usando el estatus de la API y/o un control manual).
      - Cancelar tareas para dispositivos que hayan sido forzados a desconectarse.
    """
    global devices_with_data, devices_without_data, device_tasks

    while True:
        try:
            new_devices = await fetch_device_data()

            new_devices_with_data = []
            new_devices_without_data = []
            for device in new_devices:
                ip = device.get("ip")
                if ip and ip != '0':
                    new_devices_with_data.append(device)
                else:
                    new_devices_without_data.append(device)
            devices_with_data = new_devices_with_data
            devices_without_data = new_devices_without_data

            # Para cada dispositivo, decidir si se debe mantener la conexión.
            for device in devices_with_data:
                device_id = device.get("id")
                should_connect = False
                if manual_control.get(device_id) is False:
                    should_connect = False
                elif manual_control.get(device_id) is True:
                    should_connect = True
                elif device.get("estatus") == "1":
                    should_connect = True

                if should_connect:
                    if device_id not in device_tasks or device_tasks[device_id].done():
                        logging.info(f"Lanzando tarea para dispositivo {device.get('ip')}")
                        task = asyncio.create_task(maintain_device_connection(device))
                        device_tasks[device_id] = task

            # Cancelar tareas para dispositivos que hayan quedado inactivos o forzados a desconectarse.
            for device_id, task in list(device_tasks.items()):
                device = next((d for d in devices_with_data if d.get("id") == device_id), None)
                if not device or manual_control.get(device_id) is False:
                    if not task.done():
                        logging.info(f"Cancelando tarea para dispositivo {device_id}")
                        task.cancel()
                    del device_tasks[device_id]

            await asyncio.sleep(10)
        except Exception as e:
            logging.error(f"Error actualizando la lista de dispositivos: {e}")
            await asyncio.sleep(10)

# =====================================================
# CONFIGURACIÓN DEL APP Y PUNTO DE ENTRADA
# =====================================================

def make_app():
    return tornado.web.Application([
        (r"/", MainHandler),
        (r"/wsArcos", WebSocketHandler),
    ])

async def main():
    # Inicia la tarea de actualización de dispositivos
    asyncio.create_task(update_device_lists())

    # Configura y arranca el servidor Tornado en el puerto 8888
    app = make_app()
    server = tornado.httpserver.HTTPServer(app)
    server.listen(8888)
    logging.info("Servidor Tornado iniciado en el puerto 8888.")

    # Mantiene el main task vivo para que el event loop no finalice
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    # Configuramos el AsyncIOLoop de Tornado basado en asyncio
    tornado.platform.asyncio.AsyncIOLoop().install()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Cerrando la aplicación...")
