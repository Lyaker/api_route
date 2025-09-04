from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Tuple
import numpy as np
from sklearn.metrics.pairwise import haversine_distances
from scipy.optimize import linear_sum_assignment
from fastapi.responses import FileResponse
from gerar_mapa import gerar_mapa

app = FastAPI()

class Coordenadas(BaseModel):
    pontos: List[Tuple[float, float]]

@app.post("/rota")
def calcular_rota(data: Coordenadas):
    pontos = np.radians(data.pontos)  # converter para radianos
    dist_matrix = haversine_distances(pontos) * 6371  # km

    n = len(pontos)
    velocidade_kmh = 60

    
    row_ind, col_ind = linear_sum_assignment(dist_matrix)

    
    rota = [0]
    visitado = set(rota)

    while len(rota) < n:
        ultimo = rota[-1]
        prox = None
        for r, c in zip(row_ind, col_ind):
            if r == ultimo and c not in visitado:
                prox = c
                break
        if prox is None:
            
            prox = next(i for i in range(n) if i not in visitado)
        rota.append(prox)
        visitado.add(prox)

    rota = list(map(int, rota))

    distancia_total = sum(
        dist_matrix[rota[i]][rota[i + 1]] for i in range(len(rota) - 1)
    )

    tempos_estimados = [
        round(dist_matrix[rota[i]][rota[i + 1]] / velocidade_kmh, 2)
        for i in range(len(rota) - 1)
    ]

    gerar_mapa(data.pontos, rota)
    
    return {
        "rota": rota,
        "ordem": [data.pontos[i] for i in rota],
        "distancia_total_km": round(distancia_total, 2),
        "tempo_estimados_horas": tempos_estimados
    }



@app.get("/mapa")
def get_mapa():
    return FileResponse("rota_mapa.html", media_type="text/html")