# El frontend de CloudRISK — cómo funciona y por qué

## La idea general

El frontend es una **Single Page Application** (SPA): una sola página web que no recarga nunca. El servidor simplemente entrega un fichero HTML vacío con un bundle de JavaScript, y a partir de ahí React construye todo lo que ve el jugador en el navegador. No hay múltiples páginas HTML — el "cambio de página" lo simula el propio JavaScript.

---

## Las tecnologías y para qué sirve cada una

**React 18** es el corazón. Es la librería que decide qué se pinta en pantalla y cuándo actualizarlo. Cuando cambia el estado del juego (te conquistan una zona, empieza una batalla), React detecta el cambio y redibuja solo las partes afectadas, sin refrescar la página entera.

**Vite** es la herramienta que durante el desarrollo sirve el código al navegador instantáneamente, y en producción lo empaqueta todo en un único fichero JavaScript optimizado. Es lo que se ejecuta con `npm run dev`.

**React Router** gestiona las dos "páginas" de la app: `/` que es el juego, y `/analytics` que es el dashboard de datos. Cuando escribes `/analytics` en la URL, React Router simplemente le dice a React que muestre un componente diferente — sin hacer ninguna petición al servidor.

**MapLibre GL** dibuja el mapa interactivo de Valencia. Es la alternativa open-source a Mapbox (sin necesidad de API key de pago). El mapa no es una imagen estática — es un canvas WebGL que renderiza capas vectoriales encima de las teselas del mapa base. Las zonas de juego son polígonos GeoJSON que se superponen sobre el mapa real.

**TailwindCSS** es el sistema de estilos. En lugar de escribir CSS en ficheros separados, los estilos se escriben directamente en el HTML como clases (`rounded-2xl`, `backdrop-blur-xl`, `text-white/60`). Esto hace que el aspecto táctico/oscuro sea consistente en toda la app sin duplicar CSS.

**Framer Motion** añade las animaciones: el panel de zona que sube desde abajo, los dados rodando en la batalla, la animación del cofre de recompensa al conquistar. Sin esta librería todo aparecería y desaparecería de golpe.

**Axios** es el cliente HTTP que hace las llamadas al backend (desplegar tropas, atacar, consultar zonas). Tiene un interceptor configurado: si el backend devuelve un 401 (token expirado o inválido), automáticamente cierra la sesión y recarga la página.

---

## Cómo entra el jugador — el auto-login

No hay pantalla de login. Al arrancar la app, `AuthContext.jsx` mira la URL: si tienes `?player=sur` entra como Sur, si no hay nada entra como Norte por defecto. Con esas credenciales hace login automáticamente contra el backend y guarda el token JWT en `localStorage`. Si recargas la página y el token sigue siendo válido, lo reutiliza directamente sin volver a hacer login.

Esto permite que en una demo haya cuatro jugadores abiertos en cuatro navegadores distintos, cada uno con su URL, sin necesidad de formularios.

---

## El mapa — cómo sabe qué zonas pintar de qué color

Al arrancar, el mapa carga dos ficheros GeoJSON que están en la carpeta `public/`: uno con los 57 distritos de Valencia como polígonos y otro con los distritos de contexto. Estos ficheros son estáticos — definen la geometría de las zonas pero no quién las controla.

Paralelamente, el frontend consulta al backend `/api/v1/zones/` para saber el estado actual del juego: quién controla cada zona, cuántas tropas hay, si hay batalla activa. Cruza esa información con el GeoJSON y le asigna a cada polígono su color de facción. MapLibre renderiza los polígonos con ese color usando expresiones de paint, que son básicamente fórmulas que MapLibre evalúa por cada feature del mapa.

---

## El tiempo real — WebSocket y polling

Hay dos mecanismos de actualización:

El **WebSocket** (`useWebSocket.js`) mantiene una conexión permanente abierta con el backend. Cuando ocurre algo relevante (alguien conquista una zona, empieza una batalla), el backend empuja el evento a todos los jugadores conectados sin que estos tengan que preguntar. Si la conexión cae, el hook reintenta automáticamente con un backoff exponencial (espera 1s, luego 2s, luego 4s... hasta 30s máximo). También envía un ping cada 25 segundos para que Cloud Run no cierre la conexión por inactividad.

El **polling de turno** es un singleton que consulta `/api/v1/turn/` cada 3 segundos para saber de quién es el turno activo. Se llama singleton porque antes cada componente que necesitaba saber el turno hacía su propia petición — había 4 peticiones paralelas cada 3 segundos. Ahora hay una sola que distribuye el resultado a todos los componentes suscritos.

---

## La página de analytics

La ruta `/analytics` es independiente del juego. Muestra datos históricos que vienen de un pipeline de datos: Dataflow procesa los pasos de los jugadores y los almacena en BigQuery. El frontend consulta endpoints específicos del backend que a su vez leen BigQuery, y muestra tablas con cosas como los jugadores más activos en días lluviosos o los pasos rechazados por el sistema anti-trampas. Si el pipeline todavía no ha corrido y BigQuery está vacío, las tablas muestran un mensaje explicativo en lugar de petarse.

---

## Cómo llega a producción

El build es un Docker multi-stage: primero un contenedor con Node 20 compila el proyecto con Vite y genera los ficheros estáticos en `dist/`. Luego un segundo contenedor con nginx (mucho más ligero) coge esos ficheros y los sirve. El contenedor de Node no llega a producción. Terraform despliega ese contenedor en Cloud Run y le asigna una URL pública. Las URLs del backend se hornean dentro del bundle JavaScript en tiempo de build — no se pueden cambiar en runtime sin recompilar.
