import struct
import socket
import logging
import time

# Configuración de logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("rfid_socket_inventory_log.txt", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

READER_IP = '192.168.1.20'
READER_PORT = 5084

def build_add_rospec():
    # Un ROSpec mínimo para inventario simple usando Antena 1
    rospec_id = 123
    message_id = 10

    rospec = {
        'ROSpecID': rospec_id,
        'Priority': 0,
        'CurrentState': 0,
        'ROBoundarySpec': {
            'StartTrigger': {
                'ROSpecStartTriggerType': 0  # Null trigger (start immediately)
            },
            'StopTrigger': {
                'ROSpecStopTriggerType': 0,
                'DurationTriggerValue': 0
            }
        },
        'AISpec': [{
            'AntennaIDs': [1],
            'AISpecStopTrigger': {
                'AISpecStopTriggerType': 0,
                'DurationTrigger': 0
            },
            'InventoryParameterSpec': [{
                'InventoryParameterSpecID': 1,
                'ProtocolID': 1  # EPCGlobalClass1Gen2
            }]
        }],
        'ROReportSpec': {
            'ROReportTrigger': 1,  # Upon N tag reads or end of ROSpec
            'N': 1,
            'TagReportContentSelector': {
                'EnableEPCMemory': True,
                'EnableAntennaID': True,
                'EnableFirstSeenTimestamp': True
            }
        }
    }

    from sllurp.llrp_proto import LLRPMessage
    return LLRPMessage('ADD_ROSPEC', {'ROSpec': rospec}, messageID=message_id)

def build_enable_rospec(rospec_id):
    from sllurp.llrp_proto import LLRPMessage
    return LLRPMessage('ENABLE_ROSPEC', {'ROSpecID': rospec_id}, messageID=11)

def build_start_rospec(rospec_id):
    from sllurp.llrp_proto import LLRPMessage
    return LLRPMessage('START_ROSPEC', {'ROSpecID': rospec_id}, messageID=12)

def main():
    try:
        from sllurp.llrp_proto import encode_message

        with socket.create_connection((READER_IP, READER_PORT), timeout=5) as sock:
            logging.info(f"✅ Conectado a {READER_IP}:{READER_PORT}")

            # ADD_ROSPEC
            add_rospec_msg = build_add_rospec()
            sock.sendall(encode_message(add_rospec_msg))
            logging.info("✅ ADD_ROSPEC enviado.")

            time.sleep(0.5)

            # ENABLE_ROSPEC
            enable_rospec_msg = build_enable_rospec(123)
            sock.sendall(encode_message(enable_rospec_msg))
            logging.info("✅ ENABLE_ROSPEC enviado.")

            time.sleep(0.5)

            # START_ROSPEC
            start_rospec_msg = build_start_rospec(123)
            sock.sendall(encode_message(start_rospec_msg))
            logging.info("✅ START_ROSPEC enviado.")

            # Leer respuestas
            while True:
                response = sock.recv(4096)
                if not response:
                    break
                logging.info(f"📡 Respuesta recibida: {response.hex()}")

    except Exception as e:
        logging.error(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
