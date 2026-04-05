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
def procesar_pasos(mensaje):
    pasos_dados = mensaje["steps"]
    ejercitos_ganados = pasos_dados // 100
    print(f"-> El {mensaje['player_id']} ha dado {pasos_dados} pasos en {mensaje['tile_id']}. Gana {ejercitos_ganados} ejércitos.")
    return ejercitos_ganados

if __name__ == "__main__":
    print("--- INICIANDO PRUEBA ---")
for event in mensajes_simulados:
        procesar_pasos(event)