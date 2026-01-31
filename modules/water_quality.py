import streamlit as st
import ee
import pandas as pd
from datetime import datetime

def render(m, roi, params, col_res):
    st.markdown(f"### Water Quality ({params['param']})")
    with st.spinner(f"Computing {params['param']} (Scientific Mode)..."):
        try:
            # 1. PRE-PROCESSING FUNCTION (Improved Masking)
            def mask_clouds_and_water(img):
                # Cloud Masking (using S2_CLOUD_PROBABILITY)
                cloud_prob = ee.Image(img.get('cloud_mask')).select('probability')
                is_cloud = cloud_prob.gt(params['cloud'])

                # Scale Bands to Reflectance (0 to 1)
                bands = img.select(['B.*']).multiply(0.0001)

                # Water Masking (NDWI > 0.0)
                ndwi = bands.normalizedDifference(['B3', 'B8']).rename('ndwi')
                is_water = ndwi.gt(0.0)

                return bands.updateMask(is_cloud.Not()).updateMask(is_water).copyProperties(img, ['system:time_start'])

            # 2. LOAD COLLECTIONS
            s2_sr = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterDate(params['start'], params['end']).filterBounds(roi)
            s2_cloud = ee.ImageCollection("COPERNICUS/S2_CLOUD_PROBABILITY").filterDate(params['start'], params['end']).filterBounds(roi)

            # Join collections
            s2_joined = ee.Join.saveFirst('cloud_mask').apply(
                primary=s2_sr, secondary=s2_cloud,
                condition=ee.Filter.equals(leftField='system:index', rightField='system:index')
            )

            processed_col = ee.ImageCollection(s2_joined).map(mask_clouds_and_water)

            # 3. COMPUTE SCIENTIFIC INDICES
            viz_params = {}
            result_layer = None
            layer_name = ""

            if "Turbidity" in params['param']:
                def calc_ndti(img):
                    ndti = img.normalizedDifference(['B4', 'B3']).rename('value')
                    return ndti.copyProperties(img, ['system:time_start'])

                final_col = processed_col.map(calc_ndti)
                result_layer = final_col.mean().clip(roi)
                viz_params = {'min': -0.15, 'max': 0.15, 'palette': ['0000ff', '00ffff', 'ffff00', 'ff0000']}
                layer_name = "Turbidity Index (NDTI)"

            elif "TSS" in params['param']:
                def calc_tss(img):
                    tss = img.expression('2950 * (b4 ** 1.357)', {'b4': img.select('B4')}).rename('value')
                    return tss.copyProperties(img, ['system:time_start'])

                final_col = processed_col.map(calc_tss)
                result_layer = final_col.median().clip(roi)
                viz_params = {'min': 0, 'max': 50, 'palette': ['0000ff', '00ffff', 'ffff00', 'ff0000', '5c0000']}
                layer_name = "TSS (Est. mg/L)"

            elif "Cyanobacteria" in params['param']:
                def calc_cyano(img):
                    cyano = img.expression('b5 / b4', {
                        'b5': img.select('B5'), 'b4': img.select('B4')
                    }).rename('value')
                    return cyano.copyProperties(img, ['system:time_start'])

                final_col = processed_col.map(calc_cyano)
                result_layer = final_col.max().clip(roi)
                viz_params = {'min': 0.8, 'max': 1.5, 'palette': ['0000ff', '00ff00', 'ff0000']}
                layer_name = "Cyano Risk (Ratio > 1)"

            elif "Chlorophyll" in params['param']:
                def calc_ndci(img):
                    ndci = img.normalizedDifference(['B5', 'B4']).rename('value')
                    return ndci.copyProperties(img, ['system:time_start'])

                final_col = processed_col.map(calc_ndci)
                result_layer = final_col.mean().clip(roi)
                viz_params = {'min': -0.1, 'max': 0.2, 'palette': ['0000ff', '00ffff', '00ff00', 'ff0000']}
                layer_name = "Chlorophyll-a (NDCI)"

            elif "CDOM" in params['param']:
                def calc_cdom(img):
                    cdom = img.expression('b3 / b2', {
                        'b3': img.select('B3'), 'b2': img.select('B2')
                    }).rename('value')
                    return cdom.copyProperties(img, ['system:time_start'])

                final_col = processed_col.map(calc_cdom)
                result_layer = final_col.median().clip(roi)
                viz_params = {'min': 0.5, 'max': 2.0, 'palette': ['0000ff', 'yellow', 'brown']}
                layer_name = "CDOM Proxy (Green/Blue)"

            # 4. VISUALIZATION
            if result_layer:
                m.addLayer(result_layer, viz_params, layer_name)
                m.add_colorbar(viz_params, label=layer_name)

                # 5. CHARTING
                with col_res:
                    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                    st.markdown(f'<div class="card-label">TREND ANALYSIS</div>', unsafe_allow_html=True)
                    try:
                        def get_stats(img):
                            date = ee.Date(img.get('system:time_start')).format('YYYY-MM-dd')
                            val = img.reduceRegion(
                                reducer=ee.Reducer.median(),
                                geometry=roi,
                                scale=20,
                                maxPixels=1e9
                            ).values().get(0)
                            return ee.Feature(None, {'date': date, 'value': val})

                        fc = final_col.map(get_stats).filter(ee.Filter.notNull(['value']))
                        data_list = fc.reduceColumns(ee.Reducer.toList(2), ['date', 'value']).get('list').getInfo()

                        if data_list:
                            df_chart = pd.DataFrame(data_list, columns=['Date', 'Value'])
                            df_chart['Date'] = pd.to_datetime(df_chart['Date'])
                            df_chart = df_chart.sort_values('Date').dropna()

                            st.area_chart(df_chart, x='Date', y='Value', color="#005792")
                            st.caption(f"Median {layer_name} over time")

                            # Export Data CSV
                            csv = df_chart.to_csv(index=False).encode('utf-8')
                            st.download_button("Download CSV", csv, "water_quality_ts.csv", "text/csv")
                        else:
                            st.warning("No clear water pixels found (Try reducing cloud threshold).")

                    except Exception as e:
                        st.warning(f"Chart Error: {e}")
                    st.markdown('</div>', unsafe_allow_html=True)
                
                return result_layer, viz_params
            
            else:
                 return None, {}

        except Exception as e:
            st.error(f"Analysis Failed: {e}")
            return None, {}
