import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions

# 1. Simulación de datos con los nuevos campos de clima y aire del chat
mensajes_simulados = [
    {
        "player_id": "jugador_1", 
        "tile_id": "Ruzafa", 
        "steps": 1200, 
        "air_multiplier": 1.2, # Calidad buena
        "weather_penalty": 0.2, # Penalización por calor/frío
        "timestamp": "2026-04-05T21:30:00"
    },
    {
        "player_id": "jugador_2", 
        "tile_id": "Patraix", 
        "steps": 5000, 
        "air_multiplier": 0.8, # Calidad regular
        "weather_penalty": 0.0, # Sin penalización
        "timestamp": "2026-04-05T21:45:00"
    }
]

# 2. Lógica de Negocio: Cálculo de ejércitos con multiplicadores
class CalcularEjercitosDoFn(beam.DoFn):
    def process(self, element):
        pasos = element["steps"]
        # Aplicamos la fórmula: (pasos/100) * (aire - clima)
        factor_final = element["air_multiplier"] - element["weather_penalty"]
        ejercitos_ganados = int((pasos // 100) * factor_final)
        
        element["ejercitos_ganados"] = ejercitos_ganados
        yield element

# 3. Escritura en BigQuery (Histórico de logs)
# Nota: En Dataflow se usa el conector nativo beam.io.WriteToBigQuery
def escribir_a_bigquery(pipeline):
    return (
        pipeline 
        | "WriteToBQ" >> beam.io.WriteToBigQuery(
            table='tu-proyecto:risk_dataset.historial_pasos',
            schema='player_id:STRING, tile_id:STRING, steps:INTEGER, ejercitos_ganados:INTEGER, timestamp:TIMESTAMP',
            create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
            write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND
        )
    )

# 4. Escritura en Firestore (Estado en vivo / Upsert)
class WriteToFirestoreDoFn(beam.DoFn):
    def process(self, element):
        # Aquí iría la lógica de la SDK de Google Cloud Firestore
        # Se haría un update del balance del usuario y del mapa
        print(f"[FIRESTORE UPSERT] Actualizando balance de {element['player_id']}...")
        yield element

# --- PIPELINE PRINCIPAL ---
if __name__ == "__main__":
    options = PipelineOptions()
    with beam.Pipeline(options=options) as p:
        
        # Ingesta y Procesamiento
        eventos_procesados = (
            p 
            | "Leer Datos" >> beam.Create(mensajes_simulados)
            | "Lógica RISK" >> beam.ParDo(CalcularEjercitosDoFn())
        )

        # Bifurcación 1: Histórico a BigQuery
        eventos_procesados | "Guardar Histórico" >> beam.ParDo(WriteToFirestoreDoFn()) # Simulado para print
        
        # Bifurcación 2: Estado a Firestore
        # (En un entorno real aquí llamarías a una función de carga de BQ)