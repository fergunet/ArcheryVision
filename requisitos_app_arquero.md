# Requisitos — App de vídeo multi-cámara para arquería

## Leyenda de prioridad

| Etiqueta | Significado |
|----------|-------------|
| **Must** | Obligatorio para la primera versión |
| **Should** | Muy recomendado, incluir si es posible |
| **Could** | Opcional / mejora futura |

---

## RF1 — Gestión de cámaras

| ID | Requisito | Prioridad |
|----|-----------|-----------|
| RF-1.1 | **Detección y conexión de cámaras USB.** La app detecta automáticamente hasta 4 cámaras USB conectadas al sistema y permite seleccionar cuál asignar a cada slot de vista. | Must |
| RF-1.2 | **Visualización simultánea de 4 streams.** Las 4 cámaras se muestran en tiempo real al mismo tiempo, con latencia de captura lo más baja posible. | Must |
| RF-1.3 | **Etiquetado de cámara por posición.** El usuario puede nombrar cada cámara (ej. "Lateral izquierdo", "Frontal", "Trasera") para identificarlas rápidamente. | Should |

---

## RF2 — Sistema de delay sincronizado

| ID | Requisito | Prioridad |
|----|-----------|-----------|
| RF-2.1 | **Buffer de vídeo por cámara.** La app mantiene un buffer circular en memoria para cada cámara. El tamaño mínimo debe cubrir el delay máximo configurable (ej. 60 s). | Must |
| RF-2.2 | **Delay configurable por cámara.** Cada cámara tiene un slider o campo numérico para asignar un delay individual en segundos (rango mínimo: 0–60 s, resolución de 1 s). | Must |
| RF-2.3 | **Sincronización por instante inicial común.** Al pulsar "Play", todas las cámaras comienzan a reproducirse desde el mismo instante de captura pero desplazadas cada una por su delay configurado. El reloj de sincronía es único y compartido entre todos los streams. | Must |
| RF-2.4 | **Indicador de tiempo en cada ventana.** Cada vista muestra en overlay el timestamp del fotograma que se está reproduciendo actualmente. | Should |
| RF-2.5 | **Presets de configuración de delays.** El usuario puede guardar y cargar conjuntos de delays (ej. "Sesión tiro recurvo 10/15/20/25 s") para reutilizarlos entre sesiones. | Could |

---

## RF3 — Gestión de ventanas

| ID | Requisito | Prioridad |
|----|-----------|-----------|
| RF-3.1 | **Ventanas flotantes y arrastrables.** Cada cámara se renderiza en una ventana independiente que el usuario puede mover libremente dentro del área de trabajo con arrastrar y soltar. | Must |
| RF-3.2 | **Redimensionado de ventanas.** Las ventanas son redimensionables por los bordes y esquinas, manteniendo la relación de aspecto del stream de vídeo. | Must |
| RF-3.3 | **Rotación de ventanas.** Cada ventana de vídeo puede rotarse en incrementos de 90° (0°, 90°, 180°, 270°) para adaptarse a la orientación física de la cámara. | Must |
| RF-3.4 | **Layouts predefinidos.** Botones de layout rápido: cuadrícula 2×2, vista principal + 3 miniaturas (modo PiP), o una sola cámara a pantalla completa. El usuario puede guardar su propia disposición. | Should |
| RF-3.5 | **Ventana a pantalla completa por doble clic.** Al hacer doble clic sobre una ventana, esta ocupa toda la pantalla. Un segundo doble clic restaura el tamaño anterior. | Could |

---

## RF4 — Monitor de frecuencia cardíaca (HRM)

| ID | Requisito | Prioridad |
|----|-----------|-----------|
| RF-4.1 | **Conexión Bluetooth con cinturón HRM de Decathlon.** La app se conecta mediante BLE (Bluetooth Low Energy) al dispositivo HRM Belt de Decathlon, que implementa el perfil estándar Heart Rate Profile (HRP) de Bluetooth SIG. | Must |
| RF-4.2 | **Lectura y visualización de pulsaciones en pantalla.** Las pulsaciones por minuto (bpm) se muestran en tiempo real en un overlay permanente visible sobre el área de trabajo (ej. esquina superior de la interfaz). | Must |
| RF-4.3 | **Indicador de estado de conexión BLE.** La interfaz muestra claramente si el dispositivo HRM está conectado, buscando o desconectado. | Must |
| RF-4.4 | **Registro de pulsaciones durante la sesión.** Las pulsaciones se registran con timestamp junto con la sesión de vídeo, de forma que puedan revisarse después en sincronía con las repeticiones. | Should |
| RF-4.5 | **Alertas visuales por zonas de frecuencia cardíaca.** El overlay de bpm cambia de color según rangos configurables (ej. verde / amarillo / rojo) para que el entrenador detecte de un vistazo el estado del arquero. | Could |

---

## RF5 — Grabación de clips

| ID | Requisito | Prioridad |
|----|-----------|-----------|
| RF-5.1 | **Botón de guardar clip.** La interfaz dispone de un botón prominente ("Guardar clip" o similar) que, al pulsarse, exporta a disco los últimos X segundos del buffer de todas las cámaras activas de forma simultánea. | Must |
| RF-5.2 | **Duración de clip configurable.** El valor X (segundos hacia atrás que se capturan al pulsar el botón) es configurable por el usuario en los ajustes, con un rango razonable de 5–60 s. | Must |
| RF-5.3 | **Clip compuesto con todas las cámaras.** El archivo exportado es un único vídeo con las 4 vistas dispuestas en cuadrícula (layout 2×2), respetando los delays y rotaciones aplicadas a cada ventana en el momento de la grabación. | Must |
| RF-5.4 | **Inclusión de overlay de pulsaciones en el clip.** Si el dispositivo HRM está conectado, las pulsaciones del momento quedan grabadas en el clip exportado como overlay, igual que se muestran en pantalla. | Should |
| RF-5.5 | **Nombre de archivo automático con timestamp.** El clip se guarda con un nombre generado automáticamente que incluye fecha y hora (ej. `clip_20260622_183045.mp4`) en una carpeta de salida configurable. | Should |
| RF-5.6 | **Exportación individual por cámara.** Opcionalmente, además del clip compuesto, el usuario puede elegir exportar también los 4 vídeos por separado en ficheros individuales. | Could |

---

## RNF — Requisitos no funcionales

| ID | Requisito | Prioridad |
|----|-----------|-----------|
| RNF-1 | **Rendimiento.** La app debe sostener 4 streams simultáneos a ≥30 fps con resolución mínima 720p sin degradación perceptible del sistema. | Must |
| RNF-2 | **Sincronía de reloj orientativa.** Una desviación entre streams de hasta ±100 ms es aceptable. No se requieren mecanismos de corrección activa del reloj; un reloj software compartido (`time.time()` o equivalente) es suficiente. | Should |
| RNF-3 | **Plataforma objetivo.** Aplicación de escritorio nativa para Windows 10/11. Soporte macOS considerado en una segunda fase. | Should |
| RNF-4 | **Persistencia de configuración.** Los delays, nombres de cámara, rotación y posición/tamaño de ventanas se guardan automáticamente y se restauran al volver a abrir la app. | Should |
| RNF-5 | **Compatibilidad BLE.** El sistema anfitrión debe contar con adaptador Bluetooth 4.0 o superior. La app comunica claramente si el hardware BLE no está disponible. | Must |
