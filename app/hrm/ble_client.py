"""Cliente BLE para el cinturón HRM de Decathlon (perfil estándar HRP).

RF-4.1 Conexión Bluetooth con cinturón HRM (Heart Rate Profile / Heart Rate Service).
RF-4.2 Lectura de bpm en tiempo real.
RF-4.3 Indicador de estado de conexión BLE.
RNF-5  Comunica claramente si el hardware BLE no está disponible.
"""

import asyncio
import logging

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)

HEART_RATE_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HEART_RATE_MEASUREMENT_CHAR_UUID = "00002a37-0000-1000-8000-00805f9b34fb"

SCAN_TIMEOUT_SECONDS = 6.0
RECONNECT_DELAY_SECONDS = 3.0

STATUS_DISCONNECTED = "Desconectado"
STATUS_SCANNING = "Buscando..."
STATUS_CONNECTED = "Conectado"
STATUS_BLE_UNAVAILABLE = "Bluetooth no disponible"


def parse_heart_rate_measurement(data: bytes) -> int | None:
    """Parsea el valor de bpm según el formato estándar Heart Rate
    Measurement de Bluetooth SIG (servicio 0x180D, característica 0x2A37).
    """
    if not data:
        return None
    flags = data[0]
    uint16_format = flags & 0x01
    if uint16_format:
        if len(data) < 3:
            return None
        return int.from_bytes(data[1:3], byteorder="little")
    if len(data) < 2:
        return None
    return data[1]


class HRMClient(QThread):
    """Hilo dedicado con su propio event loop de asyncio para no bloquear
    la interfaz Qt mientras se escanea/conecta/recibe notificaciones BLE.
    """

    status_changed = Signal(str)
    bpm_updated = Signal(int)
    device_found = Signal(str)

    def __init__(self):
        super().__init__()
        self._stop_requested = False
        self._loop: asyncio.AbstractEventLoop | None = None

    def run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main())
        finally:
            self._loop.close()

    def stop(self) -> None:
        self._stop_requested = True
        self.wait(SCAN_TIMEOUT_SECONDS * 1000 + 2000)

    async def _main(self) -> None:
        try:
            await BleakScanner.discover(timeout=0.1)
        except BleakError as exc:
            logger.warning("Adaptador BLE no disponible: %s", exc)
            self.status_changed.emit(STATUS_BLE_UNAVAILABLE)
            return

        while not self._stop_requested:
            self.status_changed.emit(STATUS_SCANNING)
            device = await self._scan_for_hrm()
            if device is None:
                continue
            self.device_found.emit(device.name or device.address)
            connected_cleanly = await self._connect_and_listen(device.address)
            if self._stop_requested:
                break
            self.status_changed.emit(STATUS_DISCONNECTED)
            if not connected_cleanly:
                await asyncio.sleep(RECONNECT_DELAY_SECONDS)

    async def _scan_for_hrm(self):
        try:
            devices = await BleakScanner.discover(
                timeout=SCAN_TIMEOUT_SECONDS, return_adv=True
            )
        except BleakError as exc:
            logger.warning("Error escaneando BLE: %s", exc)
            self.status_changed.emit(STATUS_BLE_UNAVAILABLE)
            await asyncio.sleep(RECONNECT_DELAY_SECONDS)
            return None

        for device, adv in devices.values():
            service_uuids = [u.lower() for u in (adv.service_uuids or [])]
            if HEART_RATE_SERVICE_UUID in service_uuids:
                return device
        return None

    async def _connect_and_listen(self, address: str) -> bool:
        try:
            async with BleakClient(address) as client:
                self.status_changed.emit(STATUS_CONNECTED)

                def _on_notify(_sender, data: bytearray) -> None:
                    bpm = parse_heart_rate_measurement(bytes(data))
                    if bpm is not None:
                        self.bpm_updated.emit(bpm)

                await client.start_notify(HEART_RATE_MEASUREMENT_CHAR_UUID, _on_notify)
                while client.is_connected and not self._stop_requested:
                    await asyncio.sleep(0.5)
                await client.stop_notify(HEART_RATE_MEASUREMENT_CHAR_UUID)
            return True
        except BleakError as exc:
            logger.warning("Error de conexión BLE con %s: %s", address, exc)
            return False
