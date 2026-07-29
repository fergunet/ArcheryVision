# ArcheryVision

App de escritorio para entrenamiento de arquería con vídeo multi-cámara
sincronizado con delay y monitor de frecuencia cardíaca por Bluetooth.

Implementa los requisitos **Must** de `requisitos_app_arquero.md`, más un
módulo de análisis de postura por visión artificial (`requisitos_modulo_vision.md`).

## Instalación y ejecución

### Windows

Doble clic en `Iniciar ArcheryVision.bat`. La primera vez crea el entorno
virtual e instala las dependencias automáticamente; en los siguientes
arranques solo reinstala si `requirements.txt` ha cambiado (por ejemplo,
tras actualizar el proyecto), así que el lanzador siempre queda al día sin
pasos manuales.

### Linux / macOS (o instalación manual)

```bash
python3 -m venv .venv
source .venv/bin/activate   # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Funcionalidad incluida

### Multicámara (pestaña "Multicámara")

- Detección y asignación de hasta 4 cámaras USB, con nombre personalizable por cámara, mostradas en tiempo real (RF-1.1, RF-1.2, RF-1.3).
- Buffer circular por cámara (hasta 60 s) y delay configurable 0-60 s (RF-2.1, RF-2.2).
- Reloj de sincronía único: al pulsar **Play**, todas las vistas se reproducen ancladas al mismo instante, desplazadas por su delay (RF-2.3).
- Ventanas de cámara flotantes, redimensionables (con relación de aspecto preservada) y rotables en pasos de 90° (RF-3.1, RF-3.2, RF-3.3).
- Conexión BLE al cinturón HRM (perfil Heart Rate estándar de Bluetooth SIG, compatible con el HRM Belt de Decathlon), overlay de bpm en pantalla e indicador de estado (RF-4.1, RF-4.2, RF-4.3, RNF-5).
- Botón "Guardar clip" (también en la barra de herramientas superior) que exporta un único vídeo en cuadrícula 2×2 con los últimos X segundos (5-60 s configurables) de las 4 cámaras, respetando delay y rotación, con overlay de fecha/hora y bpm sincronizado quemado en el vídeo y nombre de archivo con timestamp automático (RF-5.1 a RF-5.5).
- Persistencia automática de cámaras asignadas, delays, rotación, nombres, geometría de ventanas y visibilidad del panel de controles entre sesiones (RNF-4).
- Panel de controles ocultable/mostrable desde la barra de herramientas para liberar espacio en pantalla; mensajes de estado (clip guardado, errores) inline bajo el botón en vez de ventanas emergentes; botón para resetear toda la configuración guardada.

### Análisis de postura (pestaña "Análisis de postura")

Implementa `requisitos_modulo_vision.md`: detección de esqueleto en tiempo
real con [MediaPipe Pose](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker)
sobre una única cámara.

- Selección de vista (Trasera / Lateral / Superior) y de mano dominante (diestro/zurdo), cada una con sus propios criterios de ángulos y alineaciones.
- Esqueleto superpuesto en vivo, coloreado en verde/rojo según qué articulaciones incumplen algún criterio, con detalle textual del error en un panel de estado aparte.
- Delay configurable (0-30 s) y recorte final, para revisar la postura en el instante exacto del disparo con el mismo buffer que alimenta la grabación.
- Grabación a vídeo con el esqueleto ya superpuesto, carpeta de salida configurable y nombre con timestamp automático.
- Aviso sonoro opcional (activable/desactivable) al pasar de postura correcta a incorrecta.
- Al cambiar a esta pestaña, la captura del modo Multicámara se pausa por completo (cámaras liberadas, no solo ocultas) para no competir por recursos, y se reanuda automáticamente al volver.
- Todos los ajustes anteriores se persisten entre sesiones igual que en el modo Multicámara.

## Estructura

```
app/
  camera/      detección USB, captura y buffer circular
  config/      persistencia de configuración (QSettings)
  sync/        reloj de sincronía compartido
  ui/          ventana principal (pestañas), vistas de cámara, panel de control, overlay HRM, panel de postura
  hrm/         cliente BLE del pulsómetro e historial de bpm
  recording/   exportador de clips compuestos multicámara
  pose/        detección de pose (MediaPipe), análisis de postura por vista, overlay, hilo de captura y exportación
main.py        punto de entrada
```

## Notas

- Probado en Linux con cámaras virtuales/sin hardware (smoke test). El target de despliegue es Windows 10/11 (RNF-3); requiere un adaptador Bluetooth 4.0+ para el HRM (RNF-5).
- Del documento multicámara, los requisitos **Should**/**Could** de presets de delay, layouts guardables, pantalla completa por doble clic, overlay de timestamp en vivo por ventana, exportación individual por cámara y alertas de color por zona de bpm no están implementados todavía.
- Los umbrales angulares del módulo de postura son heurísticas de una primera versión; conviene afinarlos con vídeo real de tiradores.

## Licencia

Este proyecto se distribuye bajo los términos de la [GNU General Public License v3.0](LICENSE).
