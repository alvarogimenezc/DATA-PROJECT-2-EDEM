import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions
import json

class CalcularEjercitosDoFn(beam.DoFn):
    def process(self, element):
        pasos = element.get("steps", 0)
        aire = element.get("air_multiplier", 1.0)
        clima = element.get("weather_penalty", 0.0)
        
        factor_final = aire - clima
        ejercitos_ganados = int((pasos // 100) * factor_final)
        
        element["ejercitos_ganados"] = ejercitos_ganados
        print(f"[CÁLCULO] El {element.get('player_id', 'Desconocido')} gana {ejercitos_ganados} ejércitos.")
        
        yield element

class WriteToFirestoreDoFn(beam.DoFn):
    def process(self, element):
        print(f"[FIRESTORE] Actualizando balance de {element.get('player_id', 'Desconocido')} en la App...")
        yield element

if __name__ == "__main__":
    print("--- INICIANDO DATAFLOW EN MODO STREAMING (PUB/SUB) ---")
    
    options = PipelineOptions(streaming=True)
    
    with beam.Pipeline(options=options) as p:
        eventos_procesados = (
            p 
            | "Leer Pub/Sub" >> beam.io.ReadFromPubSub(subscription="projects/cloudrisk-492619/subscriptions/player-movements-consumer")
            | "Decodificar JSON" >> beam.Map(lambda x: json.loads(x.decode('utf-8')))
            | "Lógica RISK" >> beam.ParDo(CalcularEjercitosDoFn())
        )

        eventos_procesados | "Guardar Histórico BQ" >> beam.Map(lambda x: print(f"[BIGQUERY] Guardando log: {x}"))
        eventos_procesados | "Guardar Estado Firestore" >> beam.ParDo(WriteToFirestoreDoFn())
