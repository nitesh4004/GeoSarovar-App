import streamlit as st
import ee
from datetime import datetime, timedelta

# Local Modules
import utils.auth as auth
import utils.helpers as helpers
import utils.map_utils as map_utils
import utils.ui as ui
import modules.rainfall as rainfall
import modules.rwh as rwh
import modules.encroachment as encroachment
import modules.flood as flood
import modules.water_quality as water_quality

# --- 1. PAGE CONFIG ---
st.set_page_config(
    page_title="GeoSarovar - Water Intelligence",
    page_icon="geosarovar.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. CSS STYLING ---
st.markdown(ui.get_css(), unsafe_allow_html=True)

# --- 3. AUTHENTICATION (GEE) ---
auth.authenticate_gee()

# --- STATE MANAGEMENT ---
if 'calculated' not in st.session_state: st.session_state['calculated'] = False
if 'roi' not in st.session_state: st.session_state['roi'] = None
if 'mode' not in st.session_state: st.session_state['mode'] = "Rainfall & Climate Analysis"
if 'detected_state' not in st.session_state: st.session_state['detected_state'] = None 

# --- 4. SIDEBAR ---
with st.sidebar:
    st.image("geosarovar.png", width=150)
    
    # Show Active Project
    if 'active_project' in st.session_state:
        st.caption(f"Connected to: `{st.session_state['active_project']}`")
    
    st.markdown("### 1. Select Module")
    # Cleaned Names (No Emojis as requested)
    app_mode = st.radio("Choose Functionality:",
                        ["Rainfall & Climate Analysis",
                         "Rainwater Harvesting Potential",
                         "Encroachment (S1 SAR)",
                         "Flood Extent Mapping",
                         "Water Quality"],
                        label_visibility="collapsed")
    st.markdown("---")

    st.markdown("### 2. Location (ROI)")
    roi_method = st.radio("Selection Mode", ["Upload KML", "Point & Buffer", "Draw on Map"], label_visibility="collapsed")
    
    st.markdown("**Map Style**")
    map_style = st.selectbox("Select Basemap", ["Satellite (Hybrid)", "Roadmap", "Terrain", "OpenStreetMap"], index=0, label_visibility="collapsed")

    new_roi = None
    
    if roi_method == "Upload KML":
        kml = st.file_uploader("Upload KML", type=['kml'])
        if kml: 
            new_roi = helpers.parse_kml(kml.read())
            if new_roi:
                st.session_state['roi'] = new_roi.simplify(maxError=50)

    elif roi_method == "Point & Buffer":
        c1, c2 = st.columns(2)
        lat = c1.number_input("Lat", value=20.59)
        lon = c2.number_input("Lon", value=78.96)
        rad = st.number_input("Radius (m)", value=5000)
        new_roi = ee.Geometry.Point([lon, lat]).buffer(rad).bounds()
        if new_roi:
            st.session_state['roi'] = new_roi
            
    elif roi_method == "Draw on Map":
        if st.session_state['roi'] is not None:
             st.info(f"ROI Set: {st.session_state.get('detected_state', 'Custom Area')}")
             if st.button("Reset / Draw New"):
                st.session_state['roi'] = None
                st.session_state['calculated'] = False
                st.session_state['detected_state'] = None
                st.rerun()

    # --- ROI LOCKING & STATE DETECTION ---
    if roi_method != "Draw on Map" and st.session_state['roi']:
        if not st.session_state['detected_state']:
            with st.spinner("Detecting Location..."):
                detected = helpers.detect_state_from_geometry(st.session_state['roi'])
                if detected:
                    st.session_state['detected_state'] = detected
                    st.success(f"ROI Locked ({detected})")
                else:
                    st.success("ROI Locked")
        else:
             st.success(f"ROI Locked ({st.session_state['detected_state']})")

    st.markdown("---")

    params = {}
    
    # --- MODULE PARAMETERS ---
    if app_mode == "Rainfall & Climate Analysis":
        st.markdown("### 3. Data & Time Parameters")
        dataset = st.selectbox("Dataset Source", ["CHIRPS (Daily Climatology)", "GPM (IMERG Near-Real-Time)"])
        st.markdown("**Analysis Period**")
        col1, col2 = st.columns(2)
        rain_start = col1.date_input("Start Date", datetime(2023, 6, 1))
        rain_end = col2.date_input("End Date", datetime(2023, 9, 30))
        calc_mode = st.radio("Calculation Mode", ["Total Accumulation (mm)", "Rainfall Anomaly (%)"])
        params = {'dataset': dataset, 'start': rain_start.strftime("%Y-%m-%d"), 'end': rain_end.strftime("%Y-%m-%d"), 'calc_mode': calc_mode}

    elif app_mode == "Rainwater Harvesting Potential":
        st.markdown("### 3. Suitability Criteria")
        rwh_type = st.selectbox("Target Structure", ["Percolation Tank (Recharge)", "Check Dam (Streams)", "Farm Pond (Storage)"])
        
        # Smart Auto-Weights
        def_rain, def_slope, def_soil, def_lulc, def_drain = 0.25, 0.20, 0.20, 0.15, 0.20
        geo_zone = "General (Plateau)"
        state_for_logic = st.session_state.get('detected_state', None)

        if state_for_logic:
            if state_for_logic in ["Rajasthan", "Gujarat", "Haryana"]:
                geo_zone = "Arid/Semi-Arid"
                def_rain, def_slope, def_soil, def_lulc, def_drain = 0.35, 0.15, 0.25, 0.10, 0.15
            elif state_for_logic in ["Himachal Pradesh", "Uttarakhand", "Sikkim", "Arunachal Pradesh", "Jammu and Kashmir", "Ladakh"]:
                geo_zone = "Hilly/Mountainous"
                def_rain, def_slope, def_soil, def_lulc, def_drain = 0.10, 0.40, 0.15, 0.10, 0.25
            elif state_for_logic in ["Kerala", "Goa", "Konkan"]:
                geo_zone = "Coastal/Wet"
                def_rain, def_slope, def_soil, def_lulc, def_drain = 0.10, 0.30, 0.20, 0.20, 0.20
            elif state_for_logic in ["Uttar Pradesh", "Bihar", "West Bengal", "Punjab"]:
                geo_zone = "Alluvial Plains"
                def_rain, def_slope, def_soil, def_lulc, def_drain = 0.20, 0.10, 0.15, 0.30, 0.25

        st.info(f"Detected Zone: **{geo_zone}**")
        st.caption("Weights auto-adjusted for this terrain.")

        st.markdown("**Criteria Weights (0-1)**")
        w_rain = st.slider("Rainfall", 0.0, 1.0, def_rain, 0.05)
        w_slope = st.slider("Slope (Topography)", 0.0, 1.0, def_slope, 0.05)
        w_soil = st.slider("Soil Texture", 0.0, 1.0, def_soil, 0.05)
        w_lulc = st.slider("Land Use", 0.0, 1.0, def_lulc, 0.05)
        w_drain = st.slider("Drainage Density", 0.0, 1.0, def_drain, 0.05)
        
        total = w_rain + w_slope + w_soil + w_lulc + w_drain
        if total == 0: total = 1
        params = {'type': rwh_type, 'w': {'rain': w_rain/total, 'slope': w_slope/total, 'soil': w_soil/total, 'lulc': w_lulc/total, 'drain': w_drain/total}}

    elif app_mode == "Encroachment (S1 SAR)":
        st.markdown("### 3. Comparison Dates")
        orbit = st.radio("Orbit Pass", ["BOTH", "ASCENDING", "DESCENDING"])
        st.markdown("**Initial Period (Baseline)**")
        col1, col2 = st.columns(2)
        d1_start = col1.date_input("Start 1", datetime(2018, 6, 1))
        d1_end = col2.date_input("End 1", datetime(2018, 9, 30))
        st.markdown("**Final Period (Current)**")
        col3, col4 = st.columns(2)
        d2_start = col3.date_input("Start 2", datetime(2024, 6, 1))
        d2_end = col4.date_input("End 2", datetime(2024, 9, 30))
        params = {'d1_start': d1_start.strftime("%Y-%m-%d"), 'd1_end': d1_end.strftime("%Y-%m-%d"), 'd2_start': d2_start.strftime("%Y-%m-%d"), 'd2_end': d2_end.strftime("%Y-%m-%d"), 'orbit': orbit}

    elif app_mode == "Flood Extent Mapping":
        st.markdown("### 3. Flood Event Details")
        orbit = st.radio("Orbit Pass", ["BOTH", "ASCENDING", "DESCENDING"])
        st.markdown("**Before Flood (Dry)**")
        col1, col2 = st.columns(2)
        pre_start = col1.date_input("Pre Start", datetime(2023, 4, 1))
        pre_end = col2.date_input("Pre End", datetime(2023, 6, 1))
        st.markdown("**After Flood (Wet)**")
        col3, col4 = st.columns(2)
        post_start = col3.date_input("Post Start", datetime(2023, 9, 29))
        post_end = col4.date_input("Post End", datetime(2023, 10, 15))
        threshold = st.slider("Difference Threshold", 1.0, 1.5, 1.25, 0.05)
        params = {'pre_start': pre_start.strftime("%Y-%m-%d"), 'pre_end': pre_end.strftime("%Y-%m-%d"), 'post_start': post_start.strftime("%Y-%m-%d"), 'post_end': post_end.strftime("%Y-%m-%d"), 'threshold': threshold, 'orbit': orbit}

    elif app_mode == "Water Quality":
        st.markdown("### 3. Monitoring Config")
        wq_param = st.selectbox("Parameter", ["Turbidity (NDTI)", "Total Suspended Solids (TSS)", "Cyanobacteria Index", "Chlorophyll-a", "CDOM (Organic Matter)"])
        st.markdown("**Timeframe**")
        col1, col2 = st.columns(2)
        wq_start = col1.date_input("Start", datetime.now()-timedelta(days=90))
        wq_end = col2.date_input("End", datetime.now())
        cloud_thresh = st.slider("Max Cloud Cover %", 5, 50, 20)
        params = {'param': wq_param, 'start': wq_start.strftime("%Y-%m-%d"), 'end': wq_end.strftime("%Y-%m-%d"), 'cloud': cloud_thresh}

    st.markdown("###")
    if st.button("RUN ANALYSIS"):
        if st.session_state['roi']:
            st.session_state['calculated'] = True
            st.session_state['mode'] = app_mode
            st.session_state['params'] = params
        else:
            st.error("Please draw or select an ROI first.")


# --- 5. MAIN CONTENT ---
st.markdown(f"""
<div class="hud-header">
    <div>
        <div class="hud-title">GeoSarovar</div>
        <div style="color:#5c6b7f; font-size:0.9rem; font-weight:600;">MODULE: {app_mode.upper()}</div>
    </div>
    <div style="text-align:right;">
        <span style="background:#e6f0ff; color:#00204a; padding:5px 12px; border-radius:20px; font-weight:bold; font-size:0.8rem;">LIVE SYSTEM</span>
    </div>
</div>
""", unsafe_allow_html=True)

# --- CASE 1: DRAW MODE ACTIVE, ROI NOT SET ---
if roi_method == "Draw on Map" and st.session_state['roi'] is None:
    st.info("**Instructions:**\n1. Use the **Polygon** or **Rectangle** tool on the map sidebar.\n2. Draw your area of interest.\n3. Click the **'Set as ROI'** button below to lock it.")
    
    m_draw = map_utils.get_safe_map(roi_method, map_style, st.session_state['calculated'], 550)
    map_output = m_draw.to_streamlit(width=None, height=550)

    if st.button("Set as ROI", type="primary"):
        if map_output and isinstance(map_output, dict) and map_output.get('last_active_drawing'):
            drawn_geom = map_output['last_active_drawing']['geometry']
            ee_geom = helpers.geojson_to_ee(drawn_geom)
            
            if ee_geom:
                st.session_state['roi'] = ee_geom
                with st.spinner("Locking Region & Detecting State..."):
                    detected = helpers.detect_state_from_geometry(ee_geom)
                    if detected:
                        st.session_state['detected_state'] = detected
                    else:
                        st.session_state['detected_state'] = "Custom Area"
                st.success("ROI Locked! Please click 'RUN ANALYSIS' in the sidebar.")
                st.rerun()
        else:
            st.warning("No drawing detected! Please draw a polygon on the map first.")

# --- CASE 2: ROI IS SET BUT NOT CALCULATED YET ---
elif not st.session_state['calculated']:
    st.info(f"ROI Locked ({st.session_state.get('detected_state', 'Unknown')}). Please click **RUN ANALYSIS** in the sidebar.")
    m = map_utils.get_safe_map(roi_method, map_style, st.session_state['calculated'], 500)
    
    if st.session_state['roi']:
        # THIS TRY-EXCEPT IS CRITICAL FOR SERVICE USAGE API ERRORS
        try:
            m.centerObject(st.session_state['roi'], 12)
            m.addLayer(ee.Image().paint(st.session_state['roi'], 2, 3), {'palette': 'yellow'}, 'ROI')
        except ee.EEException as e:
            if "serviceUsage" in str(e) or "permission" in str(e):
                st.error("**Permission Error:** Service Usage API needed.")
                st.markdown(f"[Enable Service Usage API](https://console.cloud.google.com/apis/library/serviceusage.googleapis.com?project={st.session_state.get('active_project', 'your-project-id')})")
                st.stop()
            else:
                st.warning(f"Map Error: {e}")
    m.to_streamlit(height=500)

# --- CASE 3: ANALYSIS RESULTS ---
else:
    roi = st.session_state['roi']
    mode = st.session_state['mode']
    p = st.session_state['params']

    col_map, col_res = st.columns([3, 1])
    m = map_utils.get_safe_map(roi_method, map_style, st.session_state['calculated'], 700)
    
    # Permission check wrapper for map centering (just in case)
    try:
        m.centerObject(roi, 13)
    except ee.EEException as e:
        if "serviceUsage" in str(e) or "permission" in str(e):
            st.error("**Permission Error: Service Usage API not enabled.**")
            st.markdown(f"[Enable Service Usage API](https://console.cloud.google.com/apis/library/serviceusage.googleapis.com?project={st.session_state.get('active_project', 'your-project-id')})")
            st.stop()
        else:
            st.warning(f"Could not center map on ROI: {e}")

    image_to_export = None
    vis_export = {}

    # --- DELEGATE TO MODULES ---
    if mode == "Rainfall & Climate Analysis":
        image_to_export, vis_export = rainfall.render(m, roi, p, col_res)
    elif mode == "Rainwater Harvesting Potential":
        image_to_export, vis_export = rwh.render(m, roi, p, col_res)
    elif mode == "Encroachment (S1 SAR)":
        image_to_export, vis_export = encroachment.render(m, roi, p, col_res)
    elif mode == "Flood Extent Mapping":
        image_to_export, vis_export = flood.render(m, roi, p, col_res)
    elif mode == "Water Quality":
        image_to_export, vis_export = water_quality.render(m, roi, p, col_res)

    # --- EXPORT TOOLS (COMMON) ---
    with col_res:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-label">EXPORTS</div>', unsafe_allow_html=True)

        if st.button("Save to Drive (GeoTIFF)"):
            if image_to_export:
                desc = f"GeoSarovar_{mode.split(' ')[0]}_{datetime.now().strftime('%Y%m%d')}"
                ee.batch.Export.image.toDrive(
                    image=image_to_export, description=desc,
                    scale=30, region=roi, folder='GeoSarovar_Exports'
                ).start()
                st.toast("Export started! Check Google Drive.")
            else:
                st.warning("No result to export.")

        st.markdown("---")
        report_title = st.text_input("Report Title", f"Analysis: {mode}")
        if st.button("Generate Map Image"):
            with st.spinner("Rendering..."):
                if image_to_export:
                    is_cat = False
                    c_names = None
                    cmap = None
                    if mode == "Flood Extent Mapping":
                        is_cat = True; c_names = ['Flood Extent']
                    elif mode == "Encroachment (S1 SAR)":
                        is_cat = True; c_names = ['Stable Water', 'Encroachment', 'New Water']
                    elif 'palette' in vis_export:
                        cmap = vis_export['palette']

                    buf = helpers.generate_static_map_display(image_to_export, roi, vis_export, report_title, cmap_colors=cmap, is_categorical=is_cat, class_names=c_names)
                    if buf:
                        st.download_button("Download JPG", buf, "GeoSarovar_Map.jpg", "image/jpeg", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_map:
        m.to_streamlit(height=700)
