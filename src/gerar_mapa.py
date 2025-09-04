import folium
import webbrowser

def gerar_mapa(pontos, rota):
    
    centro = pontos[rota[0]]
    mapa = folium.Map(location=centro, zoom_start=6)

    
    rota_coords = [pontos[i] for i in rota]

    for idx, coord in enumerate(rota_coords):
        folium.Marker(location=coord, popup=f"Ponto {idx}").add_to(mapa)

    folium.PolyLine(locations=rota_coords, color="blue", weight=5).add_to(mapa)

    
    mapa.save("rota_mapa.html")
    webbrowser.open("rota_mapa.html")