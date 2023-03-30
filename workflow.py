import arcpy
import os
import sys

walk_dir = 'C:/Users/Jacky/School/GEOG4480/data_layers'
utm_29n = arcpy.SpatialReference(32629)
arcpy.env.workspace = walk_dir
arcpy.env.cellSize = 30
arcpy.env.extent = 'administrative_regions/casablanca.shp'
arcpy.env.mask = 'administrative_regions/casablanca.shp'
arcpy.env.snapRaster = 'land_use/REPROJECTED_n29_30_2020lc030.tif'
arcpy.env.outputCoordinateSystem = utm_29n
arcpy.env.overwriteOutput = True

# Reproject data layers to WGS 1984 UTM Zone 29N
for root, folders, files in os.walk(walk_dir):
    for file in files:
        # Only reproject if data isn't already reprojected
        if 'REPROJECTED' not in file:
            original_path = os.path.join(root, file)
            projected_path = os.path.join(root, f'REPROJECTED_{file}')

            if file[-4:] == '.tif':
                # Use nearest neighbour for land use data as its categorical; otherwise use cubic convolution resampling
                mode = 'NEAREST' if 'land_use' in original_path else 'CUBIC'

                print(f'Reproject {original_path} to {utm_29n.name} using {mode} resampling...')

                arcpy.management.ProjectRaster(original_path, projected_path, utm_29n, 'CUBIC')
            elif file[-4:] == '.shp':
                print(f'Reproject {original_path} to {utm_29n.name}...')

                arcpy.management.Project(original_path, projected_path, utm_29n)

# Select Grand Casablanca and convert to single polygon
print('Creating Grand Casablanca polygon...')
casablanca_query = '''
NAME_1 = 'Grand Casablanca'
'''
grand_casablanca = arcpy.SelectLayerByAttribute_management('administrative_regions/casablanca_reprojected.shp', 'NEW_SELECTION', casablanca_query)
arcpy.Dissolve_management(grand_casablanca, 'administrative_regions/casablanca.shp')

# Set extent, mask and snap rasters again to ensure they are using data that have been reprojected and exist
arcpy.env.extent = 'administrative_regions/casablanca.shp'
arcpy.env.mask = 'administrative_regions/casablanca.shp'
arcpy.env.snapRaster = 'land_use/REPROJECTED_n29_30_2020lc030.tif'

# Select clinics + hospitals
print('Selecting hosptials and clinics in Grand Casablanca...')
health_query = '''
healthcare = 'hospital' OR healthcare = 'clinic'
'''
hospital_clinic = arcpy.SelectLayerByAttribute_management('health_facilities_points/REPROJECTED_hotosm_mar_health_facilities_points.shp', 'NEW_SELECTION', health_query)
arcpy.management.CopyFeatures(hospital_clinic, 'health_facilities_points/hospital_clinic.shp')

# Slope mask
print('Calculating slope using DEM to create slope mask...')
slope_degrees = arcpy.sa.Slope('dem/REPROJECTED_N33W008_FABDEM_V1-2.tif', 'DEGREE')
slope_mask = arcpy.sa.Reclassify(slope_degrees, 'VALUE', arcpy.sa.RemapRange([[0, 5, 1]]), 'NODATA')
slope_mask.save('dem/mask_slope.tif')

# Land use mask
print('Create land use (suitable land uses: Grasslands, Shrubland and Farmland) mask...')
land_class_reclassified = arcpy.sa.Reclassify('land_use/REPROJECTED_n29_30_2020lc030.tif', 'VALUE', arcpy.sa.RemapValue([[10, 1], [30, 1], [40, 1]]), 'NODATA')
land_class_reclassified.save('land_use/mask_land.tif')

# Road line distance accumulation + mask
print('Perform distance accumulatation on roads...')
road_distance = arcpy.sa.DistanceAccumulation('road_lines/REPROJECTED_hotosm_mar_roads_lines.shp.shp')
road_distance.save('road_lines/road_distance.tif')
print('Create road mask to exclude road surfaces and their surrounding 10 m regions...')
road_mask = arcpy.sa.Reclassify(road_distance, 'VALUE', arcpy.sa.RemapRange([[10, 1337, 1]]), 'NODATA')
road_mask.save('road_lines/mask_road.tif')

# Railway line distance accumulation + mask
print('Perform distance accumulatation on railways...')
railway_distance = arcpy.sa.DistanceAccumulation('railway_lines/REPROJECTED_hotosm_mar_railways_lines.shp')
railway_distance.save('railway_lines/railway_distance.tif')
print('Create railway mask to exclude railbeds and their surrounding 200 m regions...')
railway_mask = arcpy.sa.Reclassify(railway_distance, 'VALUE', arcpy.sa.RemapRange([[200, 20641, 1]]), 'NODATA')
railway_mask.save('railway_lines/mask_rail.tif')

# Waterbody distance accumulation + mask
print('Perform distance accumulatation on waterbodies...')
waterbody_distance = arcpy.sa.DistanceAccumulation('waterways/REPROJECTED_hotosm_mar_waterways_lines.shp')
waterbody_distance.save('waterways/waterbody_distance.tif')
print('Create 250 m waterbody mask to exclude waterbodies and their surrounding 250 m regions...')
waterbody_mask_250 = arcpy.sa.Reclassify(waterbody_distance, 'VALUE', arcpy.sa.RemapRange([[250, 14096, 1]]), 'NODATA')
waterbody_mask_250.save('waterways/mask_water_250.tif')
print('Create 500 m waterbody mask to exclude waterbodies and their surrounding 500 m regions...')
waterbody_mask_500 = arcpy.sa.Reclassify(waterbody_distance, 'VALUE', arcpy.sa.RemapRange([[500, 14096, 1]]), 'NODATA')
waterbody_mask_500.save('waterways/mask_water_500.tif')
print('Create 1000 m waterbody mask to exclude waterbodies and their surrounding 1000 m regions...')
waterbody_mask_1000 = arcpy.sa.Reclassify(waterbody_distance, 'VALUE', arcpy.sa.RemapRange([[1000, 14096, 1]]), 'NODATA')
waterbody_mask_1000.save('waterways/mask_water_1000.tif')

# Final masks
road_mask = arcpy.Raster('road_lines/mask_road.tif')
railway_mask = arcpy.Raster('railway_lines/mask_rail.tif')
slope_mask = arcpy.Raster('dem/mask_slope.tif')
landuse_mask = arcpy.Raster('land_use/mask_land.tif')
water_250_mask = arcpy.Raster('waterways/mask_water_250.tif')
water_500_mask = arcpy.Raster('waterways/mask_water_500.tif')
water_1000_mask = arcpy.Raster('waterways/mask_water_1000.tif')

print('Calculate final mask using 250 m waterbody mask...')
mask_crofty = road_mask * railway_mask * slope_mask * landuse_mask * water_250_mask
print('Calculate final mask using 500 m waterbody mask...')
mask_brundle = road_mask * railway_mask * slope_mask * landuse_mask * water_500_mask
print('Calculate final mask using 1000 m waterbody mask...')
mask_kravitz = road_mask * railway_mask * slope_mask * landuse_mask * water_1000_mask

mask_crofty.save('mask_crofty.tif')
mask_brundle.save('mask_brundle.tif')
mask_kravitz.save('mask_kravitz.tif')

# Bus stop distance accumulation
print('Perform distance accumulatation on bus stops...')
bus_distance = arcpy.sa.DistanceAccumulation('bus_stops/REPROJECTED_bus-stops.shp')
bus_distance.save('bus_stops/bus_distance.tif')

# Airport distance accumulation
print('Perform distance accumulatation on airports...')
airport_distance = arcpy.sa.DistanceAccumulation('airports_points/REPROJECTED_hotosm_mar_airports_points.shp')
airport_distance.save('airports_points/airport_distance.tif')

# Hotel distance accumulation
print('Perform distance accumulatation on hotels...')
hotel_distance = arcpy.sa.DistanceAccumulation('hotels/REPROJECTED_hotels.shp')
hotel_distance.save('hotels/hotel_distance.tif')

# Health distance accumulation
print('Perform distance accumulatation on hosptial and clinics...')
health_distance = arcpy.sa.DistanceAccumulation('health_facilities_points/hospital_clinic.shp')
health_distance.save('health_facilities_points/health_distance.tif')

# Train stops distance accumulation
print('Perform distance accumulatation on train stops...')
train_stop_distance = arcpy.sa.DistanceAccumulation('train_stops/REPROJECTED_train-stops.shp')
train_stop_distance.save('train_stops/train_stop_distance.tif')

# Standardise roads
print('Rescale roads using an exponential function to standardise...')
rescaled_road_distance = arcpy.sa.RescaleByFunction('road_lines/road_distance.tif', arcpy.sa.TfExponential(0, -0.001722935025391958, 0, None, 1336.4317626953, None), 1, 10)
rescaled_road_distance.save('suitability_model/rescaled_roads.tif')

# Standardise health
print('Rescale hosptial and clinics using an exponential function to standardise...')
rescaled_health_distance = arcpy.sa.RescaleByFunction('health_facilities_points/health_distance.tif', arcpy.sa.TfExponential(0, -8.336368521733462e-05, 0, None, 27620.9609375, None), 1, 10)
rescaled_health_distance.save('suitability_model/rescaled_health.tif')

# Standardise bus stops
print('Rescale bus stops using a small function to standardise...')
rescaled_bus_distance = arcpy.sa.RescaleByFunction('bus_stops/bus_distance.tif', arcpy.sa.TfSmall(4370.65380859375, 5, 0, None, 8741.3076171875, None), 1, 10)
rescaled_bus_distance.save('suitability_model/rescaled_bus.tif')

# Standardise airports
print('Rescale airports using a small function to standardise...')
rescaled_airport_distance = arcpy.sa.RescaleByFunction('airports_points/airport_distance.tif', arcpy.sa.TfSmall(10197.626953125, 5, 0, None, 20395.25390625, None), 1, 10)
rescaled_airport_distance.save('suitability_model/rescaled_airports.tif')

# Standardise hotels
print('Rescale hotels using a small function to standardise...')
rescaled_airport_distance = arcpy.sa.RescaleByFunction('hotels/hotel_distance.tif', arcpy.sa.TfSmall(11622.482421875, 5, 0, None, 23244.96484375, None), 1, 10)
rescaled_airport_distance.save('suitability_model/rescaled_hotels.tif')

# Standardise train stops
print('Rescale train stops using a small function to standardise...')
rescaled_train_distance = arcpy.sa.RescaleByFunction('train_stops/train_stop_distance.tif', arcpy.sa.TfSmall(13236.3115234375, 5, 0, None, 26472.623046875, None), 1, 10)
rescaled_train_distance.save('suitability_model/rescaled_train_stops.tif')

# Suitability models

airports = arcpy.Raster('suitability_model/rescaled_airports.tif')
bus = arcpy.Raster('suitability_model/rescaled_bus.tif')
health = arcpy.Raster('suitability_model/rescaled_health.tif')
hotels = arcpy.Raster('suitability_model/rescaled_hotels.tif')
trains = arcpy.Raster('suitability_model/rescaled_train_stops.tif')
roads = arcpy.Raster('suitability_model/rescaled_roads.tif')
masks = {
    'crofty': arcpy.Raster('mask_crofty.tif'),
    'brundle': arcpy.Raster('mask_brundle.tif'),
    'kravitz': arcpy.Raster('mask_kravitz.tif'),
}

weights = {
    'annaliese': [
        0.12,
        0.15,
        0.30,
        0.14,
        0.04,
        0.26
    ],
    'jacky': [
        0.09,
        0.11,
        0.32,
        0.12,
        0.04,
        0.32
    ],
    'marina': [
        0.13,
        0.08,
        0.43,
        0.14,
        0.04,
        0.26
    ]
}

print('Calculate suitability score raster using weight set 1 and 250 m waterbody mask...')
equation_annaliese_crofty = ((airports * weights['annaliese'][0]) \
                            + (bus * weights['annaliese'][1]) \
                            + (health*weights['annaliese'][2]) \
                            + (hotels * weights['annaliese'][3]) \
                            + (trains * weights['annaliese'][4]) \
                            + (roads * weights['annaliese'][5])) \
                            * masks['crofty']
equation_annaliese_crofty.save('vettel_suitability_crofty.tif')

print('Calculate suitability score raster using weight set 1 and 500 m waterbody mask...')
equation_annaliese_brundle = ((airports * weights['annaliese'][0]) \
                            + (bus * weights['annaliese'][1]) \
                            + (health*weights['annaliese'][2]) \
                            + (hotels * weights['annaliese'][3]) \
                            + (trains * weights['annaliese'][4]) \
                            + (roads * weights['annaliese'][5])) \
                            * masks['brundle']
equation_annaliese_brundle.save('vettel_suitability_brundle.tif')

print('Calculate suitability score raster using weight set 1 and 1000 m waterbody mask...')
equation_annaliese_kravitz = ((airports * weights['annaliese'][0]) \
                            + (bus * weights['annaliese'][1]) \
                            + (health*weights['annaliese'][2]) \
                            + (hotels * weights['annaliese'][3]) \
                            + (trains * weights['annaliese'][4]) \
                            + (roads * weights['annaliese'][5])) \
                            * masks['kravitz']
equation_annaliese_kravitz.save('vettel_suitability_kravitz.tif')

print('Calculate suitability score raster using weight set 2 and 250 m waterbody mask...')
equation_jacky_crofty = ((airports * weights['jacky'][0]) \
                            + (bus * weights['jacky'][1]) \
                            + (health*weights['jacky'][2]) \
                            + (hotels * weights['jacky'][3]) \
                            + (trains * weights['jacky'][4]) \
                            + (roads * weights['jacky'][5])) \
                            * masks['crofty']
equation_jacky_crofty.save('villeneuve_suitability_crofty.tif')

print('Calculate suitability score raster using weight set 2 and 500 m waterbody mask...')
equation_jacky_brundle = ((airports * weights['jacky'][0]) \
                            + (bus * weights['jacky'][1]) \
                            + (health*weights['jacky'][2]) \
                            + (hotels * weights['jacky'][3]) \
                            + (trains * weights['jacky'][4]) \
                            + (roads * weights['jacky'][5])) \
                            * masks['brundle']
equation_jacky_brundle.save('villeneuve_suitability_brundle.tif')

print('Calculate suitability score raster using weight set 2 and 1000 m waterbody mask...')
equation_jacky_kravitz = ((airports * weights['jacky'][0]) \
                            + (bus * weights['jacky'][1]) \
                            + (health*weights['jacky'][2]) \
                            + (hotels * weights['jacky'][3]) \
                            + (trains * weights['jacky'][4]) \
                            + (roads * weights['jacky'][5])) \
                            * masks['kravitz']
equation_jacky_kravitz.save('villeneuve_suitability_kravitz.tif')

print('Calculate suitability score raster using weight set 3 and 250 m waterbody mask...')
equation_marina_crofty = ((airports * weights['marina'][0]) \
                            + (bus * weights['marina'][1]) \
                            + (health*weights['marina'][2]) \
                            + (hotels * weights['marina'][3]) \
                            + (trains * weights['marina'][4]) \
                            + (roads * weights['marina'][5])) \
                            * masks['crofty']
equation_marina_crofty.save('senna_suitability_crofty.tif')

print('Calculate suitability score raster using weight set 3 and 500 m waterbody mask...')
equation_marina_brundle = ((airports * weights['marina'][0]) \
                            + (bus * weights['marina'][1]) \
                            + (health*weights['marina'][2]) \
                            + (hotels * weights['marina'][3]) \
                            + (trains * weights['marina'][4]) \
                            + (roads * weights['marina'][5])) \
                            * masks['brundle']
equation_marina_brundle.save('senna_suitability_brundle.tif')

print('Calculate suitability score raster using weight set 3 and 1000 m waterbody mask...')
equation_marina_kravitz = ((airports * weights['marina'][0]) \
                            + (bus * weights['marina'][1]) \
                            + (health*weights['marina'][2]) \
                            + (hotels * weights['marina'][3]) \
                            + (trains * weights['marina'][4]) \
                            + (roads * weights['marina'][5])) \
                            * masks['kravitz']
equation_marina_kravitz.save('senna_suitability_kravitz.tif')

print('Select scores higher than 7.5 and reclassify selected values to a binary raster...')
vettel_binary = arcpy.sa.Reclassify('vettel_suitability_crofty.tif', 'VALUE', arcpy.sa.RemapRange([[7.5, 10, 1]]), 'NODATA')
villeneuve_binary = arcpy.sa.Reclassify('villeneuve_suitability_crofty.tif', 'VALUE', arcpy.sa.RemapRange([[7.5, 10, 1]]), 'NODATA')
senna_binary = arcpy.sa.Reclassify('senna_suitability_crofty.tif', 'VALUE', arcpy.sa.RemapRange([[7.5, 10, 1]]), 'NODATA')

print('Convert binary raster to a polygon shapefile...')
arcpy.conversion.RasterToPolygon(vettel_binary, 'vettel_binary.shp', 'SIMPLIFY', 'VALUE')
arcpy.conversion.RasterToPolygon(villeneuve_binary, 'villeneuve_binary.shp', 'SIMPLIFY', 'VALUE')
arcpy.conversion.RasterToPolygon(senna_binary, 'senna_binary.shp', 'SIMPLIFY', 'VALUE')

print('Calculate area statistic for each parcel of suitable land...')
vettel_binary_with_area = arcpy.management.CalculateGeometryAttributes('vettel_binary.shp', 'SHAPE_AREA AREA', None, 'SQUARE_METERS', None, 'SAME_AS_INPUT')
villeneuve_binary_with_area = arcpy.management.CalculateGeometryAttributes('villeneuve_binary.shp', 'SHAPE_AREA AREA', None, 'SQUARE_METERS', None, 'SAME_AS_INPUT')
senna_binary_with_area = arcpy.management.CalculateGeometryAttributes('senna_binary.shp', 'SHAPE_AREA AREA', None, 'SQUARE_METERS', None, 'SAME_AS_INPUT')

selected_area_query = '''
SHAPE_AREA >= 1500000
'''

print('Select final suitable regions whose area is over 1.5 sq km/15000000 sq m...')
vettel_selected_area = arcpy.SelectLayerByAttribute_management(vettel_binary_with_area, 'NEW_SELECTION', selected_area_query)
villeneuve_selected_area = arcpy.SelectLayerByAttribute_management(villeneuve_binary_with_area, 'NEW_SELECTION', selected_area_query)
senna_selected_area = arcpy.SelectLayerByAttribute_management(senna_binary_with_area, 'NEW_SELECTION', selected_area_query)

print('Convert suitable regions polygon shapefile to a raster...')
arcpy.conversion.PolygonToRaster(vettel_selected_area, 'SHAPE_AREA', 'vettel_final_regions.tif')
arcpy.conversion.PolygonToRaster(villeneuve_selected_area, 'SHAPE_AREA', 'villeneuve_final_regions.tif')
arcpy.conversion.PolygonToRaster(senna_selected_area, 'SHAPE_AREA', 'senna_final_regions.tif')

print('Reclassify as binary raster...')
vettel_intermediate_binary = arcpy.sa.Reclassify('vettel_final_regions.tif', 'VALUE', arcpy.sa.RemapRange([[0, sys.float_info.max, 1]]), 'NODATA')
villeneuve_intermediate_binary = arcpy.sa.Reclassify('villeneuve_final_regions.tif', 'VALUE', arcpy.sa.RemapRange([[0, sys.float_info.max, 1]]), 'NODATA')
senna_intermediate_binary = arcpy.sa.Reclassify('senna_final_regions.tif', 'VALUE', arcpy.sa.RemapRange([[0, sys.float_info.max, 1]]), 'NODATA')

crofty = arcpy.Raster('waterways/mask_water_250.tif')
brundle = arcpy.Raster('waterways/mask_water_500.tif')
kravitz = arcpy.Raster('waterways/mask_water_1000.tif')

vettel_suitability_crofty = arcpy.Raster('vettel_suitability_crofty.tif')
vettel_suitability_brundle = arcpy.Raster('vettel_suitability_brundle.tif')
vettel_suitability_kravitz = arcpy.Raster('vettel_suitability_kravitz.tif')
villeneuve_suitability_crofty = arcpy.Raster('villeneuve_suitability_crofty.tif')
villeneuve_suitability_brundle = arcpy.Raster('villeneuve_suitability_brundle.tif')
villeneuve_suitability_kravitz = arcpy.Raster('villeneuve_suitability_kravitz.tif')
senna_suitability_crofty = arcpy.Raster('senna_suitability_crofty.tif')
senna_suitability_brundle = arcpy.Raster('senna_suitability_brundle.tif')
senna_suitability_kravitz = arcpy.Raster('senna_suitability_kravitz.tif')

print('Calculate final suitable regions + scores using weight set 1 and 250 m waterbody mask...')
vettel_final_regions_crofty = vettel_suitability_crofty * vettel_intermediate_binary
print('Calculate final suitable regions + scores using weight set 1 and 500 m waterbody mask...')
vettel_final_regions_brundle = vettel_suitability_brundle * vettel_intermediate_binary
print('Calculate final suitable regions + scores using weight set 1 and 1000 m waterbody mask...')
vettel_final_regions_kravitz = vettel_suitability_kravitz * vettel_intermediate_binary

print('Calculate final suitable regions + scores using weight set 2 and 250 m waterbody mask...')
villeneuve_final_regions_crofty = villeneuve_suitability_crofty * villeneuve_intermediate_binary
print('Calculate final suitable regions + scores using weight set 2 and 500 m waterbody mask...')
villeneuve_final_regions_brundle = villeneuve_suitability_brundle * villeneuve_intermediate_binary
print('Calculate final suitable regions + scores using weight set 2 and 1000 m waterbody mask...')
villeneuve_final_regions_kravitz = villeneuve_suitability_kravitz * villeneuve_intermediate_binary

print('Calculate final suitable regions + scores using weight set 3 and 250 m waterbody mask...')
senna_final_regions_crofty = senna_suitability_crofty * senna_intermediate_binary
print('Calculate final suitable regions + scores using weight set 3 and 500 m waterbody mask...')
senna_final_regions_brundle = senna_suitability_brundle * senna_intermediate_binary
print('Calculate final suitable regions + scores using weight set 3 and 1000 m waterbody mask...')
senna_final_regions_kravitz = senna_suitability_kravitz * senna_intermediate_binary

vettel_final_regions_crofty.save('finalregions_vettel_crofty.tif')
vettel_final_regions_brundle.save('finalregions_vettel_brundle.tif')
vettel_final_regions_kravitz.save('finalregions_vettel_kravitz.tif')

villeneuve_final_regions_crofty.save('finalregions_villeneuve_crofty.tif')
villeneuve_final_regions_brundle.save('finalregions_villeneuve_brundle.tif')
villeneuve_final_regions_kravitz.save('finalregions_villeneuve_kravitz.tif')

senna_final_regions_crofty.save('finalregions_senna_crofty.tif')
senna_final_regions_brundle.save('finalregions_senna_brundle.tif')
senna_final_regions_kravitz.save('finalregions_senna_kravitz.tif')

print('Operation complete!')
