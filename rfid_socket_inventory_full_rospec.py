import socket
import struct
import logging
import time

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("rfid_socket_inventory_full_rospec_log.txt", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

READER_IP = '192.168.1.20'
READER_PORT = 5084

def build_message(message_type, message_id, body_bytes):
    length = 10 + len(body_bytes)
    header = struct.pack('>HHQ', message_type, length, message_id)
    return header + body_bytes

def build_add_rospec():
    rospec_id = 123
    message_id = 1001

    # ROSpec Header: ROSpecID (4 bytes), Priority (1 byte), CurrentState (1 byte)
    rospec_header = struct.pack('>IBB', rospec_id, 0, 0)

    # ROBoundarySpec (StartTrigger + StopTrigger)
    start_trigger = struct.pack('>H', 0)  # Null trigger
    stop_trigger = struct.pack('>HI', 0, 0)  # Null stop trigger
    ro_boundary_spec = start_trigger + stop_trigger

    # InventoryParameterSpec (simple, protocol ID = 1 for EPCGlobalClass1Gen2)
    inventory_param_spec = struct.pack('>H H B', 1, 1, 1)  # ParamType, Length, ProtocolID

    # AISpecStopTrigger
    ai_spec_stop_trigger = struct.pack('>H I', 0, 0)  # Null trigger

    # AISpec: AntennaIDs (Array de 16-bit IDs, aquí solo antena 1)
    antenna_count = 1
    antenna_id = 1
    antenna_ids = struct.pack('>H', antenna_id)

    # AISpec completo
    ai_spec_header = struct.pack('>H H', 0x0104, len(antenna_ids) + len(ai_spec_stop_trigger) + len(inventory_param_spec) + 4)
    ai_spec = ai_spec_header + antenna_ids + ai_spec_stop_trigger + inventory_param_spec

    # ROReportSpec (reportar cada tag leído)
    ro_report_spec = struct.pack('>H H H I B B B', 0x0105, 12, 1, 1, 1, 0, 0)  # ReportTrigger, N, etc.

    body = rospec_header + ro_boundary_spec + ai_spec + ro_report_spec

    return build_message(0x0433, message_id, body)  # MessageType = 0x0433 (ADD_ROSPEC)

def build_enable_rospec(rospec_id):
    message_type = 0x0434  # ENABLE_ROSPEC
    message_id = 1002
    body = struct.pack('>I', rospec_id)
    return build_message(message_type, message_id, body)

def build_start_rospec(rospec_id):
    message_type = 0x0436  # START_ROSPEC
    message_id = 1003
    body = struct.pack('>I', rospec_id)
    return build_message(message_type, message_id, body)

def main():
    try:
        with socket.create_connection((READER_IP, READER_PORT), timeout=5) as sock:
            logging.info(f"✅ Conectado a {READER_IP}:{READER_PORT}")

            # ADD_ROSPEC
            add_msg = build_add_rospec()
            sock.sendall(add_msg)
            logging.info("✅ ADD_ROSPEC enviado.")

            time.sleep(0.5)

            # ENABLE_ROSPEC
            enable_msg = build_enable_rospec(123)
            sock.sendall(enable_msg)
            logging.info("✅ ENABLE_ROSPEC enviado.")

            time.sleep(0.5)

            # START_ROSPEC
            start_msg = build_start_rospec(123)
            sock.sendall(start_msg)
            logging.info("✅ START_ROSPEC enviado.")

            # Leer respuesta
            while True:
                response = sock.recv(4096)
                if not response:
                    break
                logging.info(f"📡 Respuesta recibida: {response.hex()}")

    except Exception as e:
        logging.error(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
