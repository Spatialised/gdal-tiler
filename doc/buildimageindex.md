# buildimageindex

creates a JSON file which holds input aerial image tile bounds in their native CRS

#### Input parameters

`-i [string]`: the full path to a directory of Geotiff image files

`-o [string]`: the full path to an output directory to hold an index file

`-f [string]`: the name of the JSON index file emitted by this process

#### Runs like:

`python3 buildimageindex.py -i "/path/to/2018_Canberra_10cm_example_1km_MGA55_Tiles/" -o "/path/to/index/" -f "./airphotos.json"`

...which writes out `airphotos.json`, containing image locations and bounds.

it will attempt to create the path in `-o`

to use s3:

`python3 buildimageindex.py -i "s3://bucketname/2018_Canberra_10cm_example_1km_MGA55_Tiles/" -o "s3://bucketname/path/" -f "airphotos.json"`

This will also attempt to create the bucket in `-o`

#### Notes

The output JSON file is not standard GeoJSON. A sample looks like:

```
images": [
    {
        "filename": "s3://2pi-spatialised-test-imagery/examples_of_old_imagery/2018_Canberra_10cm_example_1km_MGA55_Tiles/M5690608190318.tif",
        "bbox": {
            "type": "Polygon",
            "coordinates": [
                [
                    [
                        691000.000023,
                        6081000.0002230005
                    ],
                    [
                        691000.000023,
                        6082000.000223
                    ],
                    [
                        690000.000023,
                        6082000.000223
                    ],
                    [
                        690000.000023,
                        6081000.0002230005
                    ],
                    [
                        691000.000023,
                        6081000.0002230005
                    ]
                ]
            ]
        }
    },
```
