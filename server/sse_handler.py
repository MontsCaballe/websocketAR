import tornado.web
import tornado.ioloop
import json
import logging
from server.websocket import tag_queue


class SSEHandler(tornado.web.RequestHandler):
    async def get(self):
        self.set_header('Content-Type', 'text/event-stream')
        self.set_header('Cache-Control', 'no-cache')
        self.set_header('Connection', 'keep-alive')

        logging.info(f"🌐 Cliente SSE conectado: {self.request.remote_ip}")

        try:
            while True:
                tag_data = await tag_queue.get()
                message = f"data: {json.dumps({'type': 'tag_read', 'tag': tag_data})}\n\n"
                self.write(message)
                await self.flush()
                logging.info(f"📡 Enviado via SSE: {tag_data}")
        except tornado.iostream.StreamClosedError:
            logging.info("🔌 Cliente SSE desconectado")
        except Exception as e:
            logging.error(f"❌ Error en SSEHandler: {e}")
