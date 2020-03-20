#!/usr/bin/python3

"""
Read a directory of GeoTIFF files, compute their bounding boxes
 and write out a JSON file containing a path to the file and a bounding box

# TO DO

Adam Steer
Spatialised :: http://spatialised.net
May 2019

For ACT ESA
"""
# do we need to parse arguments...
# yes! if we're calling from the CLI
from argparse import ArgumentParser

import glob
import logging
import os

import boto3
from botocore.exceptions import ClientError

import json

from osgeo import gdal
from shapely.geometry import mapping, box

AWSREGION='ap-southeast-2'

def buildimagedata(datapath):

    dataset = gdal.Open(datapath)
    print(datapath)
    imagedata = {}
    imagedata["properties"] = {}
    imagedata["properties"]["filename"] = datapath

    transform = dataset.GetGeoTransform()
    minx = transform[0]
    maxx = transform[0] + dataset.RasterXSize * transform[1]
    maxy = transform[3]
    miny = transform[3] - dataset.RasterYSize * transform[1]

    imagedata["geometry"] = {}
    imagedata["geometry"] = mapping(box(minx, miny, maxx, maxy))
    print("data: {}, miny: {}, maxy: {}".format(datapath, miny, maxy))

    return(imagedata)

#https://alexwlchan.net/2017/07/listing-s3-keys/
def get_all_s3_keys(bucket, prefix, connection):
    """Get a list of all keys in an S3 bucket."""
    keys = []

    kwargs = {'Bucket': bucket,
              'Prefix': prefix}
    while True:
        resp = connection.list_objects_v2(**kwargs)
        for obj in resp['Contents']:
            keys.append(obj['Key'])

        try:
            kwargs['ContinuationToken'] = resp['NextContinuationToken']
        except KeyError:
            break

    return keys

def createimageindex(imagerylocation):

    # set up a list to hold dicts of image bbox metadata:
    # imageindex[0]["filename"]: path to file on s3 or locally
    # imageindex[0]["geometry"]: shapely geometry describing image bbox

    #imagelist = []
    imagedata = {}

    imagejson = {}
    imagejson["name"] = "act-esa-airphotos"
    imagejson["type"] = "FeatureCollection"
    imagejson["features"] = []

    if 's3://' in imagerylocation[0:5]:
        """
        s3 path is the default,
        """
        print(imagerylocation)
        bits = imagerylocation.split("/")
        bucketname = bits[2]
        print(bits)
        theconn = boto3.client('s3', AWSREGION)
        print(bucketname)

        if len(bits) > 3:
            pathparts = bits[3:]
            print(bits[3:-1])
            startafter = "/".join(bits[3:-1])
        else:
            startafter="/"

        #print(startafter)

        listofimages = get_all_s3_keys(bucketname, startafter, theconn)

        #for key in theconn.list_objects(Bucket=bucketname, Prefix=startafter, MaxKeys=100000)["Contents"]:
        for key in listofimages:

            #if '.tif' in key['Key'][-4:]:
            if '.tif' in key[-4:]:
                print(key)
                #print(key['Key'])

                datapath = "/vsis3/" + bucketname + "/" + key
                #datapath = "/vsis3/" + bucketname + "/" + key["Key"]

                imagedata = buildimagedata(datapath)

                imagejson["features"].append(imagedata)

    else:
        """
        local path, use glob
        """
        # local filesystem version
        for key in glob.glob(imagerylocation + "*"):
            if '.tif' in key[-4:]:
                datapath = key

                imagedata = buildimagedata(datapath)

                imagejson["features"].append(imagedata)

    #print(imagelist)
    return(imagejson)


def writeimagejson(imagejson, location, filename):

    print(filename)

    #print(imagejson)
    #write the index to a JSON file
    if "s3://" in location[0:5]:
        bits = location.split("/")
        bucketname = bits[2]
        print(bucketname)

        pathtofile= "/".join(bits[3:])
        filename = "/".join([pathtofile, filename])
        print(filename)

        s3 = boto3.client('s3', AWSREGION)  # again assumes boto.cfg setup, assume AWS S3

        try:
            s3.put_object(Body=json.dumps(imagejson), Bucket=bucketname, Key=filename)
        except ClientError as e:
            logging.error(e)

    else:
        if not os.path.exists(location):
            os.makedirs(location)

        with open(location + "/" + filename, 'w') as outfile:
            json.dump(imagejson, outfile)

    return(location + "/" + filename)


def buildimageindex(imagerylocation, outputlocation, indexname):

    airphotos = createimageindex(imagerylocation)
    writeimagejson(airphotos, outputlocation, indexname)

    return

if __name__ == '__main__':
    # cli handling parts -
    # accept a test and reference polygon
    parser = ArgumentParser()
    parser.add_argument("-i", "--imagerylocation",
                        help="location of aerial photos as geoTIFFs",
                        required=True)

    parser.add_argument("-o", "--outputlocation",
                        help="where to put the imagery index",
                        required=True)

    parser.add_argument("-f", "--filename",
                        help="what to call the index",
                        required=True)

    # unpack arguments
    args = parser.parse_args()

    imagerylocation = vars(args)["imagerylocation"]
    outputlocation = vars(args)["outputlocation"]
    indexname = vars(args)["filename"]

    buildimageindex(imagerylocation, outputlocation, indexname)
