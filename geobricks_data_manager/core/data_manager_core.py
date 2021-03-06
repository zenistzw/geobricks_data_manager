import os
from geobricks_geoserver_manager.core.geoserver_manager_core import GeoserverManager
from geobricks_metadata_manager.core.metadata_manager_d3s_core import MetadataManager
from geobricks_storage_manager.core.storage_manager import StorageManager
from geobricks_data_manager.core.metadata_bridge import translate_from_metadata_to_geoserver, add_metadata_from_raster
from geobricks_data_manager.core.data_manager_syncronization import check_metadata
from geobricks_common.core.log import logger
from geobricks_common.core.filesystem import sanitize_name

log = logger(__file__)


class DataManager():

    metadata_manager = None
    geoserver_manager = None
    storage_manager = None

    def __init__(self, config):

        # settings
        self.config = config

        # uid separator if not defined
        if "folders" in config["settings"]:

            self.uid_separator = config["settings"]["folders"]["workspace_layer_separator"] if "workspace_layer_separator" in config["settings"]["folders"] else ":"

        # TODO: add only stuff used by MetadataManager?
        self.metadata_manager = MetadataManager(config)
        # TODO: add only stuff used by GeoserverManager?
        self.geoserver_manager = GeoserverManager(config)
        # TODO: add only stuff used by FTPManager?
        self.storage_manager = StorageManager(config)


    ####### PUBLISH
    def publish_coveragestore(self, file_path, metadata_def, overwrite=False, publish_on_geoserver=True, publish_metadata=True, remove_file=False):
        """
        :param file_path: path to the input file
        :param metadata_def: json metadata
        :param overwrite: overwrite the resource
        :param publish_on_geoserver: publishing on Geoserver
        :param publish_metadata:  publishing on Metadata DB
        :param remove_file: remove the file the process is finished
        :return: ?
        """
        log.info("publish_coveragestore")
        try:
            # add additional layer info to the metadata i.e. bbox and EPSG code if they are not already added
            add_metadata_from_raster(file_path, metadata_def)
            # publish the coverage store
            return self._publish_coverage(file_path, metadata_def, overwrite, publish_on_geoserver, publish_metadata, remove_file)
        except Exception, e:
            raise Exception(e)

    def _publish_coverage(self, file_path, metadata_def, overwrite=False, publish_on_geoserver=True, publish_metadata=True, remove_file=False):
        """
        :param file_path: path to the input file
        :param metadata_def: json metadata
        :param overwrite: overwrite the resource
        :param publish_on_geoserver: publishing on Geoserver
        :param publish_metadata:  publishing on Metadata DB
        :param remove_file: remove the file the process is finished
        :return: ?
        """
        try:
            # Store type (geoserver, storage)
            if "datasources" not in metadata_def["dsd"]:
                metadata_def["dsd"]["datasources"] = ["geoserver"]

            # get the title, if EN exists otherwise get the first available key
            # TODO: how to do it better? default language? Should throw an Exception the fact that there is no Title?
            title = metadata_def["title"]["EN"] if "EN" in metadata_def["title"] else metadata_def["title"][metadata_def["title"].keys()[0]]

            # sanitize the layername. "layerName" has to be set
            metadata_def["dsd"]["layerName"] = sanitize_name(metadata_def["dsd"]["layerName"])
            layername = metadata_def["dsd"]["layerName"]

            # getting the default workspace if not storage
            if metadata_def["dsd"]["datasources"] == ["geoserver"]:
                metadata_def["dsd"]["workspace"] = metadata_def["dsd"]["workspace"] if "workspace" in metadata_def["dsd"] else self.geoserver_manager.get_default_workspace_name()

            # setting up the uid (checks if the workspace is set or not)
            if "uid" not in metadata_def:
                metadata_def["uid"] = (metadata_def["dsd"]["workspace"] + self.uid_separator + layername) if "workspace" in metadata_def["dsd"] else layername

            # publish on metadata
            if publish_metadata is True:
                log.info(metadata_def)
                self.metadata_manager.publish_metadata(metadata_def, overwrite)
                log.info("Metadata published")

            # publish table on geoserver cluster
            if publish_on_geoserver is True:
                log.info("publish_on_geoserver")
                # setting up geoserver metadata TODO: move it
                abstact = None
                defaultStyle = None
                try:
                    abstact = metadata_def["meContent"]["description"]["EN"]
                except Exception: pass
                try:
                    defaultStyle = metadata_def["dsd"]["defaultStyle"]
                except Exception: pass
                geoserver_def = translate_from_metadata_to_geoserver(layername, title, metadata_def["dsd"]["workspace"], None, defaultStyle, abstact)
                log.info(self.geoserver_manager)
                print self.geoserver_manager.gs_master
                print self.geoserver_manager.gs_master.username
                print self.geoserver_manager.gs_master.password
                self.geoserver_manager.publish_coveragestore(file_path, geoserver_def, overwrite)
                log.info("Geoserver published")

            # remove files and folder of the shapefile
            if file_path is not None and remove_file:
                removefile(file_path)

        except Exception, e:
            log.error(e)
            self.rollback_coveragestore()
            raise Exception(e)
        return metadata_def

    def publish_codelist(self):
        # if a code doesn't exist publish a new code associate to the codelist (TODO: How to hanglde the labels?)
        log.warn('TODO Implement it for "meSpatialRepresentation":{"processing": {"idCodeList": "FENIX_GeographicalProcessing", "version" : "1.0", "codes": [{"code": "AVG_MONTHLY"}]}')
        log.warn('TODO Implement it for "meContent":{"resourceRepresentationType":"geographic","seCoverage":{"coverageSectors":{"idCodeList":"FENIX_GeographicalSectors","version":"1.0","codes":[{"code":"MODIS_LAND_COVER"}]}}')

    def publish_featuretype(self, data):
        log.warn("TODO: publish_featuretype")

    def pulish_postgis_table(self, data):
        log.warn("TODO: publish_postgis_table")


    ####### DELETE

    def delete(self, uid, delete_metadata=True, delete_on_geoserver=True, delete_on_storage=True):
        try:
            metadata = self.metadata_manager.get_by_uid(uid)

            # Handle Raster delete
            if metadata["meSpatialRepresentation"]["layerType"] == "raster":
                self._delete_coveragestore(metadata, delete_metadata, delete_on_geoserver, delete_on_storage)

            # Handel Vector delete
            elif metadata["meSpatialRepresentation"]["layerType"] == "vector":
                # TODO: handle shp e postgis layer
                log.warn("handle delete vector layer")

            else:
                raise Exception("No meSpatialRepresentation.layerType found")
        except Exception, e:
            log.error(e)
            raise Exception(e)

        return True

    # TODO how to handle the storage problem?
    # TODO: call the metadata service before to delete on geoserver to be sure that is a published layer and
    # and not in storage
    def _delete_coveragestore(self, metadata, delete_metadata=True, delete_on_geoserver=True, delete_on_storage=True):
        '''
        :param metadata: resource metadata of the coveragestore
        :param delete_on_geoserver: delete the resource from Geoserver
        :param delete_metadata:  delete the resource from Metadata DB
        :param delete_on_storage:  delete the resource from Storage
        :return: ?
        '''
        log.info("DELETE", metadata)
        if delete_metadata:
            self._delete_metadata(metadata["uid"])

        # get layername from uid
        if delete_on_geoserver:
            self._delete_store_on_geoserver(metadata)

        if delete_on_storage:
            self._delete_on_storage(metadata)

    def _delete_metadata(self, uid):
        log.info("deleting metadata: " + uid)
        self.metadata_manager.delete_metadata(uid)
        log.info("Metadata removed: " + uid)

    def _delete_store_on_geoserver(self, metadata):
        if "datasources" in metadata["dsd"]:
            if metadata["dsd"]["datasources"] == ["geoserver"]:
                workspace = metadata["dsd"]["workspace"]
                layername = metadata["dsd"]["layerName"]
                # TODO: Get full metadata and delete it
                log.info("deleting on geoserver: " + layername)
                log.info(workspace + ":" + layername)
                self.geoserver_manager.delete_store(layername, workspace)
                log.info("Geoserver coveragestore removed: " + workspace + ":" + layername)

    def _delete_on_storage(self, metadata):
        if "datasources" in metadata["dsd"]:
            if metadata["dsd"]["datasources"] == ["storage"]:
                layername = metadata["dsd"]["layerName"]
                log.warn("TODO: to implement _delete_on_storage:" + layername)

    def delete_featuretype(self, uid, delete_on_geoserver=True, delete_metadata=True):
        '''
        :param uid: resource uid of the featuretype (layer)
        :param delete_on_geoserver: delete the resource from Geoserver
        :param delete_metadata:  delete the resource from Metadata DB
        :return: ?
        '''
        try:
            if delete_metadata:
                self.metadata_manager.delete_metadata(uid)
                log.info("Metadata removed:" + uid)
        except Exception, e:
            log.error(e)
            raise Exception(e)

        try:
            if delete_on_geoserver:
                layername = uid if self.uid_separator not in uid else uid.split(self.uid_separator)[1]
                #TODO: shouldn't be passed also the workspace to gsconfig delete?
                self.geoserver_manager.delete_layer(layername)
                log.info("Geoserver layer removed: " + layername)
        except Exception, e:
            log.error(e)
            raise Exception(e)

    # TODO Shoulde be merged the common parts with the normal publishing
    def publish_coveragestore_storage(self, file_path, metadata_def, overwrite=False, publish_on_storage=True, publish_metadata=True, remove_file=False):
        """
        :param file_path: path to the input file
        :param metadata_def: json metadata
        :param overwrite: overwrite the resource
        :param publish_on_storage: publishing on remote storage
        :param publish_metadata:  publishing on Metadata DB
        :param remove_file: remove the file the process is finished
        :return: ?
        """
        log.info("publish_coveragestore")
        try:
            # add additional layer info to the metadata i.e. bbox and EPSG code if they are not already added
            add_metadata_from_raster(file_path, metadata_def)
            # publish the coverage store
            return self._publish_coverage_storage(file_path, metadata_def, overwrite, publish_on_storage, publish_metadata, remove_file)
        except Exception, e:
            raise Exception(e)

    def _publish_coverage_storage(self, file_path, metadata_def=None, overwrite=False, publish_on_storage=True, publish_metadata=True, remove_file=False):
        """
        :param file_path: path to the input file
        :param metadata_def: json metadata
        :param overwrite: overwrite the resource
        :param publish_on_ftp: publishing on remote ftp
        :param publish_metadata:  publishing on Metadata DB
        :param remove_file: remove the file the process is finished
        :return: ?
        """
        try:
            # Datasource type (geoserver, storage)
            if "datasources" not in metadata_def["dsd"]:
                metadata_def["dsd"]["datasources"] = ["storage"]

            # sanitize the layername. "layerName" has to be set
            metadata_def["dsd"]["layerName"] = sanitize_name(metadata_def["dsd"]["layerName"])

            # setting up the uid TODO: only layerName?
            metadata_def["uid"] = metadata_def["dsd"]["layerName"]

            # publish on metadata
            if publish_metadata is True:
                log.info(metadata_def)
                self.metadata_manager.publish_metadata(metadata_def, overwrite)
                log.info("Metadata published")

            # publish table on geoserver cluster
            if publish_on_storage is True:
                self.storage_manager.publish_raster_to_ftp(file_path)
                log.info("Storage published")

            # remove files and folder of the shapefile
            if file_path is not None and remove_file:
                removefile(file_path)

        except Exception, e:
            log.error(e)
            self.rollback_coveragestore()
        return metadata_def

    ####### SEARCH (PROXY TO MetadataManager)

    def get_all_layers(self):
        '''
        :return: json containing the stored layers
        '''
        return self.metadata_manager.get_all_layers()

    def get_metadata_by_uid(self, uid):
        '''
        :param uid: uid of the resource
        :return: json containing the stored metadata
        '''
        return self.metadata_manager.get_by_uid(uid)


    # ROLLBACK
    def rollback_coveragestore(self):
        return "TODO rollback_coveragestore"

    def check_consistency(self):
        result = check_metadata(self)
        log.warn(result)
        return result



def removefile(file_path):
    if os.path.isfile(file_path):
        os.remove(file_path)