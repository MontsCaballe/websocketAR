import requests
import logging

def obtener_arcos():
    try:
        # URLs de la API
        URL_ARCOS = "https://apirepuve.minayarit.gob.mx/recaudacion/arcos-repuve/"
        URL_ANTENAS = "https://apirepuve.minayarit.gob.mx/recaudacion/antenas-repuve/"

        arcos_resp = requests.get(URL_ARCOS, timeout=5)
        antenas_resp = requests.get(URL_ANTENAS, timeout=5)

        arcos_resp.raise_for_status()
        antenas_resp.raise_for_status()

        arcos_data = arcos_resp.json()
        antenas_data = antenas_resp.json()

        logging.info("✅ Arcos Obtenidos")
        # logging.info(arcos_data)

        logging.info("✅ Antenas Obtenidas")
        # logging.info(antenas_data)

        # Crear diccionario con arcos
        arcos = {}
        for arco in arcos_data:
            arcos[arco["id"]] = {
                "nombre": arco["nombre"],
                "ip": arco["ip"],
                "estado": "conectado" if arco["estatus"] == "1" else "desconectado",
                "antenas": []
            }

        # Agregar antenas al arco correspondiente
        for antena in antenas_data:
            arco_id = antena.get("arcos")
            if arco_id in arcos:
                arcos[arco_id]["antenas"].append(antena["id"])

        # Convertir a lista para el frontend
        resultado = []
        for arco in arcos.values():
            resultado.append({
                "nombre": arco["nombre"],
                "ip": arco["ip"],
                "estado": arco["estado"],
                "antenas": arco["antenas"],
                "imagen": "/static/arcos/arco.png"  # Imagen por default
            })
        logging.info("✅ Arcos Obtenidos")
        # 🛠️ Después de construir arcos_con_antenas
        resultado.append({
            "nombre": "ARCO DE Mon",
            "ip": "192.168.1.20",
            "estado": "conectado",  # Puedes poner "desconectado" si quieres que inicie en rojo
            "antenas": [1],  # Fake antena
            "imagen": "./static/arcos/arco.png"
        })
        # logging.info(resultado)

        return resultado

    except Exception as e:
        logging.error(f"❌ Error al obtener arcos: {e}")
        logging.warning("⚠️ No se pudieron obtener arcos desde la API. Usando datos fake.")
        # Datos de ejemplo si la API falla
        return [
            {
                "nombre": "Arco Demo",
                "ip": "192.168.1.20",
                "estado": "conectado",
                "antenas": [1],
                "imagen": "/static/arcos/arco.png"
            }
        ]
