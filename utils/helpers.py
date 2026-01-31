import ee
import xml.etree.ElementTree as ET
import re
import requests
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
import numpy as np
from io import BytesIO
from PIL import Image

def parse_kml(content):
    try:
        if isinstance(content, bytes): content = content.decode('utf-8')
        match = re.search(r'<coordinates>(.*?)</coordinates>', content, re.DOTALL | re.IGNORECASE)
        if match: return process_coords(match.group(1))
        root = ET.fromstring(content)
        for elem in root.iter():
            if elem.tag.lower().endswith('coordinates') and elem.text:
                return process_coords(elem.text)
    except: pass
    return None

def process_coords(text):
    raw = text.strip().split()
    coords = [[float(x.split(',')[0]), float(x.split(',')[1])] for x in raw if len(x.split(',')) >= 2]
    return ee.Geometry.Polygon([coords]) if len(coords) > 2 else None

def geojson_to_ee(geo_json):
    """Converts a GeoJSON geometry dictionary to an Earth Engine Geometry."""
    try:
        if geo_json['type'] == 'Polygon':
            return ee.Geometry.Polygon(geo_json['coordinates'])
        elif geo_json['type'] == 'Point':
            return ee.Geometry.Point(geo_json['coordinates'])
        return None
    except:
        return None

def detect_state_from_geometry(geometry):
    """
    Detects which Indian State the geometry center falls into using FAO GAUL.
    """
    try:
        states = ee.FeatureCollection("FAO/GAUL/2015/level1")
        center = geometry.centroid(100)
        intersecting_state = states.filterBounds(center).first()
        state_name = intersecting_state.get('ADM1_NAME').getInfo()
        return state_name
    except:
        return None

def generate_static_map_display(image, roi, vis_params, title, cmap_colors=None, is_categorical=False, class_names=None):
    try:
        if isinstance(roi, ee.Geometry):
            try:
                roi_json = roi.getInfo()
                roi_bounds = roi.bounds().getInfo()['coordinates'][0]
            except: return None
        else:
            roi_json = roi
            roi_bounds = roi['coordinates'][0]

        lons = [p[0] for p in roi_bounds]
        lats = [p[1] for p in roi_bounds]
        min_lon, max_lon = min(lons), max(lons)
        min_lat, max_lat = min(lats), max(lats)

        width_deg = max_lon - min_lon
        height_deg = max_lat - min_lat
        if height_deg == 0: height_deg = 0.001

        aspect_ratio = (width_deg * np.cos(np.radians((min_lat + max_lat) / 2))) / height_deg
        fig_width = 12
        fig_height = fig_width / aspect_ratio
        if fig_height > 20: fig_height = 20
        if fig_height < 4: fig_height = 4

        s2_background = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")\
            .filterBounds(roi).filterDate('2023-01-01', '2023-12-31')\
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))\
            .median().visualize(min=0, max=3000, bands=['B4', 'B3', 'B2'])

        if 'palette' in vis_params or 'min' in vis_params:
            analysis_vis = image.visualize(**vis_params)
        else:
            analysis_vis = image

        final_image = s2_background.blend(analysis_vis)

        thumb_url = final_image.getThumbURL({
            'region': roi_json, 'dimensions': 1000, 'format': 'png', 'crs': 'EPSG:4326'
        })

        response = requests.get(thumb_url, timeout=120)
        if response.status_code != 200: return None

        img_pil = Image.open(BytesIO(response.content))

        fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=300, facecolor='#ffffff')
        extent = [min_lon, max_lon, min_lat, max_lat]
        ax.imshow(img_pil, extent=extent, aspect='auto')
        ax.set_title(title, fontsize=18, fontweight='bold', pad=20, color='#00204a')

        ax.tick_params(colors='black', labelsize=10)
        for spine in ax.spines.values(): spine.set_edgecolor('black')

        if is_categorical and class_names and 'palette' in vis_params:
            patches = [mpatches.Patch(color=c, label=n) for n, c in zip(class_names, vis_params['palette'])]
            legend = ax.legend(handles=patches, loc='upper center', bbox_to_anchor=(0.5, -0.08),
                                     frameon=False, ncol=min(len(class_names), 4))
        elif cmap_colors and 'min' in vis_params:
            cmap = mcolors.LinearSegmentedColormap.from_list("custom", cmap_colors)
            norm = mcolors.Normalize(vmin=vis_params['min'], vmax=vis_params['max'])
            sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
            sm.set_array([])
            cax = fig.add_axes([0.92, 0.15, 0.02, 0.7])
            cbar = plt.colorbar(sm, cax=cax)
            cbar.set_label('Index Value', color='black', fontsize=12)

        buf = BytesIO()
        plt.savefig(buf, format='jpg', bbox_inches='tight', facecolor='#ffffff')
        buf.seek(0)
        plt.close(fig)
        return buf
    except: return None
