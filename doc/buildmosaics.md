# buildmosaics.py

builds virtual mosaics from input imagery, ahead of creating slippy map tiles

### required inputs:
`-r [string]`; `--referenceindex`: path to a GeoJSON file containing virtual mosaic boundaries. This file must be standard GeoJSON and must contain the field `OBJECTID` as a unique identifier for each 0.1 by 0.1 degree map grid square; and a `maxzoom` field to set up the maximum zoom level for this mosaic. This will be used to identify virtual mosaics when they are created. an example named `g4326_cas5_bbox_11.geojson` is provided in `resources`.

`-i [string]`; `--imageindex`: path to the JSON image index created in stage one by `buildimageindex.py`

`-o [string]`; `--outputlocation`: a directory which mosaics produced by `buildmosaics.py` will be stored in


### optional inputs

`-in_crs [string]`: EPSG code for incoming data. The default is GDA2020/MGA (`EPSG:7855`) - if input data are *not* provided in EPSG:7855, use `-in_crs` to supply the origin CRS

`-out_crs [string]`: EPSG code for output data. The default is `EPSG:4326`

### Outputs:
- a directory of virtual mosaics in GDAL's VRT format, in the location given by `-g`

There are two virtual mosaics created for each grid square, in the location defined by`-o`, like:
- 212-maxzoom19-native.vrt
- 212-maxzoom19-warped.vrt

The naming format is 'OBJECTID'-'maxzoomlevelXX'-'native|warped'.vrt - which is a cheap way of encoding some configuration which the tile cutter will need (mainly zoom level)

Warped vrt files are used for tile generation, but the native vrts need to be kept until tiles are all built. The warped VRT refers to data source locations references in the native VRT. I can't see a way to go straight to a warped and clipped mosaic without keeping the native VRT yet.

*build all the map grid squares*

`python3 ./buildmosaics.py -i s3://bucket/airphotos.json -o s3://bucket/mosaics -r s3://bucket/g4326_cas5_bbox_11.geojson -g s3://bucket/gridconfiguration.json`

The default operation is to build a mosaic for every feature found in the reference GeoJSON file - whichi will write a pair of mosaics for every feature in the input shapefile to `s3://bucket/mosaics/`

To use a non-default input CRS (for example, imagery referenced to WGS84), do:

`python3 ./buildmosaics.py -i s3://bucket/airphotos.json -o s3://bucket/mosaics -r s3://bucket/g4326_cas5_bbox_11.geojson -g s3://bucket/gridconfiguration.json -in_crs EPSG:4326`

*build one map grid square*

If you know the map grid tile ID for a single map grid square you can build it using the `-m` switch. Note, this example uses local paths, s3:// paths will work just as well:

`python3 buildmosaics.py -i ../airphotosindex/airphotos.json -o ../mosaics -r ../../max_zoom_level_by_z11_tiles/g4326_cas5_bbox_11.geojson -g ./resources/gridconfiguration.json -m 212`

...this will write the files:

- 212-maxzoom19-native.vrt
- 212-maxzoom19-warped.vrt

...to the location `../mosaics/`.
