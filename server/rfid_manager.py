import threading
import logging
import json
import tornado.ioloop
from server.rfid_reader import RFIDReaderThread
import asyncio

class RFIDManager:
    def __init__(self, broadcast_func):
        self.broadcast_func = broadcast_func
        self.readers = {}
        self.lock = threading.Lock()
        self._arcos_data = []
        self.tag_queue = asyncio.Queue()

    def handle_new_tag(self, tag_data):
        # Este método se llama cada vez que se detecta un tag
        asyncio.run_coroutine_threadsafe(self.tag_queue.put(tag_data), asyncio.get_event_loop())


    async def get_next_tag(self):
        return await self.tag_queue.get()

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
        # Detener lectores que ya no están activos
        for ip in list(self.readers):
            if ip not in active_ips:
                self.stop_reader(ip)
        # 🔥 CONECTAR DE FORMA ESCALONADA
        import time
        for i, arco in enumerate(arcos):
            if arco['estado'] == 'conectado':
                if i > 0:
                    time.sleep(2)  # 2 segundos entre cada conexión
                self.start_reader(arco)
        # for arco in arcos:
        #     if arco['estado'] == 'conectado':
        #         self.start_reader(arco)
        # enviar_a_clientes(json.dumps({"type": "update_arcos", "arcos": arcos}))
        # 🔥 Manda arcos actualizados a todos los clientes
        from server.websocket import RFIDWebSocket
        RFIDWebSocket.broadcast_message(json.dumps({
            "type": "update_arcos",
            "arcos": arcos
        }))
    def get_arcos_data(self):
        """Retorna la lista actual de arcos con sus estados"""
        return self._arcos_data or []

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
