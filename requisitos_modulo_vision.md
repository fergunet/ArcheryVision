# Requisitos – App de Análisis de Postura de Arquería mediante Webcam

## 1\. Objetivo

Desarrollar un módulo para la aplicación ArcheryVision que, a partir del vídeo captado por una webcam en tiempo real, detecte el esqueleto del arquero y evalúe si su postura de tiro es correcta según la vista de cámara seleccionada (frontal, superior o lateral), mostrando avisos visuales cuando detecte errores de posición (no de movimiento).

## 2\. Alcance

- La app analiza **una única vista a la vez** (frontal, superior o lateral), seleccionada por el usuario mediante un menú antes de iniciar el análisis.  
- No se requiere análisis simultáneo multi-cámara ni fusión de vistas.  
- Uso pensado para entrenamiento individual (club de tiro, autoentrenamiento, entrenador revisando alumnos).

## 3\. Requisitos funcionales

### 3.1 Selección de vista de cámara

- Menú desplegable / botones para elegir: **Frontal**, **Superior**, **Lateral**.  
- La lógica de análisis de postura cambia según la vista elegida (los criterios y los puntos del esqueleto relevantes son distintos en cada caso).  
- Debe poder cambiarse de vista sin reiniciar la aplicación completa.

### 3.2 Captura y visualización en tiempo real

- Captura del stream de la webcam (resolución configurable, por defecto 640×480 o 720p para mantener buen rendimiento).  
- Visualización del vídeo en vivo con el **esqueleto superpuesto** (puntos articulares \+ líneas de unión) sobre la imagen del arquero.  
- Frecuencia objetivo: mínimo 15–20 FPS en un equipo modesto (sin GPU dedicada).

### 3.3 Avisos visuales de postura

- Cuando la postura sea correcta: esqueleto en color "OK" (p. ej. verde) y/o mensaje en pantalla ("Postura correcta").  
- Cuando la postura sea incorrecta:  
  - Cambio de color del esqueleto o de las articulaciones implicadas (p. ej. rojo/naranja).  
  - Texto en pantalla indicando qué está mal (p. ej. "Codo del brazo del arco bloqueado", "Hombros no alineados").  
  - Opcional: aviso sonoro simple (bip) además del visual.  
- Los criterios de "correcto/incorrecto" deben basarse en ángulos y alineaciones entre articulaciones (ver sección 6).

### 3.4 Delay / retardo configurable

- Posibilidad de introducir un **retardo de hasta 30 segundos** entre la captura y la visualización.  
- Uso previsto: el arquero dispara, se aleja o mira la pantalla, y puede revisar su postura en el momento exacto del disparo con margen de tiempo.  
- El delay se gestiona mediante un buffer circular de fotogramas en memoria como en el módulo multicámara de la aplicación (ver sección 5).  
- Control deslizante o campo numérico para ajustar el delay (0–30 s) y segundos a recortar del final.

### 3.5 Grabación de vídeo

- Botón de **Grabar.**  
- Al grabar, se guarda el vídeo con el esqueleto superpuesto (o, opcionalmente, el vídeo original \+ un archivo aparte con los datos de pose).  
- Formato de salida recomendado: MP4 (códec H.264 si está disponible, o MJPG como alternativa ligera).  
- Nombre de archivo con fecha/hora automática, guardado en carpeta configurable (igual que en el modo multicámara).

### 3.6 Interfaz de usuario

- Ventana principal del módulo con:  
  - Vista de cámara en vivo (con esqueleto).  
  - Menú de selección de vista (frontal/superior/lateral).  
  - Selección de la cámara a usar (lista desplegable)  
  - Control de delay.  
  - Botón de grabación  
  - Panel de estado de la postura (correcta / incorrecta \+ detalle del error).  
- Interfaz simple, sin necesidad de conexión a internet ni cuentas de usuario.

## 4\. Requisitos no funcionales

- **Bajo consumo de recursos**: debe funcionar en tiempo real en un portátil sin GPU dedicada (CPU de gama media).  
- **Sin dependencia de servicios en la nube**: todo el procesamiento debe ser local (privacidad y velocidad).  
- **Multiplataforma**: preferiblemente compatible con Windows, macOS y Linux.  
- **Instalación sencilla**: dependencias instalables vía `pip`, sin compilación compleja.  
- **Robustez**: debe tolerar pérdida temporal de detección (p. ej. si el arquero sale parcialmente de cuadro) sin bloquear la app.

## 5\. Propuesta de arquitectura técnica (Python)

| Componente | Librería sugerida | Motivo |
| :---- | :---- | :---- |
| Captura de vídeo | `OpenCV` (`cv2.VideoCapture`) | Estándar, ligero, control total sobre FPS/resolución |
| Detección de esqueleto/pose | `MediaPipe Pose` (Google) | Muy ligero, funciona en CPU en tiempo real, 33 puntos corporales, ideal para este caso frente a alternativas como OpenPose (mucho más pesado) |
| Interfaz gráfica | `PyQt5`/`PySide6` o `Tkinter` (más ligero) | Permite menú, botones y controles fácilmente |
| Buffer de delay | Cola (`collections.deque`) con marca de tiempo, gestionada en un hilo separado | Bajo coste de memoria, permite hasta 30 s de buffer sin saturar RAM (a 720p y 15-20 FPS es asumible) |
| Grabación | `cv2.VideoWriter` | Integración directa con los frames ya procesados |
| Cálculo de ángulos/criterios | `NumPy` | Cálculos vectoriales simples entre landmarks |

### Notas de rendimiento

- MediaPipe Pose en modo "lite" o "full" (no "heavy") es suficiente y muy eficiente en CPU.  
- El buffer de 30 s debe implementarse con frames posiblemente redimensionados/comprimidos en memoria para no disparar el uso de RAM (a 720p, 30 s a 20 FPS ≈ 600 frames; conviene usar JPEG en memoria o reducir resolución del buffer si se detecta poca RAM).  
- Procesar la detección de pose en un hilo y la UI en otro evita bloqueos de la interfaz.

## 6\. Criterios de análisis según la vista 

Cada vista usa un subconjunto de los 33 landmarks de MediaPipe (hombros, codos, muñecas, caderas, orejas/nariz) y calcula ángulos entre ellos. La forma de tirar es la seguida por KSL International (apertura angular, no lineal).

Las piernas podrían verse cortadas fuera de cámara, pero debería detectarse el resto del cuerpo desde la cadera.

### 6.1 Vista trasera (la cámara apunta a la diana)

- **Verticalidad de columna**: la espalda no debe inclinarse hacia delante ni hacia atrás más de unos 5–10°.  
- **Pecho cerrado y bajo,** manteniendo firme el core.


### 6.2 Vista lateral (la cámara apunta al pecho del arquero)

- **Forma en "T"**: brazos formando una línea recta a la altura de los hombros, perpendicular a la columna.  
- **Hombros nivelados**: la línea entre ambos hombros debe ser aproximadamente horizontal (tolerancia ±3–5°).  
- **Alineación hombro–codo–flecha**: el codo del brazo de tracción debe estar aproximadamente a la misma altura que la flecha/hombro o ligeramente por encima.  
- **Codo de tracción en línea con la flecha**: en el anclaje, el codo debe quedar en línea o ligeramente por encima de la flecha.  
- **Pecho cerrado y bajo,** manteniendo firme el core.

### 6.3 Vista superior (desde arriba)

- **Alineación hombros–línea de tiro**: ambos hombros deben quedar alineados con la dirección al blanco.  
- **Alineación del codo de tracción con la flecha**: El codo de tracción debe estar siempre alineado con la flecha o un poco por detrás de esa línea.  
- La alineación de hombros-línea de tiro y la alineación del codo con la flecha forman un triángulo lo más cerrado posible

## 7\. Criterios generales de una postura de tiro con arco correcta

Estos son los fundamentos técnicos (independientes del software) que la app debe usar como referencia para clasificar una postura como correcta:

1. **Alineación  hombros**:  hombros alineados con la línea de tiro (hacia el blanco),   
2. **Brazo del arco (brazo que sostiene el arco)**: extendido ligeramente flexionado o pronado contrayendo el tríceps,  
3. **Hombros nivelados y bajos**: ambos hombros a la misma altura y alejados de las orejas.  
4. **Pecho cerrado y bajo,** manteniendo firme el core.  
5. **Forma en "T"**: en el momento del anclaje, los brazos y la línea de hombros deben formar una "T" con la columna vertebral.  
6. **Anclaje consistente**: la mano de tracción llega siempre al mismo punto de referencia en la cara, de forma repetible disparo tras disparo.  
7. **Codo de tracción alineado**: a la altura de la flecha, en línea con esta o ligeramente por encima.  
8. **Cabeza y visión**: cabeza erguida, mirada hacia el blanco   
9. **Columna vertical**: sin inclinarse hacia delante, atrás o hacia los lados durante el tiro.

Una postura se considera **incorrecta** cuando la app detecta desviaciones significativas en uno o más de estos puntos según los ángulos definidos en la sección 6 (por ejemplo: hombro elevado, codo del brazo del arco bloqueado en exceso o muy flexionado, columna inclinada más allá del umbral, codo de tracción caído, etc.).

## 8\. Posibles mejoras futuras (fuera de alcance inicial)

- Histórico de sesiones y estadísticas de consistencia del anclaje.  
- Comparación entre disparos (superposición de esqueletos de distintos intentos).  
- Exportar informe en PDF con capturas de los errores detectados.  
- Soporte multi-arquero en la misma escena.

