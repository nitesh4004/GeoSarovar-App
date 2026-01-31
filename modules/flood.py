import streamlit as st
import ee

def render(m, roi, params, col_res):
    st.markdown("### Flood Extent Mapping Results")
    with st.spinner("Processing Flood Extent..."):
        try:
            collection = ee.ImageCollection('COPERNICUS/S1_GRD') \
                .filter(ee.Filter.eq('instrumentMode', 'IW')) \
                .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH')) \
                .filter(ee.Filter.eq('resolution_meters', 10)) \
                .filterBounds(roi) \
                .select('VH')

            if params['orbit'] != "BOTH":
                collection = collection.filter(ee.Filter.eq('orbitProperties_pass', params['orbit']))

            before_col = collection.filterDate(params['pre_start'], params['pre_end'])
            after_col = collection.filterDate(params['post_start'], params['post_end'])

            if before_col.size().getInfo() > 0 and after_col.size().getInfo() > 0:
                date_pre = ee.Date(before_col.first().get('system:time_start')).format('YYYY-MM-dd').getInfo()
                date_post = ee.Date(after_col.first().get('system:time_start')).format('YYYY-MM-dd').getInfo()

                before = before_col.median().clip(roi)
                after = after_col.mosaic().clip(roi)

                smoothing = 50
                before_f = before.focal_mean(smoothing, 'circle', 'meters')
                after_f = after.focal_mean(smoothing, 'circle', 'meters')

                difference = after_f.divide(before_f)
                difference_binary = difference.gt(params['threshold'])

                gsw = ee.Image("JRC/GSW1_4/GlobalSurfaceWater")
                occurrence = gsw.select('occurrence')
                permanent_water_mask = occurrence.gt(30)

                flooded = difference_binary.updateMask(permanent_water_mask.Not())

                dem = ee.Image('WWF/HydroSHEDS/03VFDEM')
                slope = ee.Algorithms.Terrain(dem).select('slope')
                flooded = flooded.updateMask(slope.lt(5))

                flooded = flooded.updateMask(flooded.connectedPixelCount().gte(8))
                flooded = flooded.selfMask()

                vis_export = {'min': 0, 'max': 1, 'palette': ['#0000FF']}

                m.addLayer(before_f, {'min': -25, 'max': 0}, 'Before Flood (Dry)', False)
                m.addLayer(after_f, {'min': -25, 'max': 0}, 'After Flood (Wet)', True)
                m.addLayer(flooded, {'palette': ['#0000FF']}, 'Estimated Flood Extent')

                flood_stats = flooded.multiply(ee.Image.pixelArea()).reduceRegion(reducer=ee.Reducer.sum(), geometry=roi, scale=10, bestEffort=True)
                flood_area_ha = round(flood_stats.values().get(0).getInfo() / 10000, 2)

                with col_res:
                    st.markdown('<div class="alert-card">', unsafe_allow_html=True)
                    st.markdown("### Flood Report")
                    st.metric("Estimated Extent", f"{flood_area_ha} Ha")
                    st.markdown(f"""
                    <div class="date-badge">Pre: {date_pre}</div>
                    <div class="date-badge">Post: {date_post}</div>
                    """, unsafe_allow_html=True)
                    st.caption(f"Orbit: {params['orbit']} | Pol: VH")
                    st.markdown("</div>", unsafe_allow_html=True)

                return flooded, vis_export

            else:
                st.error(f"No images found for Orbit: {params['orbit']} in these dates.")
                return None, {}

        except Exception as e:
            st.error(f"Error: {e}")
            return None, {}
