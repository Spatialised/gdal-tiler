# Python GDAL Tiler

...a product of:

Spatialised (http://spatialised.net); and 2Pi Software (http://2pisoftware.com)

## Overview

Python GDAL Tiler is a set of python scripts which produces slippy map tiles from high resolution airborne orthophotos. It was wholly funded by the Australian Capital Territory Emergency Services Agency (https://esa.act.gov.au), who required a method for making slippy map tiles to fit a bespoke gridding arrangement used by an offline mapping application.

It seeks to act as an appliance which ingests imagery at one end, and produces map tiles in a bespoke gridding schema at the other.

It relies on GDAL's Python API, and the Python geospatial library Shapely. Using GDAL's virtual mosaic format, Python GDAL Tiler uses a delayed compute strategy to process pixel data at the last moment.

This is relatively compute-intensive, at the saving of storage and the advantage of only resampling each orthophoto once between the raw data and the output tile.

## Operation

Python GDAL Tiler has three stages, which broadly reflect a manual process. These steps were determined because the first two are fast and relatively light - whereas the last is compute-intensive and long.

### Step 1: index orthophotos

The first task is to create an index of incoming aerial imagery bounds. Often aerial imagery comes with a boundary index - this step was introduced to ensure reliable delivery of parameters required for later stages.

It uses [buildimageindex.py](doc/buildimageindex.md). Input is a directory of orthophotos, and output is a GeoJSON-like index file. Image bounds are expressed in their native coordinates; where GeoJSON strictly requires latitudes and longitides expressed in a WGS84 geodetic system.

Using native coordinates allows for a single coordinate transformation to occur in the next step.

### Step 2: build virtual mosaics

The ACT ESA tiling schema relies on a 'map grid square' index, dividing a region into 0.1 x 0.1 degree squares. These correspond exactly with the coverage of a single map tile at zoom level 11.

Using this index of map grid squares, we assemble a virtual mosaic for each one using [buildmosaics.py](doc/buildmosaics.md). This grid should be infinitely flexbile, however the capacity to build whatever tiling schemes we like has not been tested.


### Important caveat

This code is released as-is without warranty. Use at your own risk!

Neither Spatialised, 2Pi Software or the ACT Government offer any guaranteed that it will work for you. 

2Pi Software (https://2pisoftware.com.au) offer consulting on batch compute deployment of this code in AWS; and Spatialised (https://spatialised.net) offers consulting on modification of any of the geospatial components.


### tilecutter.py

creates slippy map tiles from virtual mosaics created by `buildmosaics.py`

#### required inputs
`-i [string]`; `--inputmosaic`: full path to a warped virtual mosaic created by `buildmosaics.py`

`-o [string]`; `--outputtilestore`: the full path to a base directory for placing output tiles

`-z [string]`; `--zoomlevel`: the zoom level to be processed

`-g [string]`; `--gridconfiguration`: path to a JSON file containing map grid and dataset boundary information. An example is found in the `resources` directory as `gridconfiguration.json`

#### optional inputs

`-t [string]`; `--tilesize`: output tile size

#### Outputs
- a directory of slippy map tiles as 256 x 256 pixel PNG images for the given zoom level. T

#### Usage

**run a single tile zoom level**

`python3 ./tilecutter.py -i /mnt/bigdata/ACT-image-processing-2019/mosaics/212-maxzoom19-warped.vrt -o ../tilecutter2/zl17 -z 17 -g./resources/gridconfiguration.json`

