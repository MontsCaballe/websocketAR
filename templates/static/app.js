let ws = new WebSocket("ws://" + window.location.host + "/ws");

ws.onopen = () => {
    document.getElementById("status").innerText = "🟢 Conectado";
};

ws.onmessage = (event) => {
    let lectura = JSON.parse(event.data);
    let li = document.createElement("li");
    li.textContent = `Folio: ${lectura.folio} | VIN: ${lectura.vin} | ${lectura.timestamp}`;
    document.getElementById("lecturas").prepend(li);
};

ws.onclose = () => {
    document.getElementById("status").innerText = "🔴 Desconectado";
};
