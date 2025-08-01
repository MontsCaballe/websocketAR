import time
import logging
import requests

ARCO_API_URL = 'https://apirepuve.minayarit.gob.mx/recaudacion/arcos-repuve/'
ANTENA_API_URL = 'https://apirepuve.minayarit.gob.mx/recaudacion/antenas-repuve/'

# Intervalo para reconsultar las APIs (segundos)
FETCH_INTERVAL = 30

def fetch_arcos_and_antenas():
    try:
        logging.info("🌐 Consultando API de arcos y antenas...")
        arcos_resp = requests.get(ARCO_API_URL, timeout=10)
        antenas_resp = requests.get(ANTENA_API_URL, timeout=10)

        if arcos_resp.status_code == 200 and antenas_resp.status_code == 200:
            arcos = arcos_resp.json()
            antenas = antenas_resp.json()

            # Combinar arcos con sus antenas
            for arco in arcos:
                arco['antenas'] = [
                    antena['id'] for antena in antenas if antena['arcos'] == arco['id']
                ]
                arco['imagen'] = '../static/arcos/arco.png'
                arco['estado'] = 'conectado' if arco['estatus'] == "1" else 'desconectado'

            # Agregar arquito de pruebas (si no está ya)
            arcos = []
            # if not any(a['ip'] == '192.168.1.20' for a in arcos):
            #     arcos.append({
            #         "id":6,
            #         "nombre": "ARCO PRUEBAS LOCAL",
            #         "ip": "192.168.1.20",
            #         "estado": "conectado",
            #         "antenas": [1],
            #         "imagen": "../static/arcos/arco.png"
            #     })
            #     logging.info("🧪 Agregado arco de pruebas 192.168.1.20")
            if not any(a['ip'] == '172.17.50.107' for a in arcos):
                arcos.append({
                    "id":7,
                    "nombre": "ARCO PRUEBAS LOCAL",
                    "ip": "172.17.50.107",
                    "estado": "conectado",
                    "antenas": [1,2],
                    "imagen": "../static/arcos/arco.png"
                })
                logging.info("🧪 Agregado arco de pruebas 172.17.50.107")
            if not any(a['ip'] == '172.17.1.110' for a in arcos):
                arcos.append({
                    "id":7,
                    "nombre": "ARCO PRUEBAS LOCAL",
                    "ip": "172.17.1.110",
                    "estado": "conectado",
                    "antenas": [1,2],
                    "imagen": "../static/arcos/arco.png"
                })
                logging.info("🧪 Agregado arco de pruebas 172.17.1.110")

            return arcos

        else:
            logging.error(f"❌ Error al consultar APIs: Arcos {arcos_resp.status_code}, Antenas {antenas_resp.status_code}")
            return []

    except Exception as e:
        logging.error(f"❌ Error al consultar APIs: {e}")
        return []

def fetch_arcos_periodically():
    """
    Generador que actualiza la lista de arcos cada FETCH_INTERVAL segundos
    """
    while True:
        arcos = fetch_arcos_and_antenas()
        if arcos:
            logging.info(f"✅ {len(arcos)} arcos obtenidos de API")
            yield arcos
        else:
            logging.warning("⚠️ No se pudieron obtener arcos, reintentando en breve...")

        time.sleep(FETCH_INTERVAL)
