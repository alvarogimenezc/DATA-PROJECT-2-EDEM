import argparse
import json
import logging
import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions

# ---------------------------------------------------------
# 1. LÓGICA DE NEGOCIO (Transformación)
# ---------------------------------------------------------
class CalcularEjercitosDoFn(beam.DoFn):
    def process(self, element):
        pasos = element.get("steps", 0)
        aire = element.get("air_multiplier", 1.0)
        clima = element.get("weather_penalty", 0.0)
        
        factor_final = aire - clima
        ejercitos_ganados = int((pasos // 100) * factor_final)
        
        element["ejercitos_ganados"] = ejercitos_ganados
        logging.info(f"[CÁLCULO] El jugador {element.get('player_id', 'Desconocido')} gana {ejercitos_ganados} ejércitos.")
        
        yield element

# ---------------------------------------------------------
# 2. ESCRITURA EN FIRESTORE (Estado en vivo)
# ---------------------------------------------------------
class WriteToFirestoreDoFn(beam.DoFn):
    def setup(self):
        # Se importa y conecta AQUÍ para que cada Worker de Google Cloud lo inicialice correctamente
        from google.cloud import firestore
        self.db = firestore.Client()

    def process(self, element):
        player_id = element.get('player_id')
        ejercitos = element.get('ejercitos_ganados', 0)
        
        if player_id:
            # Usamos 'Increment' para sumar a lo que ya tenga el jugador, sin sobreescribirlo a cero
            from google.cloud import firestore
            doc_ref = self.db.collection('user_balance').document(player_id)
            doc_ref.set({
                'armies': firestore.Increment(ejercitos),
                'updated_at': firestore.SERVER_TIMESTAMP
            }, merge=True)
            
            logging.info(f"[FIRESTORE] +{ejercitos} ejércitos guardados para {player_id}.")
        
        yield element

# ---------------------------------------------------------
# 3. CONSTRUCCIÓN DEL PIPELINE
# ---------------------------------------------------------
def run():
    # Parametrización para no hacer "hardcode" (buenas prácticas)
    parser = argparse.ArgumentParser()
    parser.add_argument('--player_sub', required=True, help='Ruta de la suscripción Pub/Sub')
    parser.add_argument('--output_table', required=True, help='Ruta de la tabla BigQuery (proyecto:dataset.tabla)')
    
    known_args, pipeline_args = parser.parse_known_args()
    
    # Forzamos modo streaming
    pipeline_args.extend(['--streaming'])
    options = PipelineOptions(pipeline_args)
    
    with beam.Pipeline(options=options) as p:
        
        # INGESTA Y PROCESAMIENTO
        eventos_procesados = (
            p 
            | "Leer Pub/Sub" >> beam.io.ReadFromPubSub(subscription=known_args.player_sub)
            | "Decodificar JSON" >> beam.Map(lambda x: json.loads(x.decode('utf-8')))
            | "Lógica RISK" >> beam.ParDo(CalcularEjercitosDoFn())
        )

        # SINK 1: BIGQUERY (Histórico)
        eventos_procesados | "Guardar Histórico BQ" >> beam.io.WriteToBigQuery(
            table=known_args.output_table,
            schema='player_id:STRING, steps:INTEGER, ejercitos_ganados:INTEGER, air_multiplier:FLOAT, weather_penalty:FLOAT',
            create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
            write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND
        )

        # SINK 2: FIRESTORE (Vivo - Stretch Goal del profe)
        eventos_procesados | "Guardar Estado Firestore" >> beam.ParDo(WriteToFirestoreDoFn())

if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)
    run()