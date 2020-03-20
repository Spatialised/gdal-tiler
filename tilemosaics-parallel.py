#!/usr/bin/python3
"""
tilemosaics.py assembles job specificiations to pass to Amazon batch

Adam Steer
Spatialised :: http://spatialised.net
May 2019
"""

from osgeo import gdal
gdal.AllRegister()

import numpy as np

import os

import glob

import re

import json

import boto3
from botocore.exceptions import ClientError

from multiprocessing import Pool

from tilecutter import tilecutter

AWSREGION = 'ap-southeast-2'

# this env variable stops GDAL writing aux.xml files
os.environ['GDAL_PAM_ENABLED'] = 'NO'

# attempting to fix the intermittent bug with reading from VRTS
# in AWS...
os.environ['VRT_SHARED_SOURCE'] = '0'

# do we need to parse arguments...
# yes! if we're calling from the CLI
from argparse import ArgumentParser

def runcutter(jobdef):
    print(jobdef)
    tilecutter(jobdef[0], jobdef[1], jobdef[2], jobdef[3])

    return


def tilemosaics(grdiconfigfile, mosaicstore, tilestore, minzoom, cores):

    # create an array to hold a list of mosaics for processing
    vrtlist = []

    # read the list of arrays from an s3:// mosaicstore or local filesystem
    if 's3://' in mosaicstore[0:5]:
        """
        s3 path is the default,
        """
        bits = mosaicstore.split("/")
        bucketname = bits[2]
        print(bits)
        s3 = boto3.resource("s3")
        print(bucketname)

        dirpath = ("/").join(bits[3:])

        print(dirpath)
        bucket = s3.Bucket(bucketname)

        for summary in bucket.objects.filter(Prefix = dirpath):
            if 'vrt' in summary.key:
                #if not 'ovr' in key['Key']:
                print(summary.key)
                if 'warped' in summary.key:
                    vrtlist.append('s3://' + bucketname + "/" + summary.key)
        print(vrtlist)

    else:
        """
        local path, use glob
        """
        print("checking for VRTs in {}".format(mosaicstore))
        # local filesystem version
        for key in glob.glob(mosaicstore + "/*"):
            #print(key)
            if 'warped' in key:
                vrtlist.append(key)

    # inspect list of mosaics to process
    #print(vrtlist)
    jobconfig = []
    # iterate over the list of mosaics and set up zoom levels plus output dir
    for vrt in vrtlist:
        # which vrt?
        #print(vrt)

        #extract max zoom from filename - is this an OK strategy or should be held some other place?
        findmaxzoom = re.search('zoom[0-9]{2}',  vrt)
        maxzoomstring = findmaxzoom.group()
        maxzoom = maxzoomstring[-2:]

        # for each zoom level between input minzoom and derived maxzoom:
        #for zoomlevel in reversed(range(int(minzoom), int(maxzoom)+1)):
        for zoomlevel in range(int(minzoom), int(maxzoom)+1):
            #print(zoomlevel)
            tileout = ''
            #set up an output directory
            tileout = tilestore + '/' + '4326_cad5_bbox_' + str(zoomlevel)

            # start a tiling job
            #gridconfigfile, vrt, zoomlevel, tilestore)

            jobconfig.append([gridconfigfile, vrt, zoomlevel, tileout])



    print(jobconfig[0:10])

    import csv

    with open ('../jobconfig.csv', 'w') as file:
        writer = csv.writer(file)
        for row in jobconfig:
            file.write(str(row))


    with Pool(int(cores)) as p:
        p.map(runcutter, jobconfig[:])


#######################################################
## does this cli block need to be in place at all?

if __name__ == '__main__':
    # cli handling parts -
    # accept a test and reference polygon
    parser = ArgumentParser()

    parser.add_argument("-m", "--mosaicstore",
                        help="input mosaic",
                        required=True)

    parser.add_argument("-o", "--outputtilestore",
                        help="where to put mosaics",
                        required=True)

    parser.add_argument("-g", "--gridconfiguration",
                        help="grid configuration file",
                        required=True)

    parser.add_argument("-c", "--cores",
                        help="how many cpus",
                        required=True)


    # unpack arguments
    args = parser.parse_args()

    gridconfigfile = vars(args)["gridconfiguration"]
    mosaicstore = vars(args)["mosaicstore"]
    tilestore = vars(args)["outputtilestore"]
    cores = vars(args)["cores"]

    minzoom = 11

    tilemosaics(gridconfigfile, mosaicstore, tilestore, minzoom, cores)
