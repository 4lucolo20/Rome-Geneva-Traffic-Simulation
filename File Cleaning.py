import osmnx as ox
import geopandas as gpd
import matplotlib.pyplot as plt
import contextily as ctx
import networkx as nx
import pandas as pd
import matplotlib.colors as mcolors
import matplotlib.cm as cm
import re
import json
from shapely.geometry import Point

#TomTom Data: Free Trial on https://developer.tomtom.com
    
# Rome Cleaning

#Rome GTFS Data: https://dati.comune.roma.it/catalog/dataset/c_h501-d-9000/resource/266d82e1-ba53-4510-8a81-370880c4678f

def load_and_plot_rome():
    G = ox.graph_from_place("Rome, Italy", network_type="drive")
    nodes, edges = ox.graph_to_gdfs(G, nodes=True, edges=True)
    edges_web = edges.to_crs(epsg=3857)

    fig, ax = plt.subplots(figsize=(10, 10))
    edges_web.plot(ax=ax, linewidth=1, edgecolor="red")
    ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik)
    ax.axis('off')
    ax.set_title("Road Network of Rome", fontsize=15, fontweight='bold')
    plt.savefig("romeplot.png", transparent=True, dpi=300)
    plt.show()

    return G, nodes, edges

def compute_rome_betweenness(G):
    G = ox.routing.add_edge_speeds(G)
    G = ox.routing.add_edge_travel_times(G)
    bc = nx.betweenness_centrality(G, weight="travel_time", normalized=True)
    nx.set_node_attributes(G, bc, "bc")
    ox.save_graphml(G, "rome_traffic_network_with_bc.graphml")
    return G

def normalize_and_plot_rome(G):
    nodes, edges = ox.graph_to_gdfs(G, nodes=True, edges=True)
    nodes['bc'] = nodes['bc'].astype(float)
    nodes['bc_normalized'] = (nodes['bc'] - nodes['bc'].min()) / (nodes['bc'].max() - nodes['bc'].min())

    nodes_web = nodes.to_crs(epsg=3857)
    edges_web = edges.to_crs(epsg=3857)

    def size_by_centrality(val):
        if val > 0.6: return 60
        if val > 0.3: return 30
        if val > 0.05: return 1
        elif val > 0.01: return 0.005
        else: return 0.001

    nodes_web['marker_size'] = nodes_web['bc_normalized'].apply(size_by_centrality)
    cmap = cm.RdYlGn_r
    norm = mcolors.Normalize(vmin=0, vmax=1)
    node_colors = nodes_web['bc_normalized'].map(lambda x: cmap(norm(x)))

    fig, ax = plt.subplots(figsize=(12, 12))
    edges_web.plot(ax=ax, linewidth=0.1, color="#333333")
    nodes_web.plot(ax=ax, color=node_colors, markersize=nodes_web['marker_size'])
    ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik)
    ax.axis('off')
    ax.set_title("Rome Betweenness Centrality – Scaled by Value", fontsize=14)
    plt.tight_layout()
    plt.savefig("rome_bc_scaled.png", dpi=300, transparent=True)
    plt.show()

    fig, ax = plt.subplots(figsize=(10, 6))
    n, bins, patches = ax.hist(nodes['bc_normalized'], bins=10)
    cmap = plt.cm.RdYlGn_r
    norm = plt.Normalize(bins.min(), bins.max())
    for patch, bin_left in zip(patches, bins[:-1]):
        patch.set_facecolor(cmap(norm(bin_left)))
    for count, patch in zip(n, patches):
        height = patch.get_height()
        if height > 0:
            ax.text(patch.get_x() + patch.get_width()/2, height, f'{int(count)}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    ax.set_axis_off()
    plt.title("Distribution of Normalized Betweenness Centrality - Rome", fontsize=14)
    plt.savefig("rome_bc_hist.png", dpi=300, transparent=True)
    plt.show()

def enrich_rome_with_tomtom(edges, tomtom_path):
    tomtomdf = gpd.read_file(tomtom_path)[['segmentId', 'speedLimit', 'streetName', 'distance', 'segmentTimeResults', 'geometry']]
    edges_proj = edges.to_crs(epsg=32633)
    tomtom_proj = tomtomdf.to_crs(epsg=32633)
    enriched = edges_proj.sjoin_nearest(tomtom_proj, how="left", distance_col="nearest_dist")
    enriched.to_file("rome_edges_with_tomtom.geojson", driver="GeoJSON")
    return enriched

def parse_rome_metro_stops(stops_path):
    df = pd.read_csv(stops_path)
    metro_a = ["BATTISTINI", "CORNELIA", "BALDO DEGLI UBALDI", "VALLE AURELIA", "CIPRO", "OTTAVIANO", "LEPANTO", "FLAMINIO", "SPAGNA", "BARBERINI", "REPUBBLICA", "TERMINI", "VITTORIO EMANUELE", "MANZONI", "SAN GIOVANNI", "RE DI ROMA", "PONTE LUNGO", "FURIO CAMILLO", "COLLI ALBANI", "ARCO DI TRAVERTINO", "PORTA FURBA", "NUMIDIO QUADRATO", "LUCIO SESTIO", "GIULIO AGRICOLA", "SUBAUGUSTA", "CINECITTÀ", "ANAGNINA"]
    metro_b = ["LAURENTINA", "EUR FERMI", "EUR PALASPORT", "EUR MAGLIANA", "MARCONI", "BASILICA S. PAOLO", "GARBATELLA", "PIRAMIDE", "CIRCO MASSIMO", "COLOSSEO", "CAVOUR", "TERMINI", "CASTRO PRETORIO", "POLICLINICO", "BOLOGNA", "TIBURTINA FS", "QUINITILIANI", "MONTI TIBURTINI", "PIETRALATA", "SANTA MARIA DEL SOCCORSO", "PONTE MAMMOLO", "REBIBBIA", "SANT'AGNESE/ANNIBALIANO", "LIBIA", "CONCA D'ORO", "JONIO"]
    metro_c = ["MONTE COMPATRI-PANTANO", "GRANITI", "FINOCCHIO", "BOLOGNETTA", "BORGHESIANA", "DUE LEONI - FONTANA CANDIDA", "GROTTE CELONI", "TORRE GAIA", "TORRE ANGELA", "TORRENOVA", "GIARDINETTI", "TORRE MAURA", "TORRE SPACCATA", "ALESSANDRINO", "PARCO DI CENTOCELLE", "MIRTI", "GARDENIE", "TEANO", "MALATESTA", "PIGNETO", "LODI", "SAN GIOVANNI"]

    all_stations = [(name, "METRO A") for name in metro_a] + [(name, "METRO B") for name in metro_b] + [(name, "METRO C") for name in metro_c]

    def get_metro_line(name):
        for keyword, line in all_stations:
            if keyword in name:
                return line
        return None

    df['metro_line'] = df['stop_name'].apply(get_metro_line)
    metro_df = df[df['metro_line'].notna()][['stop_id', 'stop_code', 'stop_name', 'stop_lat', 'stop_lon', 'metro_line']]
    metro_df.to_csv("romastops.csv", index=False)
    return metro_df


# Geneva Cleaning

#Geneva TPG Stops Data: https://opendata.tpg.ch/explore/dataset/arrets/table/?disjunctive.arretcodelong&disjunctive.nomarret&disjunctive.commune&disjunctive.pays
#Geneva TPG Line Data: https://opendata.tpg.ch/explore/dataset/montees-par-arret-par-ligne/table/?disjunctive.ligne&disjunctive.ligne_type_act&disjunctive.jour_semaine&disjunctive.horaire_type&disjunctive.arret&disjunctive.arret_code_long&disjunctive.indice_semaine

def load_and_plot_geneva():
    G = ox.graph_from_place("Geneva, Switzerland", network_type="drive")
    nodes, edges = ox.graph_to_gdfs(G, nodes=True, edges=True)
    edges_web = edges.to_crs(epsg=3857)

    fig, ax = plt.subplots(figsize=(10, 10))
    edges_web.plot(ax=ax, linewidth=0.1, color="#333333")
    ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik)
    ax.axis('off')
    ax.set_title("Road Network of Geneva", fontsize=15, fontweight='bold')
    plt.savefig("genevaplot.png", transparent=True, dpi=300)
    plt.show()

    return G, nodes, edges

def compute_geneva_betweenness(G):
    G = ox.routing.add_edge_speeds(G)
    G = ox.routing.add_edge_travel_times(G)
    bc = nx.betweenness_centrality(G, weight="travel_time", normalized=True)
    nx.set_node_attributes(G, bc, "bc")
    ox.save_graphml(G, "geneva_traffic_network_with_bc.graphml")
    return G

def normalize_and_plot_geneva(G):
    nodes, edges = ox.graph_to_gdfs(G, nodes=True, edges=True)
    nodes['bc_normalized'] = nodes['bc'].astype(float)
    nodes['bc_normalized'] = (nodes['bc_normalized'] - nodes['bc_normalized'].min()) / (nodes['bc_normalized'].max() - nodes['bc_normalized'].min())

    nodes_web = nodes.to_crs(epsg=3857)
    edges_web = edges.to_crs(epsg=3857)

    def size_by_centrality(val):
        if val > 0.6: return 60
        if val > 0.3: return 30
        if val > 0.05: return 15
        elif val > 0.01: return 10
        else: return 5

    nodes_web['marker_size'] = nodes_web['bc_normalized'].apply(size_by_centrality)
    cmap = cm.RdYlGn_r
    norm = mcolors.Normalize(vmin=0, vmax=1)
    node_colors = nodes_web['bc_normalized'].map(lambda x: cmap(norm(x)))

    fig, ax = plt.subplots(figsize=(12, 12))
    edges_web.plot(ax=ax, linewidth=0.5, color="#333333")
    nodes_web.plot(ax=ax, color=node_colors, markersize=nodes_web['marker_size'])
    ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik)
    ax.axis('off')
    ax.set_title("Geneva Betweenness Centrality – Scaled by Value", fontsize=14)
    plt.tight_layout()
    plt.savefig("geneva_bc_scaled.png", dpi=300, transparent=True)
    plt.show()

    fig, ax = plt.subplots(figsize=(10, 6))
    n, bins, patches = ax.hist(nodes['bc_normalized'], bins=10)
    cmap = plt.cm.RdYlGn_r
    norm = plt.Normalize(bins.min(), bins.max())
    for patch, bin_left in zip(patches, bins[:-1]):
        patch.set_facecolor(cmap(norm(bin_left)))
    for count, patch in zip(n, patches):
        height = patch.get_height()
        if height > 0:
            ax.text(patch.get_x() + patch.get_width()/2, height, f'{int(count)}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    ax.set_axis_off()
    plt.title("Distribution of Normalized Betweenness Centrality - Geneva", fontsize=14)
    plt.savefig("geneva_bc_hist.png", dpi=300, transparent=True)
    plt.show()

def clean_maxspeed(value):
    if pd.isna(value) or value is None:
        return 50
    if isinstance(value, str):
        if 'CH:urban' in value:
            value = value.replace('CH:urban', '50')
        numbers = re.findall(r'\d+', value)
        if numbers:
            return min(map(int, numbers))
        else:
            return 50
    try:
        return float(value)
    except:
        return 50

def parse_geneva_gtfs(stops_path, lines_path, bounding_box, target_date, output_json):
    stops = pd.read_csv(stops_path, sep=';')
    lines = pd.read_csv(lines_path, sep=';')
    lines = lines[lines['Date'] == target_date]
    lines = lines.drop(columns=['Date', 'Line Type', 'Day Week', 'Schedule Type', 'Week Index', 'Day Week Index', 'Number of Boarding Passengers', 'Number of Disembarking Passengers', 'Month Year', 'donnees_definitives', 'filter_graph'])

    stops = stops[stops['Actif'] == 'Y']
    stops[['lat', 'lon']] = stops['Coordonnées'].str.split(',', expand=True).astype(float)
    stops = stops[
        (stops['lat'] >= bounding_box['min_lat']) & (stops['lat'] <= bounding_box['max_lat']) &
        (stops['lon'] >= bounding_box['min_lon']) & (stops['lon'] <= bounding_box['max_lon'])
    ]
    lines = lines[lines['Long Code Stop'].isin(stops['Long Code Stop'])]
    lines = lines.merge(stops[['Long Code Stop', 'lat', 'lon']], on='Long Code Stop', how='left')

    line_routes = lines.groupby('Line').apply(lambda x: list(zip(x['lat'], x['lon']))).to_dict()
    line_routes = {k: v for k, v in line_routes.items() if len(v) > 1}

    with open(output_json, "w") as f:
        json.dump(line_routes, f)

    return line_routes
