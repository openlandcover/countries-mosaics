"""
Google Earth Engine Landsat Mosaic Generator for PARAGUAY
===========================================================

This script generates annual Landsat mosaics for PARAGUAY using Google Earth Engine.
It processes Landsat Collection 2 imagery (Landsat 4-9) with cloud/shadow masking,
spectral indices calculation, and SMA (Spectral Mixture Analysis) to create
analysis-ready composite images organized by grid tiles.

Version: 1
Dependencies: earthengine-api, custom MapBiomas modules
"""

import ee
import sys
import os

# Add custom module paths to Python path
sys.path.append(os.path.abspath('..\\'))
sys.path.append(os.path.abspath('..\\mapbiomas-mosaics'))

print(sys.path)

# Import custom MapBiomas modules for processing
from modules.CloudAndShadowMaskC2 import *
from modules.SpectralIndexes import *
from modules.Miscellaneous import *
from modules.SmaAndNdfi import *
from modules.Collection import *
from modules.BandNames import * 
from modules.DataType import *
from modules.Mosaic import *

# Prevent Python from writing .pyc files
sys.dont_write_bytecode = True

# Initialize Google Earth Engine with MapBiomas PARAGUAY project
ee.Initialize(project = "mapbiomas-mosaics")

# ============================================================================
# CONFIGURATION PARAMETERS
# ============================================================================

# Version of the landsat masks to use
versionMasks = '2'

# Asset path for 1:250,000 scale grid system (CIM world grid)
gridsAsset = 'projects/mapbiomas-workspace/AUXILIAR/cim-world-1-250000'

# Asset path for Landsat tile masks (removes image edge artifacts)
assetMasks = "projects/mapbiomas-workspace/AUXILIAR/landsat-mask"



# Territory names to process (no spaces allowed)
territoryNames = [
    'PARAGUAY',
]

# Version numbers for each territory
version = {
    'PARAGUAY': '1',
}

# Data filtering parameters for each territory
dataFilter = {
    'PARAGUAY': {
        'dateStart': '01-01',  # Start date (MM-DD format)
        'dateEnd': '12-31',    # End date (MM-DD format)
        'cloudCover': 80       # Maximum cloud cover percentage
    },
}

# Grid names (1:250,000 map sheets) covering Paraguay
# Currently only SE-20-Z-C is active; 
gridNames = {
    "PARAGUAY":[ 
    "SE-20-Z-C", "SE-20-Z-D", "SE-21-Y-C", "SE-21-Y-D", "SF-20-X-A", "SF-20-X-B", 
    "SF-20-X-C", "SF-20-X-D", "SF-20-Z-A", "SF-20-Z-B", "SF-20-Z-C", "SF-20-Z-D", 
    "SF-21-V-A", "SF-21-V-B", "SF-21-V-C", "SF-21-V-D", "SF-21-X-C", "SF-21-X-D", 
    "SF-21-Y-A", "SF-21-Y-B", "SF-21-Y-C", "SF-21-Y-D", "SF-21-Z-A", "SF-21-Z-B", 
    "SF-21-Z-C", "SF-21-Z-D", "SG-20-X-B", "SG-21-V-A", "SG-21-V-B", "SG-21-V-C", 
    "SG-21-V-D", "SG-21-X-A", "SG-21-X-B", "SG-21-X-C", "SG-21-X-D", "SG-21-Y-A", 
    "SG-21-Y-B", "SG-21-Y-C", "SG-21-Y-D", "SG-21-Z-A", "SG-21-Z-B", "SG-21-Z-C", 
    "SG-21-Z-D"
    ]
}


# Google Earth Engine Collection IDs for Landsat satellites (Collection 2, Tier 1, Level 2)
collectionIds = {
    'l4': 'LANDSAT/LT04/C02/T1_L2',  # Landsat 4 TM (1982-1993)
    'l5': 'LANDSAT/LT05/C02/T1_L2',  # Landsat 5 TM (1984-2013)
    'l7': 'LANDSAT/LE07/C02/T1_L2',  # Landsat 7 ETM+ (1999-present)
    'l8': 'LANDSAT/LC08/C02/T1_L2',  # Landsat 8 OLI (2013-present)
    'l9': 'LANDSAT/LC09/C02/T1_L2',  # Landsat 9 OLI-2 (2021-present)
}

# Landsat identifiers for SMA endmember selection
landsatIds = {
    'l4': 'landsat-4',
    'l5': 'landsat-5',
    'l7': 'landsat-7',
    'l8': 'landsat-8',
    'l9': 'landsat-9',
}

# Output asset collections for each Landsat sensor
outputCollections = {
    'l4': 'projects/mapbiomas-mosaics/assets/LANDSAT/LULC/PARAGUAY/mosaics-2',
    'l5': 'projects/mapbiomas-mosaics/assets/LANDSAT/LULC/PARAGUAY/mosaics-2',
    'l7': 'projects/mapbiomas-mosaics/assets/LANDSAT/LULC/PARAGUAY/mosaics-2',
    'l8': 'projects/mapbiomas-mosaics/assets/LANDSAT/LULC/PARAGUAY/mosaics-2',
    'l9': 'projects/mapbiomas-mosaics/assets/LANDSAT/LULC/PARAGUAY/mosaics-2'
}

# Buffer size in meters to expand grid boundaries (reduces edge effects)
bufferSize = 100

# Year and satellite combinations to process
# Format: [year, satellite_code]
yearsSat = [
    [2025, 'l9'],
    # [2025, 'l8'],
    [2024, 'l8'],
    [2024, 'l9'],
    [2023, 'l9'],
    [2023, 'l8'],
    [2022, 'l8'],
    [2021, 'l8'], 
    [2020, 'l8'], 
    [2019, 'l8'],
    [2018, 'l8'], 
    [2017, 'l8'], 
    [2016, 'l8'],
    [2015, 'l8'], 
    [2014, 'l8'], 
    [2013, 'l8'],
    [2012, 'l7'], 
    [2011, 'l5'], 
    [2010, 'l5'], 
    [2009, 'l5'],
    [2008, 'l5'], 
    [2007, 'l5'], 
    [2006, 'l5'],
    [2005, 'l5'], 
    [2004, 'l5'], 
    [2003, 'l5'],
    [2002, 'l7'], 
    [2001, 'l7'], 
    [2000, 'l7'],
    [1999, 'l5'], 
    [1998, 'l5'], 
    [1997, 'l5'],
    [1996, 'l5'], 
    [1995, 'l5'], 
    [1994, 'l5'],
    [1993, 'l5'], 
    [1992, 'l5'], 
    [1991, 'l5'],
    [1990, 'l5'], 
    [1989, 'l5'], 
    [1988, 'l5'],
    [1987, 'l5'], 
    [1986, 'l5'], 
    [1985, 'l5'],

    # [2003, 'l5'],
    # [2002, 'l5'], 
    # [2001, 'l5'], 
    # [2000, 'l5'],

    # [2012, 'l7'], 
    # [2011, 'l7'], 
    # [2010, 'l7'], 
    # [2009, 'l7'],
    # [2008, 'l7'], 
    # [2007, 'l7'], 
    # [2006, 'l7'],
    # [2005, 'l7'], 
    # [2004, 'l7'], 
]


def multiplyBy10000(image):

    bands = [
        'blue',
        'red',
        'green',
        'nir',
        'swir1',
        'swir2',
        'cai',
        'evi2',
        'gcvi',
        'hallcover',
        'hallheigth',
        'ndvi',
        'ndwi',
        'pri',
        'savi',
    ]

    return image.addBands(
        srcImg=image.select(bands).multiply(10000),
        names=bands,
        overwrite=True
    )


def divideBy10000(image):

    bands = [
        'blue',
        'red',
        'green',
        'nir',
        'swir1',
        'swir2'
    ]

    return image.addBands(
        srcImg=image.select(bands).divide(10000),
        names=bands,
        overwrite=True
    )


def applyCloudAndShadowMask(collection):

    # Get cloud and shadow masks
    collectionWithMasks = getMasks(collection,
                                   cloudThresh=10,
                                   cloudFlag=True,
                                   cloudScore=True,
                                   cloudShadowFlag=True,
                                   cloudShadowTdom=True,
                                   zScoreThresh=-1,
                                   shadowSumThresh=4000,
                                   dilatePixels=4,
                                   cloudHeights=[
                                       200, 700, 1200, 1700, 2200, 2700,
                                       3200, 3700, 4200, 4700
                                   ],
                                   cloudBand='cloudShadowFlagMask')

    # get collection without clouds
    collectionWithoutClouds = collectionWithMasks \
        .map(
            lambda image: image.mask(
                image.select([
                    'cloudFlagMask',
                    'cloudShadowFlagMask'  # ,
                    # 'cloudScoreMask',
                    # 'cloudShadowTdomMask'
                ]).reduce(ee.Reducer.anyNonZero()).eq(0)
            )
        )

    return collectionWithoutClouds


def getTiles(collection):

    collection = collection.map(
        lambda image: image.set(
            'tile', {
                'path': image.get('WRS_PATH'),
                'row': image.get('WRS_ROW'),
                'id': ee.Number(image.get('WRS_PATH'))
                        .multiply(1000).add(image.get('WRS_ROW')).int32()
            }
        )
    )

    tiles = collection.distinct(['tile']).reduceColumns(
        ee.Reducer.toList(), ['tile']).get('list')

    return tiles.getInfo()


def getExcludedImages(biome, year):

    assetId = 'projects/mapbiomas-workspace/MOSAICOS/workspace-c5'

    collection = ee.ImageCollection(assetId) \
        .filterMetadata('region', 'equals', biome) \
        .filterMetadata('year', 'equals', str(year))

    excluded = ee.List(collection.reduceColumns(ee.Reducer.toList(), ['black_list']).get('list')) \
        .map(
            lambda names: ee.String(names).split(',')
    )

    return excluded.flatten().getInfo()


# ============================================================================
# MAIN PROCESSING LOOP
# ============================================================================

# Load all available tile masks for filtering valid path/row combinations
collectionTiles = ee.ImageCollection(assetMasks)

allTiles = collectionTiles.reduceColumns(
    ee.Reducer.toList(), ['tile']).get('list').getInfo()

# Process each territory (currently only Paraguay)
for territoryName in territoryNames:

    # Load grid features for this territory
    grids = ee.FeatureCollection(gridsAsset)\
        .filter(
        ee.Filter.inList('name', gridNames[territoryName])
    )

    # Process each grid tile
    for gridName in gridNames[territoryName]:

        # Process each year and satellite combination
        for year, satellite in yearsSat:
            print(year, satellite)
            
            # Construct date strings from configuration
            dateStart = '{}-{}'.format(year, dataFilter[territoryName]['dateStart'])
            dateEnd = '{}-{}'.format(year, dataFilter[territoryName]['dateEnd'])
            cloudCover = dataFilter[territoryName]['cloudCover']
            
            try:
                # Check if this mosaic already exists in the output collection
                alreadyInCollection = ee.ImageCollection(outputCollections[satellite]) \
                    .filterMetadata('year', 'equals', year) \
                    .filterMetadata('territory', 'equals', territoryName) \
                    .filterMetadata('version', 'equals', version[territoryName]) \
                    .reduceColumns(ee.Reducer.toList(), ['system:index']) \
                    .get('list') \
                    .getInfo()
                
                # Construct output asset name
                outputName = territoryName + '-' + \
                    gridName + '-' + \
                    str(year) + '-' + \
                    satellite.upper() + '-' + \
                    str(version[territoryName])
                
                
                # Skip if mosaic already exists
                if outputName not in alreadyInCollection:
                    # print(outputName)
                    # Define processing geometry with buffer
                    grid = grids.filter(ee.Filter.eq('name', gridName))
                    grid = ee.Feature(grid.first()).geometry()\
                        .buffer(bufferSize).bounds()

                    excluded = []  # List of excluded images (currently empty)

                    # Retrieve Landsat images for this grid and year
                    collection = getCollection(collectionIds[satellite],
                                               dateStart='{}-{}'.format(year, '01-01'),
                                               dateEnd='{}-{}'.format(year, '12-31'),
                                               cloudCover=cloudCover,
                                               geometry=grid,
                                               trashList=excluded
                                               )
                    
                    # Detect which Landsat tiles (path/row) intersect this grid
                    tiles = getTiles(collection)
                    # Filter to only tiles with available masks
                    tiles = list(
                        filter(
                            lambda tile: tile['id'] in allTiles,
                            tiles
                        )
                    )

                    subcollectionList = []
                    
                    if len(tiles) > 0:
                        # Process each Landsat tile separately to apply tile-specific masks
                        for tile in tiles:
                            # print(tile['path'], tile['row'])

                            # Filter collection to this specific path/row
                            subcollection = collection \
                                .filterMetadata('WRS_PATH', 'equals', tile['path']) \
                                .filterMetadata('WRS_ROW', 'equals', tile['row'])

                            # Load and apply tile mask (removes edge artifacts)
                            tileMask = ee.Image(
                                '{}/{}-{}'.format(assetMasks, tile['id'], versionMasks))

                            subcollection = subcollection.map(
                                lambda image: image.mask(tileMask).selfMask()
                            )

                            subcollectionList.append(subcollection)

                        # Merge all tile subcollections into single collection
                        collection = ee.List(subcollectionList) \
                            .iterate(
                                lambda subcollection, collection:
                                    ee.ImageCollection(
                                        collection).merge(subcollection),
                                ee.ImageCollection([])
                        )

                        collection = ee.ImageCollection(collection)

                        # Standardize band names to consistent naming convention
                        bands = getBandNames(satellite + 'c2')
                        collection = collection.select(
                            bands['bandNames'],
                            bands['newNames']
                        )

                        # Apply cloud and shadow masking
                        collection = applyCloudAndShadowMask(collection)

                        # Get spectral endmembers for Spectral Mixture Analysis (SMA)
                        endmember = ENDMEMBERS[landsatIds[satellite]]

                        # Calculate SMA fractions (vegetation, soil, shade, etc.)
                        collection = collection.map(
                            lambda image: image.addBands(
                                getFractions(image, endmember))
                        )

                        # calculate SMA indexes
                        collection = collection\
                            .map(getNDFI)\
                            .map(getSEFI)\
                            .map(getWEFI)\
                            .map(getFNS)

                        # calculate Spectral indexes
                        collection = collection\
                            .map(divideBy10000)\
                            .map(getCAI)\
                            .map(getEVI2)\
                            .map(getGCVI)\
                            .map(getHallCover)\
                            .map(getHallHeigth)\
                            .map(getNDVI)\
                            .map(getNDWI)\
                            .map(getPRI)\
                            .map(getSAVI)\
                            .map(multiplyBy10000)

                        # Generate annual mosaic using percentile-based compositing
                        # Pantanal uses NDWI (water index), others use NDVI (vegetation)
                        # if territoryName in ['PANTANAL']:
                        #     percentileBand = 'ndwi'
                        # else:
                        percentileBand = 'ndvi'

                        mosaic = getMosaic(collection,
                                           percentileDry=25,      # 25th percentile (dry season)
                                           percentileWet=75,      # 75th percentile (wet season)
                                           percentileBand=percentileBand,
                                           dateStart=dateStart,
                                           dateEnd=dateEnd)

                        # Add texture and topography bands
                        mosaic = getEntropyG(mosaic)  # GLCM entropy texture
                        mosaic = getSlope(mosaic)     # Terrain slope
                        
                        # Set appropriate data types for each band
                        mosaic = setBandTypes(mosaic)

                        # Add metadata properties
                        mosaic = mosaic.set('year', year)
                        mosaic = mosaic.set('collection', 1.0)
                        mosaic = mosaic.set('grid_name', gridName)
                        mosaic = mosaic.set('version', str(version[territoryName]))
                        mosaic = mosaic.set('territory', territoryName)
                        mosaic = mosaic.set('satellite', satellite)

                        # print(outputName)

                        # Export mosaic to Earth Engine asset
                        task = ee.batch.Export.image.toAsset(
                            image=mosaic,
                            description=outputName,
                            assetId=outputCollections[satellite] + '/' + outputName,
                            region=grid.coordinates().getInfo(),
                            scale=30,              # 30-meter spatial resolution
                            maxPixels=int(1e13)    # Maximum pixels to export
                        )

                        task.start()

            except Exception as e:
                # Handle queue limit errors
                msg = 'Too many tasks already in the queue (3000). Please wait for some of them to complete.'
                if e == msg:
                    raise Exception(e)
                else:
                    print(e)
