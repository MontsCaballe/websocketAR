# 📁 utils/parser.py
import logging

def parse_user_memory(raw_bytes):
    try:
        if not raw_bytes or len(raw_bytes) < 25:
            return None
        vin_start = 8
        vin_end = vin_start + 17
        vin_bytes = raw_bytes[vin_start:vin_end]
        vin = vin_bytes.decode('ascii', errors='ignore').strip()
        return vin
    except Exception as e:
        logging.error(f"❌ Error parseando memoria: {e}")
        return None

def parse_epc_folio(epc_bytes):
    try:
        hex_string = epc_bytes.decode('ascii', errors='ignore')
        ascii_bytes = bytes.fromhex(hex_string)
        folio = ascii_bytes.decode('ascii', errors='ignore').strip()
        return folio
    except Exception as e:
        logging.error(f"❌ Error al parsear EPC: {e}")
        return None