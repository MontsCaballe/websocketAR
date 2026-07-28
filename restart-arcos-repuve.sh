#!/bin/bash
#
# Script para reiniciar el servicio arcos-repuve.service cada 6 horas
# Ubicación: /usr/local/bin/restart-arcos-repuve.sh
#

SERVICE_NAME="arcos-repuve.service"
LOG_FILE="/var/log/arcos-repuve/restart.log"
MAX_STOP_TIME=30

# Función para logging
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Función para verificar estado del servicio
check_service_status() {
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        return 0  # Activo
    else
        return 1  # Inactivo
    fi
}

# Función para obtener PID del servicio
get_service_pid() {
    systemctl show --property MainPID --value "$SERVICE_NAME"
}

# Inicio del script
log_message "=== INICIANDO REINICIO PROGRAMADO DE $SERVICE_NAME ==="

# Verificar estado inicial
if check_service_status; then
    INITIAL_PID=$(get_service_pid)
    log_message "Servicio actualmente activo con PID: $INITIAL_PID"
else
    log_message "ADVERTENCIA: Servicio no está activo antes del reinicio"
fi

# Reiniciar el servicio
log_message "Ejecutando: systemctl restart $SERVICE_NAME"
if systemctl restart "$SERVICE_NAME"; then
    log_message "Comando restart ejecutado exitosamente"
else
    log_message "ERROR: Fallo el comando restart"
    exit 1
fi

# Esperar un momento para que se inicie
sleep 5

# Verificar que el servicio esté activo
RETRY_COUNT=0
MAX_RETRIES=6

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if check_service_status; then
        NEW_PID=$(get_service_pid)
        log_message "✅ Servicio reiniciado exitosamente con nuevo PID: $NEW_PID"
        
        # Mostrar estado del servicio
        log_message "Estado del servicio:"
        systemctl status "$SERVICE_NAME" --no-pager -l | tee -a "$LOG_FILE"
        
        # Mostrar información de memoria y CPU
        if [ "$NEW_PID" != "0" ] && [ "$NEW_PID" != "" ]; then
            log_message "Información del proceso:"
            ps -p "$NEW_PID" -o pid,ppid,cmd,%mem,%cpu,etime | tee -a "$LOG_FILE"
        fi
        
        log_message "=== REINICIO COMPLETADO EXITOSAMENTE ==="
        exit 0
    else
        RETRY_COUNT=$((RETRY_COUNT + 1))
        log_message "Intento $RETRY_COUNT/$MAX_RETRIES: Servicio aún no está activo, esperando 5 segundos..."
        sleep 5
    fi
done

# Si llegamos aquí, el servicio no se pudo iniciar
log_message "❌ ERROR: Servicio no se pudo iniciar después de $MAX_RETRIES intentos"
log_message "Estado actual del servicio:"
systemctl status "$SERVICE_NAME" --no-pager -l | tee -a "$LOG_FILE"

# Mostrar logs recientes del servicio para debugging
log_message "Últimas 20 líneas del log del servicio:"
journalctl -u "$SERVICE_NAME" -n 20 --no-pager | tee -a "$LOG_FILE"

log_message "=== REINICIO FALLÓ ==="
exit 1