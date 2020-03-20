#!/usr/bin/python3
"""
Produces PNG tiles conforming to an ACT ESA geowebcache grid schema from 0.1 x 0.1 degree
 (WGS84) virtual mosaics.

Much of this code is based on gdal2tiles.py:


...with a lot of extra parts removed.

Adam Steer
Spatialised :: http://spatialised.net
May 2019
"""

from osgeo import gdal
gdal.AllRegister()

import numpy as np

import os

import json

import boto3
from botocore.exceptions import ClientError

AWSREGION = 'ap-southeast-2'

# this env variable stops GDAL writing aux.xml files
os.environ['GDAL_PAM_ENABLED'] = 'NO'

# do we need to parse arguments...
# yes! if we're calling from the CLI
from argparse import ArgumentParser


def genoffsets(zoom, mapgridconf):
    """
    sets column and row offsets for the web map tile gridding schema

    input:
    - zoom level (int)
    - dictionary of map grid conf data

    ouput:
    - column and row offsets
    - file name padding length
    """

    xmin = mapgridconf["gridbounds"]["xmin"]
    ymin = mapgridconf["gridbounds"]["ymin"]

    chips = ntiles(int(zoom), int(mapgridconf["gridoffsets"]["zoom"]))

    # compute length of a chip, or slippy map tile, in degrees
    chiplength = mapgridconf["gridoffsets"]["side"] / np.sqrt(chips)

    # computing offsets. For our zoom level, offset is:
    # (full grid / chipsize) - (thishalf-minx / chipsize)
    # (360 ÷ 0.1) − ((180−148) ÷ 0.1)
    coloff = int((360 / chiplength) - ((180-xmin) / chiplength))
    #
    # (90÷ 0.1) − ((90−(90−36.5)) ÷ 0.1)
    rowoff = int(abs((90 / chiplength) - ((90-(90-abs(ymin))) / chiplength)))

    # grid 0, 0 is at geo -180, -90. Rows and cols are counted
    # positive right from -180, positive up from -90.

    # get the length of the biggest number number
    padsizer = max([len(str(coloff)), len(str(rowoff))])

    # make some rules about how long column and row ID
    # numbers should be  - these were empirically determined
    # from an ACT ESA sample dataset
    if (zoom == 19) or (zoom == 18):
        padsizer = padsizer+2
    elif (zoom == 12):
        padsizer = padsizer+2
    elif (padsizer % 2 == 0):
        padsizer = padsizer
    else:
        padsizer = padsizer+1

    print("offsets from conf file - col: {}; row: {}".format(coloff, rowoff))
    return coloff, rowoff, padsizer

# this function computes pixel coordinates from geo coordinates
# from gdal2tiles.py
def geo_query(ds, ulx, uly, lrx, lry):
    """
    For given dataset and query in cartographic coordinates returns parameters for ReadRaster()
    in raster coordinates and x/y shifts (for border tiles). If the querysize is not given, the
    extent is returned in the native resolution of dataset ds.
    raises Gdal2TilesError if the dataset does not contain anything inside this geo_query
    """
    geotran = ds.GetGeoTransform()
    #print("geotran: {}".format(geotran))
    #print("ulx: {}, uly {}: ".format(ulx, uly))
    #print("lrx: {}, lry {}: ".format(lrx, lry))

    # pixel offsets for clipped area
    rx = int((ulx - geotran[0]) / geotran[1] + 0.001)
    ry = int((uly - geotran[3]) / geotran[5] + 0.001)

    # size of clipped area
    rxsize = int((lrx - ulx) / geotran[1] + 0.5)
    rysize = int((lry - uly) / geotran[5] + 0.5)

    # set the buffer size
    wxsize, wysize = rxsize, rysize

    # Coordinates should not go out of the bounds of the raster
    # wx and wy are where to put data in the output raster, these should always be zero for us
    wx = 0
    wy = 0

    # yoffsets should be always positive
    ry = abs(ry)

    #print("clipping rx: {} ry: {} rxsize {} rysize {}".format(rx, ry, rxsize, rysize))

    return (rx, ry, rxsize, rysize), (wx, wy, wxsize, wysize)


def ntiles(zoomlevel, basezoomlevel):
    """
    compute the number of tiles for this zoom level
    """
    if zoomlevel > basezoomlevel:
        zoompower = zoomlevel - basezoomlevel
        tiles = 4**zoompower
    elif zoomlevel == basezoomlevel:
        tiles = 1
    else:
        raise ValueError("zoom level {} cannot be computed with base zoom {}".format(
            zoomlevel, basezoomlevel))

    return tiles


def tilebboxes(bbox, zoomlevel, mapgridconf):
    """
    generate an index of lat lon bboxes for each tile
    along with row, column offsets for the chip naming
    scheme

    inputs:
    bbox: this grid sqaure bbox
    zoomlevel: this zoom level
    mapgridconf: dictionary of data from the grid and dataset conf file

    """
    # flatten grid square bbox to 1 decimal place
    bbox = np.around(bbox, decimals=1)
    print("bbox for tile bboxes: {}".format(bbox))

    # how many chips (tiles) do we need to make for this zoom level
    chips = ntiles(int(zoomlevel), int(mapgridconf["gridoffsets"]["zoom"]))

    # make xmin ymin xmax ymax from the grid square bbox
    xmin = bbox[0]
    ymin = bbox[1]
    xmax = bbox[2]
    ymax = bbox[3]

    # compute length of a chip, or slippy map tile, in degrees
    xchiplength = (xmax-xmin) / np.sqrt(chips)
    ychiplength = (ymax-ymin) / np.sqrt(chips)

    # where do slippy map tiles start, in degrees. these arrays
    # hold LOWER LEFT corners
    xchipsrange = np.arange(xmin, xmax, xchiplength)
    ychipsrange = np.arange(ymin, ymax, ychiplength)

    #print("xchipsrange: {}, len: {}".format(xchipsrange, len(xchipsrange)))
    #print("ychipsrange: {}, len: {}".format(ychipsrange,len(ychipsrange)))
    # print(np.diff(ychipsrange))
    # print(len(ychipsrange))

    # logic here to figure out columns from grid xmin/ymin to dataset xmin/ymin
    # this adds extra colums and rows depending on the distance of this data from
    # the gridset origins / column offsets
    col = np.abs(xmin - mapgridconf["gridbounds"]["xmin"]) / xchiplength

    row = np.abs(ymin - mapgridconf["gridbounds"]["ymin"]) / ychiplength

    print("col: {}; row {}: ".format(col, row))

    #print("tilecol: {}; tilerow {}: ".format(
    #    col + mapgridconf["gridoffsets"]["coloffset"], row + mapgridconf["gridoffsets"]["rowoffset"]))

    #set an initialing value for each loop around col, for row...
    rowstart = row
    tilebboxes = []
    # compute an array of tile bounds in geographic space
    for xchip in xchipsrange:
        # reset each row..
        row = rowstart
        for ychip in ychipsrange:
            tilebox = [xchip, ychip, xchip + xchiplength, ychip + ychiplength, col, row]
            tilebboxes.append(tilebox)
            row += 1
        col += 1

    return tilebboxes

def tilenamer(col, row, padding):
    """
    figure out what to call tiles...
    keep the maths simple, this has to go fast

    takes in some infomation about the grid spec and tile,
    returns a tile path relative to it's zoom level parent

    """
    col = np.around(col)
    row = np.around(row)
    if padding == 4:
        tilename = "{0:04d}_{1:04d}".format(int(col), int(row))
    elif padding == 6:
        tilename = "{0:06d}_{1:06d}".format(int(col), int(row))
    elif padding == 8:
        tilename = "{0:08d}_{1:08d}".format(int(col), int(row))

    # colnumber,rownumber,tilename=column_row_file_name(rownumber,colnumber,coloffset,rowoffset,padding)
    #print("CN: {} ; RN: {} ; tilename: {}".format(colnumber, rownumber, tilename))

    return(tilename)

def directorynamer(zoomlevel, bbox):
    """
    Construct a directory for holding tiles based on the tile bbox

    hopefully some clearer logic springs out here, the rules below are a bit
    handrollic
    """
    degreesperdir = {
                    11: 6.4,
                    12: 6.4,
                    13: 3.2,
                    14: 3.2,
                    15: 1.6,
                    16: 1.6,
                    17: 0.8,
                    18: 0.8,
                    19: 0.4,
                    20: 0.4
                    }

    xgrid = np.floor((180 + bbox[0]) / degreesperdir[zoomlevel] )
    ygrid = np.floor((90 - abs(bbox[1])) / degreesperdir[zoomlevel])

    xgrid = str(int(xgrid))
    ygrid = str(int(ygrid))

    if zoomlevel == 12 or zoomlevel == 18 or zoomlevel == 19 or zoomlevel == 20:
        xgrid = "0" + xgrid
        ygrid = "0" + ygrid

    if zoomlevel > 11:
        if len(xgrid) < 3:
            xgrid = xgrid.zfill(3)
        if len(ygrid) < 3:
            print(len(ygrid))
            ygrid = ygrid.zfill(3)

    if zoomlevel == 11 and len(ygrid) < 2:
        ygrid = ygrid.zfill(2)

    if zoomlevel == 18 and len(ygrid) < 4:
        ygrid = ygrid.zfill(4)

    tiledir = xgrid + "_" + ygrid

    return(tiledir)

# scale clipped pixels to tile dimensions
# from gdal2tiles.py
def tilescaler(dsquery, dstile, resampling='lanczos', tilefilename=''):
    """
    scale a clipped raster to an output tile size

    inputs:

    dsquery: an in-memory gdal dataset object, clipped to xsize/ysize
    dstile: an empty in-memory gdal dataset, with dims == tilesize
    resampling: resmapling algorithm , defaults to lanczos
    tilefilename: not used here.

    output:
     dstile: an in-memory gdal dataset object filled with resampled pixels
    """

    querysize = dsquery.RasterXSize
    tile_size = dstile.RasterXSize
    tilebands = dstile.RasterCount

    if resampling == 'near':
        gdal_resampling = gdal.GRA_NearestNeighbour

    elif resampling == 'bilinear':
        gdal_resampling = gdal.GRA_Bilinear

    elif resampling == 'cubic':
        gdal_resampling = gdal.GRA_Cubic

    elif resampling == 'cubicspline':
        gdal_resampling = gdal.GRA_CubicSpline

    elif resampling == 'lanczos':
        gdal_resampling = gdal.GRA_Lanczos

    dsquery.SetGeoTransform((0.0, tile_size / float(querysize), 0.0, 0.0, 0.0,
                             tile_size / float(querysize)))
    dstile.SetGeoTransform((0.0, 1.0, 0.0, 0.0, 0.0, 1.0))

    res = gdal.ReprojectImage(dsquery, dstile, None, None, gdal_resampling)
    if res != 0:
        exit_with_error("ReprojectImage() failed on %s, error %d" % (tilefilename, res))


# this is called as a command line program
def tilecutter(gridconfigfile, sourcemosaic, zoomlevel, tilebasedir=None, tilesize=256):
    """
    methods for cutting input mosaics into slippy map tiles

    roughly analogous to gdal2tiles.py 'create base tiles' method, with excess parts
    removed and some bespoke grid / tile naming computation.


    """
    print(zoomlevel)
    # read the grid configuration
    if 's3://' in gridconfigfile[0:5]:
        """
        s3 path is the default,
        """
        bits = gridconfigfile.split("/")
        bucketname = bits[2]
        pathtofile = "/".join(bits[3:])
        print(pathtofile)
        print(bucketname)
        conn = boto3.client('s3', AWSREGION)  # again assumes boto.cfg setup, assume AWS S3
        result = conn.get_object(Bucket=bucketname, Key=pathtofile)
        # read the image index into a dictionary
        try:
            mapgridconf = json.loads(result["Body"].read().decode())
        except ValueError as err:
            print(err)

    else:
        try:
            with open(gridconfigfile, 'r') as infile:
                mapgridconf = json.load(infile)
        except ValueError as err:
            print(err)

    print(mapgridconf["gridoffsets"])
    # read the source mosaic, using GDAL's vsis3 virtual filesystem
    if "s3://" in sourcemosaic[0:5]:
        sourcemosaic = sourcemosaic.replace('s3://', '/vsis3/')

    # check whether to put tiles in S3 or locally
    if "s3://" in tilebasedir[0:5]:
        bucketname = tilebasedir[5:]
        tilebasedir = tilebasedir.replace('s3://', '/vsis3/')
    else:
        # local version
        if not os.path.exists(tilebasedir):
            os.makedirs(tilebasedir)

    # open the source mosaic and grab some metadata
    try:
        dataset = gdal.Open(sourcemosaic, gdal.GA_ReadOnly)
    except ValueError as err:
        print(err)

    transform = dataset.GetGeoTransform()

    print(transform)
    # compute bounding box for this map grid square
    minx = transform[0]
    maxx = transform[0] + dataset.RasterXSize * transform[1]
    miny = transform[3] - dataset.RasterYSize * transform[1]
    maxy = transform[3]

    # create bounds for the source mosaic
    mosaicbbox = [minx, miny, maxx, maxy]
    print("mosaic bounds: {}".format(mosaicbbox))
    mosaicheight = dataset.RasterXSize

    # generate tile bounding boxes for this zoom level in geo coordinates
    tilebounds = tilebboxes(mosaicbbox, zoomlevel, mapgridconf)

    # read the alpha band and compute a band number.
    alphaband = dataset.GetRasterBand(1).GetMaskBand()
    if ((alphaband.GetMaskFlags() & gdal.GMF_ALPHA) or
            dataset.RasterCount == 4 or
            dataset.RasterCount == 2):
        nbands = dataset.RasterCount - 1

    # set up GDAL drivers that we need
    mem_drv = gdal.GetDriverByName('MEM')
    out_drv = gdal.GetDriverByName('PNG')

    # generate tile naming base offsets for this zoom level.
    # this creates offsets to the lower left corner of the complete imagery
    # dataset, given in mapgridconf - but also likely compute-able from the
    # airphoto index

    coloffset, rowoffset, padding = genoffsets(int(zoomlevel), mapgridconf)

    #print(coloffset, rowoffset, padding)

    for bbox in tilebounds:

        print('bounds (minx, miny, maxx, maxy, col, row): {}'.format(bbox))
        print("chip bounds: {}".format(bbox))
        rb, wb = geo_query(dataset, bbox[0], bbox[3], bbox[2], bbox[1])

        rx, ry, rxsize, rysize = rb
        wx, wy, wxsize, wysize = wb

        data = alpha = None
        # def tilenamer(colnumber, rownumber, coloffset, rowoffset, padding):
        tilename = tilenamer(coloffset + bbox[4], rowoffset + bbox[5], padding)
        dirname = directorynamer(int(zoomlevel), bbox)
        if not "/vsis3/" in tilebasedir:
            if not os.path.exists(tilebasedir + "/" + dirname):
                os.makedirs(tilebasedir + "/" + dirname)

        imgtilename = dirname + "/" + tilename + ".png"

        print(imgtilename)

        print("reading nodata mask")
        alpha = alphaband.ReadRaster(rx, ry, rxsize, rysize, wxsize, wysize)

        if alpha and int(alpha.count('\x00'.encode('ascii'))) != 0:
            print("incomplete tile, skipping")
            alpha = None
        else:

            print("creating in-memory tile")

            dstile = mem_drv.Create('', tilesize, tilesize, 4)

            print("reading tile data")

            data = dataset.ReadRaster(rx, ry, rxsize, rysize, wxsize,
                                      wysize, band_list=list(range(1, nbands + 1)))

            dsquery = mem_drv.Create('', rxsize, rysize, nbands+1)

            dsquery.WriteRaster(0, 0,  rxsize, rysize, data,
                                band_list=list(range(1, nbands + 1)))

            dsquery.WriteRaster(0, 0,  rxsize, rysize, alpha, band_list=[nbands+1])

            tilescaler(dsquery, dstile,
                       tilefilename=imgtilename)
            del dsquery

            del data

            out_drv.CreateCopy(tilebasedir + "/" + imgtilename, dstile, strict=0)

            del dstile

            print("tile {} created".format(imgtilename))


if __name__ == '__main__':
    # cli handling parts -
    # accept a test and reference polygon
    parser = ArgumentParser()

    parser.add_argument("-i", "--inputmosaic",
                        help="input mosaic",
                        required=True)

    parser.add_argument("-o", "--outputtilestore",
                        help="where to put mosaics",
                        required=True)

    parser.add_argument("-z", "--zoomlevel",
                        help="zoom level for this process",
                        required=True)

    parser.add_argument("-g", "--gridconfiguration",
                        help="grid configuration file",
                        required=True)

    parser.add_argument("-t", "--tilesize",
                        help="output tile size",
                        default=256,
                        required=False)

    # unpack arguments
    args = parser.parse_args()

    gridconfigfile = vars(args)["gridconfiguration"]
    mosaic = vars(args)["inputmosaic"]
    zoomlevel = vars(args)["zoomlevel"]
    tilestore = vars(args)["outputtilestore"]
    tilesize = vars(args)["tilesize"]

    tilecutter(gridconfigfile, mosaic, zoomlevel, tilestore, tilesize)
