# Apis de calidad del aire y del tiempo

Sirven como multiplicador de puntos, envian en tiempo real y en base a unas reglas el factor multiplicador. 

## 1. Índice de Calidad del Aire (air_quality)
Este índice se deriva del AQI (Air Quality Index) proporcionado por OpenWeatherMap. El objetivo es asignar un valor mayor a 1 cuando el aire es saludable y un valor menor a 1 cuando la calidad es deficiente.

Rango del parámetro: 0.6 (Muy mala) a 1.5 (Muy buena).

Fórmula: 

P=1.5−(AQI−1)⋅0.225

Interpretación:

- AQI 1 (Muy bueno): P=1.5
- AQI 3 (Moderado): P=1.05
- AQI 5 (Muy malo): P=0.6

## 2. Índice de Meteorología (weather_condition)
Este índice evalúa el estado del tiempo para determinar si las condiciones son favorables. Considera tanto el estado del cielo como temperaturas extremas.

Rango del parámetro: 0.6 (Adverso) a 1.5 (Óptimo).

Lógica de Asignación:

- Despejado (Clear): 1.5 (Máxima puntuación).
- Nublado/Llovizna: 1.2.
- Lluvia: 0.8.
- Tormenta/Nieve: 0.6 (Penalización máxima).

Ajuste de Temperatura: Si la temperatura es extrema (>35ºC o <5º C), se aplica una penalización de −0.2 sobre el índice calculado, garantizando siempre que el valor final se mantenga dentro del rango [0.6,1.5].


