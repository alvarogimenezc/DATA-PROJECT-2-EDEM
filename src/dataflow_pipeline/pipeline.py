import apache_beam as beam

#Simulamos el stream de eventos JSON que llegará desde Pub/Sub
mensajes_simulados = [
    {
        "player_id": "jugador_1", 
        "tile_id": "Ruzafa", 
        "steps": 120, 
        "timestamp": "2026-04-05T21:30:00"
    },
    {
        "player_id": "jugador_2", 
        "tile_id": "Patraix", 
        "steps": 10000, 
        "timestamp": "2026-04-05T21:45:00"
    },
    {
        "player_id": "jugador_3", 
        "tile_id": "Benimaclet,", 
        "steps": 170, 
        "timestamp": "2026-04-05T18:00:06"
    },
]

#conversión a estado
class ProcesarPasosDoFn(beam.DoFn):
    def process(self, mensaje):
        pasos_dados = mensaje["steps"]
        ejercitos_ganados = pasos_dados // 100
        mensaje["ejercitos"] = ejercitos_ganados
        print(f"[BEAM WORKER] -> El {mensaje['player_id']} ha dado {pasos_dados} pasos en {mensaje['tile_id']}. Gana {ejercitos_ganados} ejércitos.")
        yield [mensaje]

if __name__ == "__main__":
    print("--- INICIANDO PRUEBA CON ESTRUCTURA APACHE BEAM ---")

with beam.Pipeline() as pipeline:
    (
            pipeline 
            | "Ingestar Datos Simulados" >> beam.Create(mensajes_simulados) 
            | "Calcular Ejércitos" >> beam.ParDo(ProcesarPasosDoFn())
    )