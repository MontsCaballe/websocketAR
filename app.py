# import logging
# import tornado.ioloop
# import tornado.web
# import tornado.websocket
# from server.websocket_handler import RFIDWebSocket
# from server.dashboard_handler import DashboardHandler
# from server.rfid_service import fake_rfid_reader
# from server.arcos_service import obtener_arcos
# from server.rfid_manager import RFIDManager

# # Configuración de logging
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s [%(levelname)s] %(message)s',
#     handlers=[
#         logging.FileHandler("log.txt", encoding="utf-8"),
#         logging.StreamHandler()
#     ]
# )
# # 🔥 Obtener lista de arcos reales desde la API
# arcos = obtener_arcos()

# def make_app(arcos):
    
#     return tornado.web.Application([
#         (r"/", DashboardHandler, dict(arcos=arcos)),   # ✅ Pasar arcos al handler
#         (r"/ws", RFIDWebSocket, dict(arcos=arcos)),    # ✅ También al WebSocket
#         (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": "static"}),
#     ],
#     template_path="templates",
#     static_path="static",
#     debug=True)

# if __name__ == "__main__":   
    
#     if not arcos:
#         logging.warning("⚠️ No se pudieron obtener arcos desde la API. Usando datos fake.")
#         arcos = [
#             {"nombre": "Arco 1 – Plaza Laguna", "ip": "192.168.1.20", "antenas": [1], "estado": "conectado", "imagen": "/static/arcos/arco.png"}
#         ]
#     app = make_app(arcos)
#     app.listen(8888)
#     logging.info("✅ Servidor Tornado y WebSocket iniciado en http://localhost:8888")

#     # Inicia el RFIDManager y pasa la función de broadcast
#     rfid_manager = RFIDManager(RFIDWebSocket.broadcast_message)
#     rfid_manager.start()

#     # Iniciar lector fake si no hay arcos reales
#     if all(a["estado"] == "desconectado" for a in arcos):
#         logging.info("🌀 Iniciando lector fake por falta de arcos reales.")
#         tornado.ioloop.IOLoop.current().spawn_callback(fake_rfid_reader)

#     tornado.ioloop.IOLoop.current().start()
# import tornado.ioloop
# import tornado.web
# import tornado.httpserver
# import threading
# import logging
# from server.websocket import RFIDWebSocket
# from server.rfid_manager import RFIDManager
# from server.dashboard_handler import DashboardHandler
# from server.api_client import fetch_arcos_periodically

# logging.basicConfig(level=logging.INFO)

# if __name__ == '__main__':
#     rfid_manager = RFIDManager(RFIDWebSocket.broadcast_message)
#     app = tornado.web.Application([
#          (r'/', DashboardHandler, dict(rfid_manager=rfid_manager)),
#         (r'/ws', RFIDWebSocket)
#     ], template_path='templates',  debug=True)

    

#     def arcos_updater():
#         while True:
#             try:
#                 for arcos in fetch_arcos_periodically():
#                     logging.info(f"🔁 API devolvió {len(arcos)} arcos")
#                     rfid_manager.update_arcos(arcos)
#             except Exception as e:
#                 logging.error(f"❌ Error actualizando arcos: {e}")


#     updater_thread = threading.Thread(target=arcos_updater, daemon=True)
#     updater_thread.start()

#     server = tornado.httpserver.HTTPServer(app)
#     server.listen(8888)
#     logging.info("✅ Servidor Tornado y WebSocket iniciado en http://localhost:8888")
#     tornado.ioloop.IOLoop.current().start()
import os
import threading
import logging
import tornado.ioloop
import tornado.web
import tornado.httpserver
from dotenv import load_dotenv

from server.rfid_manager import rfid_manager
from server.websocket import RFIDWebSocket
from server.dashboard_handler import DashboardHandler
from server.api_client import fetch_arcos_periodically

load_dotenv()
logging.basicConfig(level=logging.INFO)
# 🔥 Calcula ruta absoluta a templates
base_dir = os.path.dirname(__file__)
templates_path = os.path.join(base_dir, "templates")
static_path = os.path.join(base_dir, "static")  # 🔥 ruta a static


def arcos_updater():
    """Hilo que consulta periódicamente la API y actualiza los arcos"""
    for arcos in fetch_arcos_periodically():
        rfid_manager.update_arcos(arcos)
        try:
            RFIDWebSocket.broadcast_message({
                "type": "update_arcos",
                "arcos": arcos
            })
            logging.info("📡 Enviado update_arcos a los clientes")
        except Exception as e:
            logging.error(f"❌ Error enviando arcos a clientes: {e}")

if __name__ == "__main__":
    app = tornado.web.Application([
        (r'/', DashboardHandler, dict(rfid_manager=rfid_manager)),
        (r'/ws', RFIDWebSocket),
        (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": static_path}),  # 💥 Static handler
    ], debug=True, template_path=templates_path)

    # Iniciar hilo para actualizar arcos periódicamente
    updater_thread = threading.Thread(target=arcos_updater, daemon=True)
    updater_thread.start()

    # Iniciar servidor HTTP
    server = tornado.httpserver.HTTPServer(app)
    port = int(os.getenv("PORT", 8888))
    server.listen(port)
    logging.info(f"✅ Servidor Tornado y WebSocket iniciado en http://localhost:{port}")

    tornado.ioloop.IOLoop.current().start()

