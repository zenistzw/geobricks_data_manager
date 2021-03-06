from geobricks_data_manager.config.config import config
from geobricks_data_manager.core.data_manager_core import DataManager

metadata_def = {
    "creationDate": 1416221596000,
    "meContent": {
        "resourceRepresentationType": "geographic",
        "seCoverage": {
            "coverageSectors": {
                "idCodeList": "FENIX_GeographicalSectors",
                "version": "1.0",
                "codes": [{"code": "storage_test"}]
            },
            "coverageTime": {
                "to": 949276800000,
                "from": 946684800000
            }
        }
    },
    "meSpatialRepresentation": {
        "processing": {
            "idCodeList": "FENIX_GeographicalProcessing",
            "version" : "1.0",
            "codes": [{"code": "AVG_MONTHLY"}]
        },
        "seDefaultStyle": {"name": "ghg_cultivation_organic_soils_cropland"},
        "layerType": "raster"
    },
    "title": {"EN": "Cultivation Organic Soils - Croplands"},

    "dsd": {
        "contextSystem": "FENIX",
        "datasource" : "geoserver",
        "workspace": "dajeforte",
        "layerName": "test_modis",
        "defaultStyle": "raster_style_modis"
    }
}
metadata_def["uid"] = metadata_def["dsd"]["workspace"] + "@" + metadata_def["dsd"]["layerName"]

path = "../test_data/MODIS/MOD13A2/MOD13A2_3857.tif"

data_manager = DataManager(config)

# Publish coveragestore
data_manager.publish_coveragestore(path, metadata_def)

# Remove coveragestore
try:
    #data_manager.delete_coveragestore(metadata_def["uid"])
    print "here"
except Exception, e:
    print e

