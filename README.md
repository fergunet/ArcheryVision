# ArcheryVision

App de escritorio para entrenamiento de arquería con vídeo multi-cámara
sincronizado con delay y monitor de frecuencia cardíaca por Bluetooth.

Implementa los requisitos **Must** de `requisitos_app_arquero.md`.

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate   # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecución

```bash
python main.py
```

## Funcionalidad incluida

- Detección y asignación de hasta 4 cámaras USB, mostradas en tiempo real (RF-1.1, RF-1.2).
- Buffer circular por cámara (hasta 60 s) y delay configurable 0-60 s (RF-2.1, RF-2.2).
- Reloj de sincronía único: al pulsar **Play**, todas las vistas se reproducen ancladas al mismo instante, desplazadas por su delay (RF-2.3).
- Ventanas de cámara flotantes, redimensionables (con relación de aspecto preservada) y rotables en pasos de 90° (RF-3.1, RF-3.2, RF-3.3).
- Conexión BLE al cinturón HRM (perfil Heart Rate estándar de Bluetooth SIG, compatible con el HRM Belt de Decathlon), overlay de bpm en pantalla e indicador de estado (RF-4.1, RF-4.2, RF-4.3, RNF-5).
- Botón "Guardar clip" que exporta un único vídeo en cuadrícula 2×2 con los últimos X segundos (5-60 s configurables) de las 4 cámaras, respetando delay y rotación (RF-5.1, RF-5.2, RF-5.3).

## Estructura

```
app/
  camera/      detección USB, captura y buffer circular
  sync/        reloj de sincronía compartido
  ui/          ventana principal, vistas de cámara, panel de control, overlay HRM
  hrm/         cliente BLE del pulsómetro
  recording/   exportador de clips compuestos
main.py        punto de entrada
```

## Notas

- Probado en Linux con cámaras virtuales/sin hardware (smoke test). El target de despliegue es Windows 10/11 (RNF-3); requiere un adaptador Bluetooth 4.0+ para el HRM (RNF-5).
- Los requisitos **Should**/**Could** (etiquetado de cámaras, presets de delay, layouts guardables, persistencia de configuración, pantalla completa por doble clic, overlay de timestamp, exportación individual por cámara) no están implementados en esta primera versión.
