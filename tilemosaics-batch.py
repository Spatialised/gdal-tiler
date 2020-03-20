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
 
import os, sys 
 
import glob 
 
import re 
 
import json 
 
import boto3 
from botocore.exceptions import ClientError 
 
# from multiprocessing import Pool 
 
#from tilecutter_batch import tilecutter 
 
AWSREGION = 'ap-southeast-2' 
 
# attempting to fix the intermittent bug with reading from VRTS 
# in AWS... 
os.environ['VRT_SHARED_SOURCE'] = '0' 
 
# this env variable stops GDAL writing aux.xml files 
os.environ['GDAL_PAM_ENABLED'] = 'NO' 
 
# Constants 
BATCH_JOB_QUEUE_ID = 'JobQueue-8a86c0393ac32e7' 
BATCH_JOB_QUEUE_DEFINITION = 'TileCutterJobDef-119affa6ecd2b37' 
 
# do we need to parse arguments... 
# yes! if we're calling from the CLI 
from argparse import ArgumentParser 
 
# def runcutter(jobdef): 
#     print(jobdef) 
#     tilecutter(jobdef[0], jobdef[1], jobdef[2], jobdef[3]) 
 
#     return 
 
 
def tilemosaics(gridconfigfile, mosaicstore, tilestore, minzoom): 
 
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
 
    batch = boto3.client('batch', region_name=AWSREGION) 
 
    # iterate over the list of mosaics and set up zoom levels plus output dir 
    for vrt in vrtlist: 
        # which vrt? 
        #print(vrt) 
 
        #extract max zoom from filename - is this an OK strategy or should be held some other place? 
        findmaxzoom = re.search('zoom[0-9]{2}', vrt) 
        maxzoomstring = findmaxzoom.group() 
        maxzoom = maxzoomstring[-2:] 
 
        # for each zoom level between input minzoom and derived maxzoom: 
        #for zoomlevel in reversed(range(int(minzoom), int(maxzoom)+1)): 
        for zoomlevel in range(int(minzoom), int(maxzoom)+1): 
            #set up an output directory 
            tileout = tilestore + '/' + '4326_cad5_bbox_' + str(zoomlevel) 
                
            if zoomlevel <= 13:
                memory = 64000
            elif zoomlevel >= 14 and zoomlevel <= 19:
                memory = 16000
            else: 
                print("Invalid Zoom level")

            # Run job in batch 
            containerOverrides = { 
                # 'vcpus': 123, 
                'memory': memory, 
                'environment': [ 
                    {'name': 'GRID_CONFIGURATION', 'value': gridconfigfile}, 
                    {'name': 'INPUT_MOSAIC', 'value': vrt}, 
                    {'name': 'ZOOM_LEVEL', 'value': str(zoomlevel)}, 
                    {'name': 'OUTPUT_TILE_STORE', 'value': tileout} 
                ] 
            } 
 
            vrt_basename = os.path.basename(vrt) 
            batchJobName = os.path.splitext(vrt_basename)[0] + "_" + str(zoomlevel) 
            print("Scheduling job: " + batchJobName) 
 
            try: 
                response = batch.submit_job(jobQueue=BATCH_JOB_QUEUE_ID, jobName=batchJobName, jobDefinition=BATCH_JOB_QUEUE_DEFINITION, 
                                        containerOverrides=containerOverrides) 
 
                print("Scheduled " + str(response)) 
            except Exception as e: 
                print(e) 
 
                # Comment this out if script should continue despite failure 
                raise Exception(e) 
 
            # jobconfig.append({ 
            #     "GRID_CONFIG_FILE": gridconfigfile,  
            #     "VRT": vrt,  
            #     "ZOOM_LEVEL": zoomlevel,  
            #     "TILE_OUTPUT_DIR": tileout 
            # }) 
 
 
    # print(jobconfig[0:10]) 
 
    # import csv 
 
    # with open ('../jobconfig.csv', 'w') as file: 
    #     writer = csv.writer(file) 
    #     for row in jobconfig: 
    #         file.write(str(row)) 
 
     
    # with Pool(int(cores)) as p: 
    #     p.map(runcutter, jobconfig[:]) 
 
 
####################################################### 
## does this cli block need to be in place at all? 
 
"""
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
 
    # unpack arguments 
    args = parser.parse_args() 
"""    
 
gridconfigfile = os.environ['GRID_CONFIG_FILE']
mosaicstore = os.environ['MOSAIC_OUTPUT']
tilestore = os.environ['OUTPUT_BUCKET']

 
minzoom = 11 
 
try: 
    tilemosaics(gridconfigfile, mosaicstore, tilestore, minzoom) 
except Exception as e: 
    print(e) 
    sys.exit(1) 
