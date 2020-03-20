#!/usr/bin/python3
"""
Given an:
- aerial imagery source folder
- index of aerial imagery bounds
- index of 'map grid squares'

This code will output a set of mosaics as GDAL
virtual files OR geotiffs corresponding to map grid
squares which contain aerial imagery.

The output files will be cropped to map grid squares


Adam Steer
Spatialised :: http://spatialised.net
May 2019

"""
# do we need to parse arguments...
# yes! if we're calling from the CLI
from argparse import ArgumentParser

import json

from shapely.geometry import shape, Polygon, mapping
from shapely.ops import transform

from osgeo import gdal

from functools import partial
import pyproj

import numpy as np
import os
import time
import glob

# AWS s3 handling
import boto3
from botocore.exceptions import ClientError

AWSREGION='ap-southeast-2'

def transformgeom(geometry, fromcrs, tocrs):
    """
    convert geometries
    needs:
    - a shapely geometry
    - 'from' proj string
    - 'to' proj string

    returns:
    -shapely geometry in 'to' coordinates
    """
    project = partial(
        pyproj.transform,
        pyproj.Proj(init=fromcrs),  # source coordinate system
        pyproj.Proj(init=tocrs))  # destination coordinate system

    return transform(project, geometry)

def openjsonindex(jsonindex):
    """
    Utility function to read a JSON file into memory as a dictionary

    """

    if 's3://' in jsonindex[0:5]:
        """
        s3 path is the default,
        """
        bits = jsonindex.split("/")
        bucketname = bits[2]
        pathtofile = "/".join(bits[3:])
        #print(pathtofile)
        conn = boto3.client('s3', AWSREGION)  # again assumes boto.cfg setup, assume AWS S3
        result = conn.get_object(Bucket=bucketname, Key=pathtofile)
        # read the image index into a dictionary
        indexjson = json.loads(result["Body"].read().decode())

    else:
        with open(jsonindex, 'r') as infile:
            indexjson=json.load(infile)

    return(indexjson)

def chooseairphotos(airphotoindex, mapgridsquare):
    """
    input:
    - a dictionary of airphoto paths and bounding geometries
    - a single map grid tile geometry

    ouput:
    - an array of file locations which intersect the tile
    """
    #mapgridsquare= shape(maptile["geometry"])

    filelist=[]
    #print(mapgridsquare)
    for image in airphotoindex["features"]:
        #print(shape(image["bbox"]))
        if shape(mapgridsquare).intersects(shape(image["geometry"])):
            filename = image["properties"]["filename"]
            #print(filename)
            if 's3://' in filename[0:5]:
                filename = filename.replace('s3://', '/vsis3/')
            filelist.append(filename)
        """
        if mapgridsquare.contains(shape(image["bbox"])):
            filename = image["filename"]
            if 's3://' in filename[0:5]:
                filename = filename.replace('s3://', '/vsis3/')
            filelist.append(filename)
        """
    print("images in set: {}".format(len(filelist)))
    if len(filelist) == 0:
        filelist=None
    print(filelist)
    return(filelist)

def createnativemosaic(filelist, nativemosaic, resample='lanczos',  mosaictype='vrt'):
    """
    input is an array of file addresses, a location to place output,
    and a resampling method.

    writes a VRT to the specified location
    """
    print("building native CRS mosaic")
    #GDAL understands the /vsis3/ driver, niot s3 urls:
    # https://www.gdal.org/gdal_virtual_file_systems.html
    if 's3://' in nativemosaic:
        nativemosaic = nativemosaic.replace('s3://', '/vsis3/')

    vrtoptions= gdal.BuildVRTOptions(resampleAlg=resample, addAlpha=True)
    myvrt= gdal.BuildVRT(nativemosaic, filelist, options=vrtoptions)
    myvrt.FlushCache()
    myvrt= None

    return(nativemosaic)

def createwarpedmosaic(nativemosaic, warpedmosaic, bbox, incrs='EPSG:28355', outcrs='EPSG:4236', resample='lanczos'):
    """
    input is the native-CRS VRT made with buildvrt
    output is a warped or geotiff, determined by the extension provided on the
    output file name.
    """

    print("writing warped and clipped mosaic to be used for tiling")
    bbox = np.around(bbox, decimals=1)

    if 's3://' in nativemosaic:
        nativemosaic = nativemosaic.replace('s3://', '/vsis3/')

    if 's3://' in warpedmosaic:
        warpedmosaic = warpedmosaic.replace('s3://', '/vsis3/')

    print(nativemosaic)
    print(warpedmosaic)

    warpoptions= gdal.WarpOptions(resampleAlg=resample,
                                      outputBounds=bbox,
                                      srcSRS=incrs,
                                      dstSRS=outcrs,
                                      dstAlpha=True)

    warpedfile= gdal.Warp(warpedmosaic, nativemosaic, options=warpoptions)
    warpedfile.FlushCache
    warpedfile = None

    return(warpedmosaic)

def buildamosaic(gridsquare, imagejson, mosaicstore, incrs, outcrs, resample='lanczos'):

    #print(gridsquare)
    #transform each map grid square to image CRS
    gridsquaregeom = shape(gridsquare["geometry"])

    # this statement looks reversed - recall we're transforming map grid tiles from the
    # systems 'outpout' CRS (WGS84) to the image tile 'input' CRS (usually MGA94 or GDA2020)
    # so this syntactically backward looking transformation needs to stay
    print("gridsquare: {}".format(gridsquaregeom))
    tgridsquare = transformgeom(gridsquaregeom, outcrs, incrs)
    print("tgridsquare: {}".format(tgridsquare))
    print("from CRS: {}; to crs: {}".format(outcrs, incrs))


    # get the bbox for this grid square, clip it to 1 decimal place
    bbox = gridsquaregeom.bounds
    bbox = np.around(bbox, decimals=1)

    mosaicname = mosaicstore + "/" + str(gridsquare["properties"]["OBJECTID"]) + "-maxzoom" + str(gridsquare["properties"]["maxzoom"])
    nativemosaic = mosaicname + '-native.vrt'
    warpedmosaic = mosaicname + '-warped'

    warpedmosaic = warpedmosaic + ".vrt"

    # see if any images intersect this map grid square
    filelist = chooseairphotos(imagejson, tgridsquare)

    if filelist:
        #create a native CRS mosaic
        createnativemosaic(filelist, nativemosaic)
        #wait just a moment...
        time.sleep(0.5)
        # use the native mosaic as a base dataset for a warped and clipped mosaic
        createwarpedmosaic(nativemosaic, warpedmosaic, bbox, incrs, outcrs, resample)
        print("images: {} ".format(len(filelist)))
    else:
        print('no image tiles intersected grid square {}'.format(str(gridsquare["properties"]["OBJECTID"])))

    return

def buildallthemosaics(mapgridindex, imagejson, mosaicstore, incrs, outcrs, resample='lanczos', mosaictype="vrt"):
    """
    loops over mapgridindex and cuts a mosaic for each geometry it contains
    """
    #print(incrs)
    #print(outcrs)
    if not "s3://" in mosaicstore[0:5]:
        if not os.path.exists(mosaicstore):
            os.makedirs(mosaicstore)

    print("mapgridindex: {}".format(mapgridindex))

    mapgridjson = openjsonindex(mapgridindex)
    #print(mapgridjson)
    #for gridsquare in fiona.open(mapgridindex, 'r'):
    for gridsquare in mapgridjson["features"]:

        gridid = gridsquare["properties"]["OBJECTID"]
        #print("mapgridinex geometry: {} ".format(shape(gridsquare["geometry"])))
        gridsquaregeom = shape(gridsquare["geometry"])
        #print("resampling: {}".format(resample))
        metadata = buildamosaic( gridsquare, imagejson, mosaicstore, incrs, outcrs, resample)

    return

def buildmosaics(*args):
    """
    management function to handle CLI calls
    """

    imagejson = openjsonindex(imageindex)

    mapgridjson = openjsonindex(mapgridindex)

    if mapgridid is not None:
    #build the mosaic for one square
        for gridsquare in mapgridjson["features"]:

            #build a warped raster for one map grid square
            if gridsquare["properties"]["OBJECTID"] == int(mapgridid):

                buildamosaic( gridsquare, imagejson, mosaicstore, in_crs, out_crs, resample='lanczos')

    else:
    #build all the mosaics
        buildallthemosaics( mapgridindex, imagejson, mosaicstore, in_crs, out_crs, resample='lanczos', mosaictype="vrt")

    return

if __name__ == '__main__':
    # cli handling parts -
    # accept a test and reference polygon
    parser = ArgumentParser()

    parser.add_argument("-i", "--imageindex",
                        help="image index",
                        required=True)

    parser.add_argument("-o", "--outputlocation",
                        help="where to put mosaics",
                        required=True)

    parser.add_argument("-r", "--referenceindex",
                        help="location of the reference map grid squares as a GeoJSON file",
                        required=True)

    parser.add_argument("-m", "--mapgridid",
                        help="map grid square number",
                        default=None)

    parser.add_argument("-in_crs", "--in_crs",
                        help="input CRS",
                        default="EPSG:28355",
                        required=False)

    parser.add_argument("-out_crs", "--out_crs",
                        help="output CRS",
                        default="EPSG:4326",
                        required=False)

    # unpack arguments
    args = parser.parse_args()

    imageindex = vars(args)["imageindex"]
    mapgridindex = vars(args)["referenceindex"]
    mapgridid = vars(args)["mapgridid"]
    mosaicstore = vars(args)["outputlocation"]
    in_crs = vars(args)["in_crs"]
    out_crs = vars(args)["out_crs"]

    buildmosaics(imageindex, mapgridindex,  mosaicstore, mapgridid, in_crs, out_crs)
