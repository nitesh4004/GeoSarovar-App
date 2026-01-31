import streamlit as st
import ee

def render(m, roi, params, col_res):
    st.markdown("### Rainwater Harvesting Potential Results")
    with st.spinner("Calculating Multi-Criteria Hydrological Suitability..."):
        try:
            # 1. Inputs
            # Rainfall (Norm)
            chirps = ee.ImageCollection("UCSB-CHG/CHIRPS/PENTAD").filterDate('2020-01-01', '2023-12-31').filterBounds(roi)
            rain_mean = chirps.reduce(ee.Reducer.mean()).clip(roi)
            min_max_r = rain_mean.reduceRegion(ee.Reducer.minMax(), roi, 5000, bestEffort=True).getInfo()
            r_min = min_max_r.get('precipitation_mean_min', 0)
            r_max = min_max_r.get('precipitation_mean_max', 2000)
            norm_rain = rain_mean.unitScale(r_min, r_max)

            # Slope (Norm: Flatter is better 2-8%)
            dem = ee.Image("USGS/SRTMGL1_003").clip(roi)
            slope = ee.Terrain.slope(dem)
            # Invert: High slope = 0 suitability, Low slope = 1
            norm_slope = slope.unitScale(0, 30).multiply(-1).add(1).clamp(0, 1)

            # Drainage (Flow Acc)
            flow_acc = ee.Image("WWF/HydroSHEDS/15ACC").clip(roi)
            log_flow = flow_acc.log()
            norm_drain = log_flow.unitScale(0, 12).clamp(0, 1)

            # Soil (OpenLandMap)
            soil_tex = ee.Image("OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02").clip(roi)
            # Remap based on structure type
            # Classes: 1:Clay... 12:Sand
            if "Pond" in params['type']: 
                # Prefer Clay (1,2,6) for storage
                soil_suit = soil_tex.remap([1,2,3,4,5,6,7,8,9,10,11,12], 
                                            [1.0, 0.9, 0.7, 0.6, 0.5, 0.9, 0.5, 0.4, 0.3, 0.4, 0.1, 0.2])
            else: 
                # Prefer Sand/Loam (9,10,11,12) for recharge
                soil_suit = soil_tex.remap([1,2,3,4,5,6,7,8,9,10,11,12], 
                                            [0.1, 0.2, 0.3, 0.4, 0.5, 0.3, 0.6, 0.7, 0.9, 0.9, 1.0, 0.9])
            
            # LULC (ESA WorldCover)
            esa = ee.ImageCollection("ESA/WorldCover/v100").first().clip(roi)
            # 40:Ag(1.0), 30:Grass(0.9), 50:Urban(0.0)
            lulc_suit = esa.remap([10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100],
                                [0.6, 0.8, 0.9, 1.0, 0.0, 0.1, 0.2, 0.0, 0.5, 0.0, 0.1])

            # 2. Weighted Overlay
            ws = params['w']
            final_idx = (norm_rain.multiply(ws['rain'])) \
                .add(norm_slope.multiply(ws['slope'])) \
                .add(soil_suit.multiply(ws['soil'])) \
                .add(lulc_suit.multiply(ws['lulc'])) \
                .add(norm_drain.multiply(ws['drain']))
            
            final_idx = final_idx.rename('suitability')
            
            # 3. Visualization
            vis_suit = {'min': 0, 'max': 0.8, 'palette': ['red', 'orange', 'yellow', 'green', 'darkgreen']}
            
            m.addLayer(norm_rain, {'min':0, 'max':1, 'palette':['white','blue']}, 'Rainfall Input', False)
            m.addLayer(norm_slope, {'min':0, 'max':1, 'palette':['black','white']}, 'Slope Input', False)
            m.addLayer(final_idx, vis_suit, 'RWH Suitability Index')
            m.add_colorbar(vis_suit, label="Suitability Index (0-1)")
            
            # High Potential Zones
            high_pot = final_idx.updateMask(final_idx.gt(0.65))
            m.addLayer(high_pot, {'palette':['cyan']}, 'High Potential Zones (>0.65)')
            
            with col_res:
                st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                st.markdown('<div class="card-label">MODEL STATS</div>', unsafe_allow_html=True)
                
                mean_suit = final_idx.reduceRegion(ee.Reducer.mean(), roi, scale=1000, bestEffort=True).values().get(0).getInfo()
                st.metric("Avg Suitability", f"{mean_suit:.2f} / 1.0")
                
                st.markdown("**Criteria Weights:**")
                st.progress(ws['rain'], text="Rain")
                st.progress(ws['slope'], text="Slope")
                st.progress(ws['soil'], text="Soil")
                st.caption(f"Structure: {params['type']}")
                st.markdown("</div>", unsafe_allow_html=True)
            
            return final_idx, vis_suit
            
        except Exception as e:
            st.error(f"RWH Analysis Error: {e}")
            return None, {}
