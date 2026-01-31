import streamlit as st
import ee
from datetime import datetime

def render(m, roi, params, col_res):
    st.markdown("### Rainfall & Climate Analysis Results")
    with st.spinner("Processing Meteorological Data..."):
        try:
            # 1. Dataset Selection
            col = None
            rain_band = ''
            scale_res = 5000 # Meters

            if "CHIRPS" in params['dataset']:
                col = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").filterDate(params['start'], params['end']).filterBounds(roi)
                rain_band = 'precipitation'
                scale_res = 5566 
            elif "GPM" in params['dataset']:
                col = ee.ImageCollection("NASA/GPM_L3/IMERG_V06").filterDate(params['start'], params['end']).filterBounds(roi)
                rain_band = 'precipitationCal'
                scale_res = 10000 

            if col.size().getInfo() == 0:
                st.error("No data found for the selected date range.")
                return None, {}

            main_layer = None
            legend_title = ""
            vis_params_rain = {}

            if "Accumulation" in params['calc_mode']:
                main_layer = col.select(rain_band).sum().clip(roi)
                stats = main_layer.reduceRegion(ee.Reducer.minMax(), roi, scale=scale_res, bestEffort=True).getInfo()
                min_val = stats.get(f'{rain_band}_min', 0)
                max_val = stats.get(f'{rain_band}_max', 500)
                
                vis_params_rain = {'min': min_val, 'max': max_val, 'palette': ['#ffffcc', '#a1dab4', '#41b6c4', '#225ea8', '#081d58']}
                legend_title = "Total Rainfall (mm)"
                
            elif "Anomaly" in params['calc_mode']:
                current_sum = col.select(rain_band).sum().clip(roi)
                start_dt = datetime.strptime(params['start'], "%Y-%m-%d")
                end_dt = datetime.strptime(params['end'], "%Y-%m-%d")
                baseline_years = range(start_dt.year - 5, start_dt.year)
                baseline_imgs = []
                for y in baseline_years:
                    s = start_dt.replace(year=y).strftime("%Y-%m-%d")
                    e = end_dt.replace(year=y).strftime("%Y-%m-%d")
                    baseline_imgs.append(ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").filterDate(s, e).select('precipitation').sum())
                ltm = ee.ImageCollection(baseline_imgs).mean().clip(roi)
                main_layer = current_sum.subtract(ltm).divide(ltm).multiply(100).rename('anomaly')
                vis_params_rain = {'min': -50, 'max': 50, 'palette': ['red', 'orange', 'white', 'cyan', 'blue']}
                legend_title = "Rainfall Anomaly (%)"

            m.addLayer(main_layer, vis_params_rain, legend_title)
            m.add_colorbar(vis_params_rain, label=legend_title)
            
            with col_res:
                st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                st.markdown('<div class="card-label">STATISTICS</div>', unsafe_allow_html=True)
                roi_mean = main_layer.reduceRegion(ee.Reducer.mean(), roi, scale=scale_res, bestEffort=True).values().get(0).getInfo()
                unit = "mm" if "Accumulation" in params['calc_mode'] else "%"
                st.metric("Region Average", f"{roi_mean:.1f} {unit}")
                st.markdown("</div>", unsafe_allow_html=True)

            return main_layer, vis_params_rain

        except Exception as e:
            st.error(f"Error in Rainfall Module: {e}")
            return None, {}
