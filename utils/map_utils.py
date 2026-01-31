try:
    import geemap.foliumap as geemap
except Exception:
    import geemap
    import streamlit as st
# Helper for Safe Map Loading (ROBUST FOLIUM VERSION)
def get_safe_map(roi_method, map_style, is_calculated, height=500):
    # 1. Initialize Map (Folium Backend)
    m = geemap.Map(location=[20.59, 78.96], zoom_start=4, max_zoom=25)
    
    # 2. Add Basemap
    if map_style == "Satellite (Hybrid)":
        m.add_basemap("HYBRID")
    elif map_style == "Roadmap":
        m.add_basemap("ROADMAP")
    elif map_style == "Terrain":
        m.add_basemap("TERRAIN")
    elif map_style == "OpenStreetMap":
        m.add_basemap("OpenStreetMap")
    else:
        m.add_basemap("HYBRID")

    # 3. Add Controls
    # m.add_layer_control() # Folium adds this by default or handles it differently
    
    # 4. Handle Drawing Controls
    if roi_method == "Draw on Map" and not is_calculated:
        m.add_draw_control()
        
    return m
