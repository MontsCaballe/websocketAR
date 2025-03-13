import logging
import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.httpserver
import warnings
import requests
import httpx
import socket
import time
import asyncio
import os
import sys
import atexit
from ping3 import ping
from sllurp.reader import R420

# URLs
URL_DEVICES = "https://apirepuve.minayarit.gob.mx/recaudacion/arcos-repuve/"
URL_ANTENNAS = "https://apirepuve.minayarit.gob.mx/recaudacion/antenas-repuve/"
API_URL = "https://apirepuve.minayarit.gob.mx/tramites/lecturas-arcos/"
URL_LECTURAS = "https://192.168.0.200/tramites/lecturas-arcos/"

# Archivos de Log
LOG_API = "logs_api.txt"
LOG_LECTURAS = "logs_lecturas.txt"

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_API, mode="a"),
        logging.StreamHandler(sys.stdout)  # También imprime en consola
    ]
)

# Variables globales
devices_with_data = []
devices_without_data = []

def cerrar_logs():
    """Cerrar los logs cuando la aplicación se cierra."""
    logging.info("🛑 Cerrando aplicación y liberando logs.")
    for handler in logging.getLogger().handlers:
        handler.close()
    print("✅ Logs cerrados correctamente.")

# Registrar la función para que se ejecute al cerrar la aplicación
atexit.register(cerrar_logs)

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        """Manejo de solicitudes HTTP en la ruta principal."""
        self.set_status(200)
        # Convertir las listas de dispositivos en HTML
        devices_with_data_html = "<ul>" + "".join(
            f"<li>ID: {device['id']}, IP: {device.get('ip')}, MAC: {device.get('mac_address')}</li>"
            for device in devices_with_data
        ) + "</ul>"
        
        devices_without_data_html = "<ul>" + "".join(
            f"<li>ID: {device['id']}, Nombre: {device.get('nombre')}</li>"
            for device in devices_without_data
        ) + "</ul>"
        
        # Define el contenido HTML para mostrar el mensaje de bienvenida y los pasos de conexión, junto con las listas
        html_content = f"""
        <html>
            <head>
                <title>Bienvenido al WebSocket</title>
                <style>
                    body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                    h1 {{ color: #333; }}
                    p {{ font-size: 18px; color: #555; }}
                    .steps {{ margin-top: 20px; text-align: left; display: inline-block; max-width: 600px; }}
                    .step {{ margin-bottom: 15px; }}
                    .device-list {{ text-align: left; margin-top: 20px; }}
                    .device-list h2 {{ color: #444; }}
                </style>
            </head>
            <body>
                <h1>Bienvenido al WebSocket</h1>
                <p>Este servicio permite la conexión en tiempo real utilizando WebSocket.</p>
                <div class="steps">
                    <h2>Pasos para conectarse:</h2>
                    <div class="step">
                        <strong>Paso 1:</strong> Asegúrate de que tu cliente soporte conexiones WebSocket.
                    </div>
                    <div class="step">
                        <strong>Paso 2:</strong> Conéctate a la URL de WebSocket del servidor:<br>
                        <code>ws://172.17.1.245/wsArcos</code>
                    </div>
                    <div class="step">
                        <strong>Paso 3:</strong> Envía y recibe mensajes en tiempo real después de establecer la conexión.
                    </div>
                    <div class="step">
                        <strong>Paso 4:</strong> Cierra la conexión cuando hayas terminado de interactuar.
                    </div>
                </div>
                <div class="device-list">
                    <h2>Dispositivos Disponibles para Conexión</h2>
                    {devices_with_data_html}
                    <h2>Dispositivos sin Datos para Conexión</h2>
                    {devices_without_data_html}
                </div>
            </body>
        </html>
        """
        
        # Escribe el contenido HTML en la respuesta
        self.write(html_content)

class WebSocketHandler(tornado.websocket.WebSocketHandler):
    clients = set()

    def open(self):
        WebSocketHandler.clients.add(self)
        logging.info("🔗 WebSocket conectado.")

    def on_message(self, message):
        logging.info(f"📩 Mensaje recibido: {message}")
        self.write_message("Mensaje recibido.")

    def on_close(self):
        WebSocketHandler.clients.remove(self)
        logging.info("❌ WebSocket cerrado.")

async def fetch_device_data():
    """Consulta los dispositivos y sus antenas."""
    async with httpx.AsyncClient(verify=False) as client:
        try:
            response_devices = await client.get(URL_DEVICES)
            response_devices.raise_for_status()
            devices = response_devices.json()

            response_antennas = await client.get(URL_ANTENNAS)
            response_antennas.raise_for_status()
            antennas = response_antennas.json()

            for device in devices:
                device["antenas"] = [ant for ant in antennas if ant["arcos"] == device["id"]]

            return devices
        except Exception as e:
            logging.error(f"❌ Error al obtener dispositivos: {e}")
            return []

async def process_inventory_data(tag):
    """Procesa los datos de inventario de un tag RFID y los envía a la API."""
    data = {"vin": "3N1CK3CD4LL211137", "folio": tag.epc, "arco": 2, "antena": 1}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(API_URL, json=data)
            response.raise_for_status()
            logging.info(f"✅ Datos enviados: {data}")
    except Exception as e:
        logging.error(f"❌ Error enviando datos: {e}")

async def process_tag_data(tag, ip):
    """Procesa los datos de inventario de un tag RFID y los envía a la API."""
    
    # Leer TID del banco TID, si está disponible en el tag
    tid = tag['EPC-96'].hex()  # Convertir el EPC (TID) a una cadena hexadecimal para su visualización
    logging.info(f"TID: {tid}")
    # Obtener los datos de ReadData desde OpSpecResult, que contiene los datos del banco de Usuario
    user_data = tag['OpSpecResult']['ReadData']
    logging.info(f"🏷️ Banco de Usuario - ReadData: {user_data.hex()}")
    
    if len(user_data) >= 13:  # Asegura que haya suficiente data en ReadData
        # Los primeros 4 bytes para 'folio' (ajusta según la estructura específica del usuario)
        folio = str(int(user_data[:4].hex(), 16))
        # Extrae VIN en el formato deseado (ajusta la posición según la estructura de usuario)
        vin = ConvertHex(user_data[4:34].hex())  # Suponiendo que vin empieza en el quinto byte
        
        
        # Suprimir la advertencia (solo para pruebas)
        warnings.filterwarnings("ignore", message="Unverified HTTPS request")
        # Remueve los caracteres nulos en vin
        vin = vin.replace('\x00', '').strip()
        logging.info(f"🏷️ Folio: {folio}")
        logging.info(f"🏷️ VIN: {vin}")
               
        # Identificar antena y dispositivo
        antenna_index = tag.get('AntennaID', 1) - 1  # Ajustamos a índice de arreglo (0-based)
        associated_device = next((d for d in devices_with_data if d.get("ip").strip() == ip.strip()), None)
        arco_id = None
        antenna_id = None
        
        if associated_device:
            logging.info(f"⚠️ Device found: {associated_device}")
            # Busca la antena por índice en el arreglo de antenas
            antenas = associated_device.get("antenas", [])
            if 0 <= antenna_index < len(antenas):
                antenna = antenas[antenna_index]
                antenna_id = antenna.get("id")
                arco_id = antenna.get("arcos")
                logging.info(f"✅ Antenna found: {antenna}")
            else:
                logging.info(f"❌ Antenna index {antenna_index} out of range for device {associated_device}")
        else:
            logging.info(f"❌ No device found with IP {ip}")

        
        # Preparar la URL y el payload
        url = URL_LECTURAS
        payload = {
            "vin": vin,
            "folio": folio,
            "arco": arco_id,
            "antena": antenna_id
        }
            
        
        # payload = {"vin": vin,"folio": folio,"arco": 5,"antena": 1}

        logging.info(f"⚠️ Sending POST request to URL: {url} with payload: {payload}")        
        
        try:
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.post(url, json=payload, timeout=6)  # Tiempo máximo de espera de 6 segundos
                response.raise_for_status()
                logging.info(f"👓 Respuesta de la API: {response}")
                logging.info(f"📑 Datos enviados: {payload}")
        except Exception as e:
            
            logging.error(f"❌ Error enviando datos: {e}")
            logging.info(f" Datos enviados: {payload}")
        

async def connect_to_device(device):
    """Intenta conectar al dispositivo RFID mediante LLRP."""
    ip = device.get("ip")
    reader = R420(ip)
    logging.info(f"🔌 Conectando a {ip}...")
      
    # setup access spec
    epcLen = 12 # total number of bytes
    epcRawStart = b'\x12\x34\x56\x78' # let the raw EPC URI start with these bytes
    epcRawUri = epcRawStart+b'\x00'*(epcLen-len(epcRawStart)) # fill up with zeros
    readSpecParam = {
            'OpSpecID': 0,
            'MB':3,
            'WordPtr': 0,
            'AccessPassword': 0,
            'WordCount': 13
    }

    try:
        reader.startAccess(readWords=readSpecParam)
        tags = reader.detectTags()
        for tag in tags:
            logging.info(f"🏷️ Tag detectado: {tag}")         
            logging.info(f"💻 Procesando TAG ")   
            asyncio.create_task(process_tag_data(tag,ip))
    except Exception as e:
        logging.error(f"❌ Error con dispositivo {ip}: {e}")

async def connect_to_devices():
    """Maneja la conexión a los dispositivos filtrando por latencia."""
    for device in devices_with_data:
        if device.get('estatus') == '1':  # Solo conecta si está activo
            ip_dispositivo = device.get("ip")
            latencia = medir_latencia_tcp(ip_dispositivo)
            logging.info(f"📟 IP Dispositivo {ip_dispositivo}")
            if latencia is None:
                logging.warning(f"⚠️ No se pudo medir latencia de {ip_dispositivo}")
                continue

            if latencia < 100:
                logging.info(f"✅ Latencia segura ({latencia:.2f} ms). Conectando...")
                await asyncio.wait_for(connect_to_device(device), timeout=0.5)
            elif 100 <= latencia < 150:
                logging.warning(f"⚠️ Latencia moderada ({latencia:.2f} ms). Intentando conexión...")
                await asyncio.wait_for(connect_to_device(device), timeout=0.5)
            else:
                logging.error(f"🚨 Latencia alta ({latencia:.2f} ms). Descartando conexión.")

async def update_device_lists():
    """Actualiza la lista de dispositivos periódicamente."""
    global devices_with_data, devices_without_data
    while True:
        try:
            new_devices = await fetch_device_data()
            devices_with_data = [d for d in new_devices if d.get("ip") and d["ip"] != "0"]
            devices_without_data = [d for d in new_devices if not d.get("ip") or d["ip"] == "0"]
            logging.info(f"🔄 Dispositivos actualizados: {len(devices_with_data)} con datos, {len(devices_without_data)} sin datos.")

            await connect_to_devices()
            await asyncio.sleep(10)  # Esperar antes de volver a consultar
        except Exception as e:
            logging.error(f"❌ Error actualizando lista de dispositivos: {e}")

def ConvertHex(hex_string):
    try:
        # Convertimos la cadena hexadecimal a bytes, luego a texto ASCII
        text = bytes.fromhex(hex_string).decode('ascii')
    except ValueError:
        # Si el hex no es un valor ASCII válido, devolvemos una cadena vacía o un valor predeterminado
        text = ""
    return text


def medir_latencia_tcp(ip):
    """Mide la latencia TCP hacia el dispositivo."""
    puertos = [80, 443, 502, 8080, 1883, 5084, 5085, 9000]
    for puerto in puertos:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            start_time = time.time()
            sock.connect((ip, puerto))
            latency = (time.time() - start_time) * 1000
            sock.close()
            return latency
        except Exception:
            continue
    return None

def make_app():
    """Crea la aplicación Tornado."""
    return tornado.web.Application([
        (r"/", MainHandler),
        (r"/wsArcos", WebSocketHandler),
    ])

async def main():
    """Función principal que inicia Tornado y las tareas asincrónicas."""
    # Crear archivos de log si no existen
    for log_file in [LOG_API, LOG_LECTURAS]:
        if not os.path.exists(log_file):
            with open(log_file, "w") as f:
                f.write("=== Inicio del Log ===\n")

    asyncio.create_task(update_device_lists())

    app = make_app()
    server = tornado.httpserver.HTTPServer(app)
    server.listen(8888)
    logging.info("🚀 Tornado server iniciado en el puerto 8888")

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
    tornado.ioloop.IOLoop.current().start()
