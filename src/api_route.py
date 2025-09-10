from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional, Union, Dict
import numpy as np
from fastapi.responses import FileResponse
from gerar_mapa import gerar_mapa
import datetime

# OR-Tools imports
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import requests

app = FastAPI()

class Ponto(BaseModel):
    lat: float
    lon: float
    nome: Optional[str] = None

class Coordenadas(BaseModel):
    pontos: List[Ponto]

def haversine(p1, p2):
    from math import radians, sin, cos, sqrt, atan2

    R = 6371  
    lat1, lon1 = p1
    lat2, lon2 = p2

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c

def create_distance_matrix(locations):
    n = len(locations)
    dist_matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i != j:
                dist_matrix[i][j] = haversine(locations[i], locations[j])
    return dist_matrix

def nearest_neighbor_route(dist_matrix):
    n = len(dist_matrix)
    if n == 0:
        return []
    
    visited = [False] * n
    route = []
    current_node = 0
    route.append(current_node)
    visited[current_node] = True
    
    while len(route) < n:
        min_dist = float('inf')
        next_node = -1
        for neighbor in range(n):
            if not visited[neighbor] and dist_matrix[current_node][neighbor] < min_dist:
                min_dist = dist_matrix[current_node][neighbor]
                next_node = neighbor
        if next_node != -1:
            route.append(next_node)
            visited[next_node] = True
            current_node = next_node
        else:
            break
    return route

# Funções otimizadas para o TSP
def solve_tsp_ortools(locations):
    cost_matrix, is_osrm = create_osrm_matrix(locations)
    n = len(locations)

    if n <= 2:
        return list(range(n))

    start_node = 0
    manager = pywrapcp.RoutingIndexManager(n, 1, start_node)
    routing = pywrapcp.RoutingModel(manager)

    def cost_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int(cost_matrix[from_node][to_node])

    transit_callback_index = routing.RegisterTransitCallback(cost_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    search_params = pywrapcp.DefaultRoutingSearchParameters()

    
    search_params.time_limit.seconds = 60
    
    
    search_params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.TABU_SEARCH
    )
    search_params.lns_time_limit.seconds = 5

    solution = routing.SolveWithParameters(search_params)

    if solution:
        index = routing.Start(0)
        rota = []
        while not routing.IsEnd(index):
            rota.append(manager.IndexToNode(index))
            index = solution.Value(routing.NextVar(index))
       
        rota.append(manager.IndexToNode(routing.End(0)))
        return rota
    else:
        return nearest_neighbor_route(cost_matrix)

# Função para criar matriz com OSRM
def create_osrm_matrix(locations):
    coords_str = ";".join([f"{p[1]},{p[0]}" for p in locations])

    url = f"http://router.project-osrm.org/table/v1/driving/{coords_str}?sources=all&destinations=all"

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()

        if 'durations' in data:
            return np.array(data['durations']), True
        else:
            print("Resposta da API OSRM não contém 'durations'. Fallback para Haversine.")
            return create_distance_matrix(locations), False
    except requests.exceptions.RequestException as e:
        print(f"Erro ao conectar com a API do OSRM: {e}. Fallback para Haversine.")
        return create_distance_matrix(locations), False


def filter_points(pontos: List[Ponto], tolerance_km: float = 0.005):
    if not pontos:
        return []

    unique_pontos = []
    coords_unique = set()
    
    for p in pontos:
        coord_tuple = (p.lat, p.lon)
        if coord_tuple in coords_unique:
            continue
        
        is_close = False
        for up in unique_pontos:
            up_coord = (up.lat, up.lon)
            if haversine(coord_tuple, up_coord) < tolerance_km:
                is_close = True
                break
        
        if not is_close:
            unique_pontos.append(p)
            coords_unique.add(coord_tuple)
            
    return unique_pontos

@app.post("/rota")
def calcular_rota(data: Coordenadas):
    print("calculando rotas...")
    
    pontos_filtrados = filter_points(data.pontos, tolerance_km=0.005)
    
    if len(pontos_filtrados) <= 1:
        return {"error": "Não há pontos suficientes para calcular uma rota otimizada."}
        
    n = len(pontos_filtrados)
    velocidade_kmh = 60

    coords = [(p.lat, p.lon) for p in pontos_filtrados]

    
    rota = solve_tsp_ortools(coords)
    
    
    dist_matrix_haversine = create_distance_matrix(coords)
    
    distancia_total = 0
    if len(rota) > 1:
        distancia_total = sum(dist_matrix_haversine[rota[i]][rota[i + 1]] for i in range(len(rota) - 1))
        distancia_total += dist_matrix_haversine[rota[-1]][rota[0]]
    
    tempos_estimados = [
        round(dist_matrix_haversine[rota[i]][rota[i + 1]] / velocidade_kmh, 2)
        for i in range(len(rota) - 1)
    ]
    tempo_total = round(sum(tempos_estimados), 2)

    pontos_dict = [p.dict() for p in pontos_filtrados]
    
    gerar_mapa(
        pontos=pontos_dict,
        rota=rota,
        distancia_total=distancia_total,
        tempo_total=tempo_total,
        velocidade_kmh=velocidade_kmh,
        cor_rota="blue",
        cor_pontos="red",
        tamanho_icone=8
    )

    return {
        "rota": rota,
        "ordem": [coords[i] for i in rota],
        "nomes": [p.nome if p.nome else f"Ponto {i+1}" for i, p in enumerate(pontos_filtrados)],
        "distancia_total_km": round(distancia_total, 2),
        "tempo_total_horas": tempo_total,
        "tempo_estimados_horas": tempos_estimados
    }

@app.get("/mapa")
def get_mapa():
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    return FileResponse(f"rota_mapa.html?v={timestamp}", media_type="text/html")
