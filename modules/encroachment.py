import streamlit as st
import ee
import geemap.foliumap as geemap

def render(m, roi, params, col_res):
    st.markdown("### Encroachment Detection Results")
    with st.spinner("Processing Sentinel-1 SAR Data..."):

        def get_sar_collection(start_d, end_d, roi_geom, orbit_pass):
            s1 = ee.ImageCollection('COPERNICUS/S1_GRD')\
                .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))\
                .filter(ee.Filter.eq('instrumentMode', 'IW'))\
                .filterDate(start_d, end_d)\
                .filterBounds(roi_geom)
            if orbit_pass != "BOTH":
                s1 = s1.filter(ee.Filter.eq('orbitProperties_pass', orbit_pass))
            return s1

        def process_water_mask(col, roi_geom):
            if col.size().getInfo() == 0: return None, "N/A"
            date_found = ee.Date(col.first().get('system:time_start')).format('YYYY-MM-dd').getInfo()
            def speckle_filter(img): return img.select('VV').focal_median(50, 'circle', 'meters').rename('VV_smoothed')
            mosaic = col.map(speckle_filter).min().clip(roi_geom)
            water_mask = mosaic.lt(-16).selfMask()
            return water_mask, date_found

        try:
            col_initial = get_sar_collection(params['d1_start'], params['d1_end'], roi, params['orbit'])
            col_final = get_sar_collection(params['d2_start'], params['d2_end'], roi, params['orbit'])

            water_initial, date_init = process_water_mask(col_initial, roi)
            water_final, date_fin = process_water_mask(col_final, roi)

            if water_initial and water_final:
                encroachment = water_initial.unmask(0).And(water_final.unmask(0).Not()).selfMask()
                new_water = water_initial.unmask(0).Not().And(water_final.unmask(0)).selfMask()
                stable_water = water_initial.unmask(0).And(water_final.unmask(0)).selfMask()

                change_map = ee.Image(0).where(stable_water, 1).where(encroachment, 2).where(new_water, 3).clip(roi).selfMask()
                image_to_export = change_map
                vis_export = {'min': 1, 'max': 3, 'palette': ['cyan', 'red', 'blue']}

                left_layer = geemap.ee_tile_layer(water_initial, {'palette': 'blue'}, "Initial Water")
                right_layer = geemap.ee_tile_layer(water_final, {'palette': 'cyan'}, "Final Water")
                m.split_map(left_layer, right_layer)

                m.addLayer(encroachment, {'palette': 'red'}, '🔴 Encroachment (Loss)')
                m.addLayer(new_water, {'palette': 'blue'}, '🔵 New Water (Gain)')

                pixel_area = encroachment.multiply(ee.Image.pixelArea())
                val_loss = pixel_area.reduceRegion(ee.Reducer.sum(), roi, 10, maxPixels=1e9).values().get(0).getInfo()
                loss_ha = round((val_loss or 0) / 10000, 2)

                pixel_area_gain = new_water.multiply(ee.Image.pixelArea())
                val_gain = pixel_area_gain.reduceRegion(ee.Reducer.sum(), roi, 10, maxPixels=1e9).values().get(0).getInfo()
                gain_ha = round((val_gain or 0) / 10000, 2)

                with col_res:
                    st.markdown('<div class="alert-card">', unsafe_allow_html=True)
                    st.markdown(f"### Change Report")
                    st.metric("Water Loss", f"{loss_ha} Ha", help="Potential Encroachment")
                    st.metric("Water Gain", f"{gain_ha} Ha", help="Flooding/New Storage")

                    st.markdown(f"""
                    <div class="date-badge">Base: {date_init}</div>
                    <div class="date-badge">Curr: {date_fin}</div>
                    """, unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)

                    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                    st.markdown('<div class="card-label">TIMELAPSE</div>', unsafe_allow_html=True)
                    if st.button("Create Timelapse"):
                        with st.spinner("Generating GIF..."):
                            try:
                                s1_tl = get_sar_collection(params['d1_start'], params['d2_end'], roi, params['orbit']).select('VV')
                                video_args = {'dimensions': 600, 'region': roi, 'framesPerSecond': 5, 'min': -25, 'max': -5, 'palette': ['black', 'blue', 'white']}
                                # Note: geemap.create_timeseries might be available in foliumap or implicitly
                                # If it fails, we might need a standard geemap import. 
                                # For now assuming it works as per original code.
                                monthly = geemap.create_timeseries(s1_tl, params['d1_start'], params['d2_end'], frequency='year', reducer='median')
                                gif_url = monthly.getVideoThumbURL(video_args)
                                st.image(gif_url, caption="Radar Intensity (Dark=Water)", use_container_width=True)
                            except Exception as e: st.error(f"Timelapse Error: {e}")
                    st.markdown("</div>", unsafe_allow_html=True)
                
                return image_to_export, vis_export

            else:
                st.warning("Insufficient SAR data for selected dates and orbit.")
                return ee.Image(0), {}
        except Exception as e:
            st.error(f"Computation Error: {e}")
            return None, {}
