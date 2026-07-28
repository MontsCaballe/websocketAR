import asyncio
import json
import random
import time
from .websocket_handler import RFIDWebSocket

async def fake_rfid_reader():
    """
    Genera lecturas fake y las envía a todos los clientes WebSocket cada 2 segundos.
    """
    while True:
        # Simular una lectura RFID
        lectura_fake = {
            "epc": f"EPC{random.randint(1000, 9999)}",
            "vin": f"VIN{random.randint(100000, 999999)}",
            "folio": random.randint(10000000, 99999999),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "arco": "Arco Demo"
        }
        mensaje = json.dumps(lectura_fake)

        # Enviar a todos los clientes WebSocket conectados
        for cliente in list(RFIDWebSocket.clientes):
            try:
                cliente.write_message(mensaje)
            except:
                RFIDWebSocket.clientes.remove(cliente)

        print(f"📡 Enviando lectura fake: {mensaje}")

        await asyncio.sleep(2)  # No bloquear el event loop
