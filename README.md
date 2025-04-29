# RFID WebSocket Server

Este proyecto implementa un servidor WebSocket en Python para conectar y reportar en tiempo real las lecturas de tags RFID usando los arcos de REPUVE.

## Tecnologías utilizadas

- **Python 3.12**
- **Tornado** (Servidor Web y WebSocket)
- **Sllurp** (LLRP para comunicación RFID)
- **httpx** (Cliente HTTP asíncrono)
- **asyncio** (Concurrencia eficiente)

## Funcionalidades principales

- Conexión automática a dispositivos RFID registrados.
- Inicio de inventariado RFID en modo continuo.
- Lectura de datos en el tag (VIN y Folio).
- Envío inmediato de cada lectura válida a API REUVE.
- WebSocket para notificación de lecturas en tiempo real.
- Dashboard web simple para visualizar dispositivos conectados y tags reportados.

## Estructura

- `app.py`: archivo principal que arranca el servidor, maneja la conexión a RFID y el WebSocket.
- `sllurp/`: directorio con el cliente LLRP modificado para conexión directa.

## Requisitos

- Python 3.10+
- Conexión red directa al arco REPUVE (Speedway R420).

Instalar dependencias:
```bash
pip install tornado httpx
```

## Uso

Levanta el servidor local:
```bash
python app.py
```

Accede en el navegador a:
```
http://localhost:8888
```

Conéctate al WebSocket desde tu aplicación en:
```
ws://localhost:8888/wsArcos
```

## Mejoras incluidas

- **Reconexión automática** si el lector RFID se cae.
- **Cerrar conexiones** polite antes de reconectar.
- **Evitar duplicados**: Cada tag solo se reporta una vez.
- **Cierre ordenado** al detener el servidor.
- **Diseño responsivo** de la página web.

## Notas técnicas

- La conexión a cada lector se realiza en **hilos (threading)** para no bloquear el servidor WebSocket.
- La comunicación HTTP hacia la API es totalmente **asíncrona**.
- Se realiza una **prevalidación** de `ReadData` para garantizar datos completos antes de enviarlos.

---

### 🎉 Proyecto desarrollado con pasión para integración RFID en entornos productivos en tiempo real.

