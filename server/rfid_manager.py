# import threading
# import logging
# from server.rfid_reader import RFIDReaderThread
# # from server.websocket import RFIDWebSocket



# class RFIDManager:
    
#     def __init__(self, broadcast_func):
#         self.broadcast_func = broadcast_func
#         self.readers = {}
#         self.lock = threading.Lock()
#         self.arcos_data = []
        
        
    
#     def initialize(self, arcos=None):
#         self.arcos_data = arcos or [{
#             "nombre": "Arco de pruebas",
#             "ip": "192.168.1.20",
#             "estado": "conectado",
#             "antenas": [1, 2],
#             "imagen": "/static/arcos/arco.png"
#         }]
    
#     @property
#     def arcos(self):
#         return self.arcos_data


#     def start_reader(self, arco):
#         ip = arco['ip']
#         # antennas = arco.get('antenas', [1])
#         # Transformar a posiciones locales 1..N
#         antennas_backend = arco.get('antenas', [])
#         antennas = list(range(1, len(antennas_backend) + 1)) or [1]

#         if ip in self.readers:
#             return  # Ya está corriendo
#         logging.info(f"✅ Conectando nuevo arco {ip}")
#         reader_thread = RFIDReaderThread(ip, antennas, self.broadcast_func)
#         with self.lock:
#             self.readers[ip] = reader_thread
#         reader_thread.start()

#     def stop_reader(self, ip):
#         with self.lock:
#             reader = self.readers.pop(ip, None)
#         if reader:
#             reader.stop()

#     def update_arcos(self, arcos):
#         self.arcos_data = arcos
#         logging.info(f"📝 update_arcos llamado con {len(arcos)} arcos")
#         if self.broadcast_func:
#             self.broadcast_func({
#                 "type": "update_arcos",
#                 "arcos": arcos
#             })


import threading
import logging
import json
import tornado.ioloop
from server.rfid_reader import RFIDReaderThread

class RFIDManager:
    def __init__(self, broadcast_func):
        self.broadcast_func = broadcast_func
        self.readers = {}
        self.lock = threading.Lock()
        self._arcos_data = []

    @property
    def arcos(self):
        return self._arcos_data

    def initialize(self, arcos=None):
        logging.info("📝 Inicializando arcos en RFIDManager")
        self._arcos_data = arcos or []

    def start_reader(self, arco):
        ip = arco['ip']
        antennas_backend = arco.get('antenas', [])
        antennas = list(range(1, len(antennas_backend) + 1)) or [1]

        if ip in self.readers:
            return
        logging.info(f"✅ Conectando nuevo arco {ip}")
        reader_thread = RFIDReaderThread(ip, antennas, self.broadcast_func, self.arcos)
        with self.lock:
            self.readers[ip] = reader_thread
        reader_thread.start()

    def stop_reader(self, ip):
        with self.lock:
            reader = self.readers.pop(ip, None)
        if reader:
            reader.stop()

    def update_arcos(self, arcos):
        logging.info(f"📝 update_arcos llamado con {len(arcos)} arcos")
        self._arcos_data = arcos
        active_ips = set(arco['ip'] for arco in arcos)
        for ip in list(self.readers):
            if ip not in active_ips:
                self.stop_reader(ip)
        for arco in arcos:
            if arco['estado'] == 'conectado':
                self.start_reader(arco)
        enviar_a_clientes(json.dumps({"type": "update_arcos", "arcos": arcos}))

def enviar_a_clientes(mensaje):
    from server.websocket import RFIDWebSocket
    io_loop = tornado.ioloop.IOLoop.current()
    io_loop.add_callback(lambda: _enviar_a_clientes(mensaje, RFIDWebSocket))

def _enviar_a_clientes(mensaje, websocket_class):
    for client in websocket_class.clients.copy():
        try:
            client.write_message(mensaje)
        except Exception as e:
            logging.error(f"❌ Error enviando mensaje a cliente: {e}")

rfid_manager = RFIDManager(None)
