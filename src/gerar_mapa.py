import folium
from folium import Element
from typing import List, Union, Dict
import requests

def gerar_mapa(
    pontos: List[Union[tuple, Dict]],
    rota: List[int],
    distancia_total: float = None,
    tempo_total: float = None,
    cor_rota: str = "blue",
    cor_pontos: str = "red",
    tamanho_icone: int = 8,
    velocidade_kmh: int = 60,
):
    """
    Gera um arquivo HTML com a rota otimizada em um mapa Folium.
    Agora obtém a geometria da rota do OSRM para traçar o caminho exato.
    """
    from math import radians, cos, sin, asin, sqrt

    def haversine(p1, p2):
        lon1, lat1 = p1[1], p1[0]
        lon2, lat2 = p2[1], p2[0]
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))
        r = 6371
        return c * r

    def get_coords(p):
        return (p["lat"], p["lon"]) if isinstance(p, dict) else p

    def get_name(p, idx):
        return p.get("nome", f"Ponto {idx + 1}") if isinstance(p, dict) else f"Ponto {idx + 1}"
    
    if not pontos:
        return
        
    inicio = get_coords(pontos[rota[0]])
    mapa = folium.Map(location=inicio, zoom_start=14, tiles="Stamen Terrain")
    
    bounds = []
    for idx, i in enumerate(rota):
        coord = get_coords(pontos[i])
        nome = get_name(pontos[i], idx)
        folium.Marker(
            location=coord,
            popup=nome,
            tooltip=f"{idx + 1} - {nome}",
            icon=folium.Icon(color=cor_pontos, icon="info-sign")
        ).add_to(mapa)
        bounds.append(coord)

    try:
        # Pega a ordem dos pontos da rota
        caminho = [get_coords(pontos[i]) for i in rota]
        
        # Converte as coordenadas para o formato lon,lat;lon,lat exigido pelo OSRM
        coords_str = ";".join([f"{p[1]},{p[0]}" for p in caminho])
        
        # URL da API do OSRM para obter a geometria da rota
        # O parâmetro 'geometries=geojson' é crucial para obter os dados do traçado
        url = f"http://router.project-osrm.org/route/v1/driving/{coords_str}?geometries=geojson"
        
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        if 'routes' in data and data['routes']:
            # Extrai as coordenadas da geometria da rota
            geojson_coords = data['routes'][0]['geometry']['coordinates']
            
            # Folium espera as coordenadas no formato [lat, lon]
            folium_coords = [[coord[1], coord[0]] for coord in geojson_coords]
            
            # Desenha a linha da rota usando as coordenadas do OSRM
            folium.PolyLine(folium_coords, color=cor_rota, weight=4, opacity=0.7).add_to(mapa)
        else:
            print("Resposta do OSRM não contém rota válida. Usando linha reta.")
            folium.PolyLine(caminho, color=cor_rota, weight=4, opacity=0.7).add_to(mapa)
            
    except requests.exceptions.RequestException as e:
        print(f"Erro ao obter a rota do OSRM: {e}. Usando linha reta como fallback.")
        folium.PolyLine(caminho, color=cor_rota, weight=4, opacity=0.7).add_to(mapa)
    
    if bounds:
        mapa.fit_bounds(bounds)
    
    if distancia_total is None or tempo_total is None:
        distancia_total = 0.0
        for i in range(len(rota) - 1):
            p1 = get_coords(pontos[rota[i]])
            p2 = get_coords(pontos[rota[i + 1]])
            distancia_total += haversine(p1, p2)
        if len(rota) > 1 and velocidade_kmh > 0:
            tempo_total = distancia_total / velocidade_kmh
        else:
            tempo_total = 0.0

    legenda_html = f"""
    <div style="
        position: fixed;
        bottom: 30px;
        left: 30px;
        z-index: 9999;
        background-color: white;
        padding: 15px;
        border: 2px solid grey;
        border-radius: 10px;
        box-shadow: 2px 2px 6px rgba(0,0,0,0.3);
        font-size: 14px;
    ">
        <b>Resumo da Rota</b><br>
        Distância total: <b>{distancia_total:.2f} km</b><br>
        Tempo estimado: <b>{tempo_total:.2f} horas</b><br>
        Velocidade: {velocidade_kmh} km/h
    </div>
    """
    mapa.get_root().html.add_child(Element(legenda_html))

    mapa.save("rota_mapa.html")
