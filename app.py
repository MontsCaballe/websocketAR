import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.httpserver
import warnings
import requests
import httpx
import asyncio
from sllurp import llrp
import sys
sys.path.append('./sllurp/reader.py')
from sllurp.reader import Reader, R420
import logging
from ping3 import ping

# url = "https://apirepuve.minayarit.gob.mx/tramites/lecturas-arcos/"
        # payload = {"vin": "3N1CK3CD4LL211137","folio": vin,"arco": 2,"antena": 1}

# URL de consulta de los dispositivos
URL_DEVICES = "https://apirepuve.minayarit.gob.mx/recaudacion/arcos-repuve/"
URL_ANTENNAS = "https://apirepuve.minayarit.gob.mx/recaudacion/antenas-repuve/"
# URL de la API donde se almacenarán los datos
API_URL = "https://apirepuve.minayarit.gob.mx/tramites/lecturas-arcos/"

# Variables globales
devices_with_data = []
devices_without_data = []

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        # Establece el código de estado HTTP 200 (OK)
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
        print("WebSocket opened")

    def on_message(self, message):
        print("Received message:", message)
        self.write_message("Message received")

    def on_close(self):
        WebSocketHandler.clients.remove(self)
        print("WebSocket closed")

async def fetch_device_data():
    async with httpx.AsyncClient(verify=False) as client:
        # Consulta los dispositivos
        response_devices = await client.get(URL_DEVICES)
        response_devices.raise_for_status()
        devices = response_devices.json()
        
        # Verifica si 'devices' es una lista y, si es así, conviértela en un diccionario
        if isinstance(devices, list):
            devices = {device['id']: device for device in devices}

        # Consulta las antenas
        response_antennas = await client.get(URL_ANTENNAS)
        response_antennas.raise_for_status()
        antennas = response_antennas.json()
        
        # Asociar antenas a cada dispositivo
        devices_with_antennas = []

        for device_id, device in devices.items():
            # Filtrar antenas que tienen el mismo id de dispositivo en 'arcos'
            device_antennas = [antenna for antenna in antennas if antenna['arcos'] == device_id]
            
            # Agregar la lista de antenas al dispositivo
            device_with_antennas = {**device, "antenas": device_antennas}
            
            # Agregar el dispositivo con antenas a la lista final
            devices_with_antennas.append(device_with_antennas)

        return devices_with_antennas

async def process_inventory_data(tag):
    """
    Procesa los datos de inventario leídos de cada etiqueta RFID y los envía a una API.
    """
    # Preparar los datos a enviar en la solicitud POST
    # data = {
    #     "epc": tag.epc,
    #     "rssi": tag.rssi,
    #     "antenna_port": tag.antenna_port
    # }

    data = {"vin": "3N1CK3CD4LL211137","folio": tag.epc,"arco": 2,"antena": 1}
    
    try:
        # Enviar los datos a la API mediante una solicitud POST
        async with httpx.AsyncClient() as client:
            response = await client.post(API_URL, json=data)
            response.raise_for_status()  # Verificar si la solicitud fue exitosa
            print(f"Data sent successfully: {data}")
    except httpx.HTTPStatusError as exc:
        print(f"Error sending data: {exc.response.status_code} - {exc.response.text}")
    except Exception as e:
        print(f"An error occurred: {e}")

async def connect_to_device(device):
    ip = device.get("ip")
    # mac_address = device.get("mac_address")
    # logging.basicConfig(filename='llrp.log', level=logging.DEBUG)
    reader = R420(ip)
    
    # reader.
    
    print(f"Connecting to device at IP: {ip}")
    
    # setup access spec
    epcLen = 12 # total number of bytes
    epcRawStart = b'\x12\x34\x56\x78' # let the raw EPC URI start with these bytes
    epcRawUri = epcRawStart+b'\x00'*(epcLen-len(epcRawStart)) # fill up with zeros
    # note: 1 Word = 2 Bytes
    # writeSpecParam = {
    #         'OpSpecID': 0,
    #         'MB': 3,
    #         'WordPtr': 2,
    #         'AccessPassword': 0,
    #         'WriteDataWordCount': len(epcRawUri)//2,
    #         'WriteData': epcRawUri,
    # }
    # reader.startAccess(writeWords=writeSpecParam, opCount=0) # set opCount to 1 to stop after 1 write operation
    # Actually adds and enables an access spec.
    # It is executed with the next inventory round (reader.detectTags())


    readSpecParam = {
            'OpSpecID': 0,
            'MB':3,
            'WordPtr': 0,
            'AccessPassword': 0,
            'WordCount': 13
    }
    reader.startAccess(readWords=readSpecParam)
    

    print('Before start:')
    tags = reader.detectTags(powerDBm=16, antennas=(0,)) # remove antennas argument or set to (0,) to use all antenna ports
#     tag_report = reader.startLiveReports(
#     reportCallback=tag_seen_callback2,  # Tu función de callback
#     powerDBm=31.5,                     # Potencia en dBm
#     freqMHz=866.9,                     # Frecuencia en MHz
#     mode=1002,                         # Modo de operación
#     searchmode=3,                      # Modo de búsqueda
#     tagInterval=1,                    # Opcional: cada 10 tags encontrados, reportar
#     timeInterval=2                     # Opcional: cada 5 segundos, si tagInterval está configurado
# )
    
    print(tags)
    for tag in tags:
            resultado_convertido = {k: v.hex() if isinstance(v, bytes) else v for k, v in tag.items()}
            print(tag)
             # Leer TID del banco TID, si está disponible en el tag
            tid = tag['EPC-96'].hex()  # Convertir el EPC (TID) a una cadena hexadecimal para su visualización
            print(f"TID: {tid}")
        
            # Obtener los datos de ReadData desde OpSpecResult, que contiene los datos del banco de Usuario
            user_data = tag['OpSpecResult']['ReadData']
            print(f"Banco de Usuario - ReadData: {user_data.hex()}")
            # Procesar ReadData para obtener 'folio' y 'vin' según las posiciones especificadas
            if len(user_data) >= 13:  # Asegura que haya suficiente data en ReadData
                # Los primeros 4 bytes para 'folio' (ajusta según la estructura específica del usuario)
                folio = str(int(user_data[:4].hex(), 16))
                # Extrae VIN en el formato deseado (ajusta la posición según la estructura de usuario)
                vin = ConvertHex(user_data[4:34].hex())  # Suponiendo que vin empieza en el quinto byte
                
                print(f"Folio: {folio}")
                print(f"VIN: {vin}")
                # Suprimir la advertencia (solo para pruebas)
                warnings.filterwarnings("ignore", message="Unverified HTTPS request")
                # Remueve los caracteres nulos en vin
                vin = vin.replace('\x00', '').strip()
               
                url = "https://192.168.0.200/tramites/lecturas-arcos/"
                payload = {"vin": vin,"folio": folio,"arco": 2,"antena": 1}

                print(f"Sending POST request to URL: {url} with payload: {payload}")
                
                try:
                    response = requests.post(url, json=payload, verify=False)  # Realiza la solicitud POST
                    
                    if response.status_code == 200:
                        print(f"API response for {vin}: {response.json()}")
                    else:
                        print(f"Failed to fetch data from API. Status code: {response.status_code}")
                except Exception as e:
                    print(f"Error querying API: {e}")
            
def tag_seen_callback(tags):
    print(tags)
    if len(tags) > 0 :
        for tag in tags:
                        
                # Obtener los datos de ReadData desde OpSpecResult, que contiene los datos del banco de Usuario
                user_data = tag['OpSpecResult']['ReadData']
                
                print(f"Banco de Usuario - ReadData: {user_data.hex()}")
                # Procesar ReadData para obtener 'folio' y 'vin' según las posiciones especificadas
                if len(user_data) >= 13:  # Asegura que haya suficiente data en ReadData
                    # Los primeros 4 bytes para 'folio' (ajusta según la estructura específica del usuario)
                    folio = str(int(user_data[:4].hex(), 16))
                    # Extrae VIN en el formato deseado (ajusta la posición según la estructura de usuario)
                    vin = ConvertHex(user_data[4:34].hex())  # Suponiendo que vin empieza en el quinto byte
                    
                    print(f"Folio: {folio}")
                    print(f"VIN: {vin}")
 
def tag_seen_callback2(tags):
    print(tags)
    if len(tags) > 0:
        for tag in tags:
            # Verificar si 'OpSpecResult' está presente en el tag
            if 'OpSpecResult' in tag:
                # Obtener los datos de ReadData desde OpSpecResult
                user_data = tag['OpSpecResult'].get('ReadData')
                
                if user_data:
                    print(f"Banco de Usuario - ReadData: {user_data.hex()}")
                    # Procesar ReadData para obtener 'folio' y 'vin' según las posiciones especificadas
                    if len(user_data) >= 13:
                        # Los primeros 4 bytes para 'folio' (ajusta según la estructura específica del usuario)
                        folio = str(int(user_data[:4].hex(), 16))
                        # Extrae VIN en el formato deseado (ajusta la posición según la estructura de usuario)
                        vin = ConvertHex(user_data[4:34].hex())  # Suponiendo que vin empieza en el quinto byte
                        
                        print(f"Folio: {folio}")
                        print(f"VIN: {vin}")
                else:
                    print("No hay datos en 'ReadData' en este tag.")
            else:
                print("No se encontró 'OpSpecResult' en este tag.")

async def connect_to_devices():
    # Conectar a todos los dispositivos con datos
    for device in devices_with_data:
        if device.get('estatus') == '1':  # Verificar si el estatus es '1'
            try:
                # Limitar el tiempo de conexión a 0.5 segundos
                # connect_to_device(device)
                # Realizar ping antes de intentar la conexión
                if device['ip'] and await ping_device(device['ip']):  # Solo intentar conectar si el ping tiene éxito
                    try:
                        # Limitar el tiempo de conexión a 0.5 segundos
                        await asyncio.wait_for(connect_to_device(device), timeout=0.5)
                    except asyncio.TimeoutError:
                        print(f"Tiempo de espera agotado para el dispositivo {device['ip']}, intentando con el siguiente.")
                    except Exception as e:
                        print(f"Error inesperado con el dispositivo {device['ip']}: {e}")
                else:
                    print(f"Dispositivo {device['ip']} no está disponible o no respondió al ping.")
                # await asyncio.wait_for(connect_to_device(device), timeout=0.5)
            except asyncio.TimeoutError:
                print(f"Tiempo de espera agotado para el dispositivo {device['ip']}, intentando con el siguiente.")
            except Exception as e:
                print(f"Error inesperado con el dispositivo {device['ip']}: {e}")
        else:
            print(f"Dispositivo {device['ip']} ignorado, estatus: {device.get('estatus')}")


async def update_device_lists():
    global devices_with_data, devices_without_data
    while True:
        try:
            # Obtener los datos actuales de los dispositivos
            new_devices = await fetch_device_data()

            # Convertir la lista actual de devices_without_data a un conjunto de ids para fácil comparación
            if(len(devices_without_data)>0):
                existing_ids_without_data = {device['id'] for device in devices_without_data}
            else:
                existing_ids_without_data = []

            # Listas temporales para los nuevos datos
            new_devices_with_data = []
            new_devices_without_data = []

            for device in new_devices:
                ip = device.get("ip")
                mac_address = device.get("mac_address")

                # Clasificar dispositivos
                # if ip is not None and mac_address is not None:
                if ip is not None and ip != '0':
                    new_devices_with_data.append(device)
                else:
                    # Verificar si el dispositivo ya estaba en la lista de dispositivos sin datos completos
                    if device['id'] not in existing_ids_without_data:
                        # print(f"Adding new device without data: {device}")
                        new_devices_without_data.append(device)

            # Actualizar las listas globales
            devices_with_data = new_devices_with_data
            devices_without_data.extend(new_devices_without_data)  # Agregar solo los nuevos dispositivos sin datos

            # Imprimir las listas actualizadas
            print("Updated devices with data:", devices_with_data)
            # print("Updated devices without data:", devices_without_data)

            # Conectarse a los nuevos dispositivos en devices_with_data
            await connect_to_devices()

            # Esperar un intervalo de tiempo antes de volver a consultar
            await asyncio.sleep(1)  # Consulta cada 60 segundos (ajusta según tus necesidades)

        except Exception as e:
            print("Error updating device lists:", e)
            # await asyncio.sleep(1)  # Esperar antes de intentar de nuevo en caso de error

def convertir_EPC_a_texto(diccionario):
    diccionario_copia = diccionario.copy()
    if 'EPC-96' in diccionario_copia:
        valor_bytes = diccionario_copia['EPC-96']
        valor_texto = valor_bytes.decode('utf-8')
        diccionario_copia['EPC-96'] = valor_texto
        print(f'Valor Bytes: {valor_bytes}')
        print(f'Valor Texto: {valor_texto}')
    return diccionario_copia

def ConvertHex(hex_string):
    try:
        # Convertimos la cadena hexadecimal a bytes, luego a texto ASCII
        text = bytes.fromhex(hex_string).decode('ascii')
    except ValueError:
        # Si el hex no es un valor ASCII válido, devolvemos una cadena vacía o un valor predeterminado
        text = ""
    return text
async def ping_device(ip):
    """Realiza un ping a la IP del dispositivo y devuelve True si responde."""
    try:
        response_time = ping(ip, timeout=2)  # Timeout de 2 segundos
        if response_time is None:
            print(f"Dispositivo en {ip} no responde al ping.")
            return False
        else:
            print(f"Dispositivo en {ip} respondió en {response_time} segundos.")
            return True
    except Exception as e:
        print(f"Error al hacer ping a {ip}: {e}")
        return False
# Llamada a la función en un contexto asíncrono
def handle_tag_read(tag):
    asyncio.create_task(process_inventory_data(tag))

def make_app():
    return tornado.web.Application([
        (r"/", MainHandler),
        (r"/wsArcos", WebSocketHandler),
    ])

async def main():
    # Iniciar el proceso de actualización de listas de dispositivos
    asyncio.create_task(update_device_lists())

    # Configura y ejecuta el servidor Tornado
    app = make_app()
    server = tornado.httpserver.HTTPServer(app)
    server.listen(8888)
    print("Tornado server started on port 8888")

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
    tornado.ioloop.IOLoop.current().start()
