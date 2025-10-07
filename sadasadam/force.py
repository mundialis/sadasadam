#!/usr/bin/env python3
#
############################################################################
#
# MODULE:      force.py
# AUTHOR(S):   Momen Mawad, Guido Riembauer
#
# PURPOSE:     Handles FORCE processing and postprocessing of satellite data
# COPYRIGHT:   (C) 2023 by mundialis GmbH & Co. KG
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
############################################################################

# Developed and tested for FORCE version 3.7.11
import os
import shutil
from subprocess import Popen, PIPE
import tarfile
import warnings

from datetime import datetime
from multiprocessing import Pool
import requests
from osgeo import osr, gdal


def makedirs(directory):
    """Helper function to create a directory"""
    if not os.path.exists(directory):
        try:
            os.makedirs(directory)
        except Exception as exception:
            raise Exception(
                "Error during the creation "
                f"of the FORCE directory {directory}: {exception}"
            )
    else:
        warnings.warn(f"Directory {directory} already exists, skipping...")
    return directory


def get_wkt_from_epsg(epsg):
    """Helper function to get WKT from an EPSG code"""
    proj = osr.SpatialReference()
    proj.ImportFromEPSG(epsg)
    wkt = proj.ExportToWkt()
    return wkt


def update_band_description_from_reference(target_raster, reference_raster):
    """Helper function that adds raster band descriptions from
    a reference raster file.
    Both rasters have to have the same number of bands
    """
    ds_ref = gdal.Open(reference_raster)
    num_bands = ds_ref.RasterCount
    bands_descs = {}
    for i in range(1, num_bands + 1):
        band = ds_ref.GetRasterBand(i)
        description = band.GetDescription()
        bands_descs[i] = description
    del ds_ref
    ds_target = gdal.Open(target_raster)
    for i, desc in bands_descs.items():
        target_band = ds_target.GetRasterBand(i)
        target_band.SetDescription(desc)
    del ds_target


def run_subprocess(cmd_list, pipe=True):
    """Helper function that runs a subprocess
    and tries to catch potential errors
    """
    cmd_str = " ".join(cmd_list)
    if pipe is True:
        process = Popen(cmd_list, stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        # stdout_dec = stdout.decode()
        stderr_dec = stderr.decode()
        if "error" in stderr_dec.lower():
            raise Exception(f"Error running process {cmd_str}:\n {stderr_dec}")
    else:
        process = Popen(cmd_list)
        process.wait()


def run_subprocess_parallel(cmd_list_list, num_processes):
    """Helper function that runs run_subprocess in parallel"""
    pool = Pool(processes=num_processes)
    pool.map(run_subprocess, cmd_list_list)


class ForceProcess(object):
    """Stores Methods to set up and run the FORCE Level-2 processor,
    mosaic creation, and postprocessing"""

    def __init__(self, temp_dir, level1_dir=None, wvdb_dir=None):
        """Creates the default FORCE folder structure in the
        user-defined temp directory
        """
        now_time = datetime.now()
        now_time_str = now_time.strftime("%Y%m%d_%H%M%S")
        self.force_dir = makedirs(
            os.path.join(temp_dir, f"force_dir_{now_time_str}")
        )
        if not level1_dir:
            self.level1_dir = makedirs(os.path.join(self.force_dir, "level1"))
        else:
            self.level1_dir = level1_dir
        self.level2_dir = makedirs(os.path.join(self.force_dir, "level2"))
        self.log_dir = makedirs(os.path.join(self.force_dir, "log"))
        self.misc_dir = makedirs(os.path.join(self.force_dir, "misc"))
        self.param_dir = makedirs(os.path.join(self.force_dir, "param"))
        self.provenance_dir = makedirs(
            os.path.join(self.force_dir, "provenance")
        )
        self.temp_dir = makedirs(os.path.join(self.force_dir, "temp_dir"))
        self.wvdb_dir = wvdb_dir
        self.queue_file = None
        self.config_file = None
        # the mosaic tool just takes a relative path as
        # input so both attributes are stored
        self.mosaic_dir_name = "mosaic"
        self.mosaic_path = makedirs(
            os.path.join(self.level2_dir, self.mosaic_dir_name)
        )

    def create_force_queue_file(self):
        """Creates a queue file needed for L2 processing for
        all files of the level1 dir
        """
        files_to_process = [
            os.path.join(self.level1_dir, scene)
            for scene in os.listdir(self.level1_dir)
            if scene.startswith(("LC09", "LC08", "LO09", "LO08", "S2A", "S2B", "S2C"))
        ]
        lines_per_string = [f"{path} QUEUED\n" for path in files_to_process]
        queue_file = os.path.join(self.level1_dir, "queue")
        with open(queue_file, "w") as file:
            file.writelines(lines_per_string)
        self.queue_file = queue_file

    def __replace_in_config_file(
        self, old_config_file, new_config_file, replace_lines
    ):
        """Replaces lines in a FORCE config file"""
        replace_lines_keys = [item.split("= ")[0] for item in replace_lines]
        # create dict
        replace_dict = dict(
            map(lambda i, j: (i, j), replace_lines_keys, replace_lines)
        )
        # open file and replace lines
        updated_conf = ""
        with open(old_config_file, "r") as file:
            for line_raw in file:
                line = line_raw.strip()
                for key, value in replace_dict.items():
                    if line.startswith(key):
                        line = line.replace(line, value)
                updated_conf += f"{line}\n"
        # write content to new file
        with open(new_config_file, "w") as file:
            file.write(updated_conf)
        self.config_file = new_config_file

    def create_force_level2_config_file(
        self,
        dem_path="NULL",
        target_proj_epsg=25832,
        n_procs=1,
        n_threads=2,
        cloud_buffer=300,
    ):
        """Creates a config file needed for L2 processing"""
        config_file_dummy = os.path.join(self.param_dir, "l2ps_dummy.prm")
        config_file = os.path.join(self.param_dir, "l2ps.prm")
        # create a dummy config_file and adapt it
        cmd_list = ["force-parameter", config_file_dummy, "LEVEL2"]
        run_subprocess(cmd_list)
        wkt = get_wkt_from_epsg(target_proj_epsg)
        replace_lines = [
            f"FILE_QUEUE = {self.queue_file}",
            f"DIR_LEVEL2 = {self.level2_dir}",
            f"DIR_LOG = {self.log_dir}",
            f"DIR_PROVENANCE = {self.provenance_dir}",
            f"DIR_TEMP = {self.temp_dir}",
            f"FILE_DEM = {dem_path}",
            f"PROJECTION = {wkt}",
            f"DIR_WVPLUT = {self.wvdb_dir}",
            "RESAMPLING = BL",
            # not really needed because clearsky information will be used
            # in the end:
            # "ERASE_CLOUDS = TRUE",
            # this means all scenes will be processed regardless of cloud
            # cover. The cloud cover limit is already applied during download:
            "MAX_CLOUD_COVER_FRAME = 100",
            # this means that no FORCE tile is taken out of the calculation,
            # even if it has 100% cloud cover:
            "MAX_CLOUD_COVER_TILE = 100",
            f"CLOUD_BUFFER  = {str(cloud_buffer)}",
            f"NPROC = {str(n_procs)}",
            f"NTHREAD = {str(n_threads)}",
        ]
        self.__replace_in_config_file(
            old_config_file=config_file_dummy,
            new_config_file=config_file,
            replace_lines=replace_lines,
        )

    def update_force_level2_config_file(
        self, user_file, target_proj_epsg=None
    ):
        """Updates a config file needed for L2 processing.
        It only updates the config file with the
        FORCE internal directories, the wkt for the projection string,
        and the water vapor db path.
        """
        config_file = os.path.join(self.param_dir, "l2ps.prm")
        replace_lines = [
            f"FILE_QUEUE = {self.queue_file}",
            f"DIR_LEVEL2 = {self.level2_dir}",
            f"DIR_LOG = {self.log_dir}",
            f"DIR_PROVENANCE = {self.provenance_dir}",
            f"DIR_TEMP = {self.temp_dir}",
            f"DIR_WVPLUT = {self.wvdb_dir}",
        ]
        if target_proj_epsg:
            wkt = get_wkt_from_epsg(target_proj_epsg)
            replace_lines.append(f"PROJECTION = {wkt}")
        self.__replace_in_config_file(
            old_config_file=user_file,
            new_config_file=config_file,
            replace_lines=replace_lines,
        )

    def download_wvdb(self, target_dir):
        """Downloads the Water Vapor Database 2000-2020 for
        Landsat atmospheric correction.
        """
        url = (
            "https://zenodo.org/records/4468701/"
            "files/wvp-global.tar.gz?download=1"
        )
        response = requests.get(url)
        if response.status_code != 200:
            raise Exception(
                f"Download from url {url} was not successful: "
                f"Status code {response.status_code}"
            )
        else:
            target_dir = makedirs(target_dir)
            target_file_path = os.path.join(target_dir, "wvp-global.tar.gz")
            with open(target_file_path, mode="wb") as file:
                file.write(response.content)
            print("Extracting Water Vapor Database...")
            with tarfile.open(target_file_path) as tfile:
                tfile.extractall(target_dir)
            os.remove(target_file_path)
            self.wvdb_dir = target_dir
            print(
                "Water Vapor Database downloaded and "
                f"extracted to {target_dir}"
            )

    def setup_wvdb(self, target_dir):
        """Downloads the Water Vapor Database 2000-2020 for Landsat
        atmospheric correction. target_path should be outside any
        temporary folder so the database can be used in the next run.
        Skips the download if the directory exists already and contains
        the minimum requirement for WVDB (monthly averages)
        """
        print(f"Downloading Water Vapor Database to {target_dir}...")
        # first check whether the wvdb exists already:
        if os.path.isdir(target_dir):
            files_in_dir = os.listdir(target_dir)
            # minimum requirement is the monthly averages
            # i:>02 yields 01,02,03 etc.
            required_files = [f"WVP_0000-{i:>02}-00.txt" for i in range(1, 13)]
            file_exists = []
            for req_file in required_files:
                if req_file not in files_in_dir:
                    file_exists.append(False)
                else:
                    file_exists.append(True)
            if False not in file_exists:
                print(
                    "Water Vapor Database exists already "
                    f"in {target_dir}, skipping..."
                )
                self.wvdb_dir = target_dir
            else:
                print(
                    "Water Vapor Database directory exists, but "
                    "files are missing, cleaning up and redownloading..."
                )
                for file in os.listdir(target_dir):
                    # remove files
                    if file.startswith(("wrs-2-land", "WVP_", "wvp-global")):
                        os.remove(os.path.join(target_dir, file))
                    else:
                        raise Exception(
                            f"Unexpected file {file} found in "
                            "Water Vapor Database"
                            f"directory {target_dir}. "
                            "File will not be removed."
                            "Please provide a new Water "
                            "Vapor Database directory"
                        )
                self.download_wvdb(target_dir)
        else:
            self.download_wvdb(target_dir)

    def run_force_level2(self):
        """Runs the Level2 processing - this can be time-consuming!"""
        print("Running FORCE Level-2 Processing...")
        cmd_list = ["force-level2", self.config_file]
        # stderr and stdout are not piped here so the FORCE
        # process becomes visible
        run_subprocess(cmd_list, pipe=False)

    def save_log_files(self, target_dir):
        """Copies the FORCE log files in a target directory."""
        target_dir = makedirs(target_dir)
        for logfile in os.listdir(self.log_dir):
            shutil.copy(os.path.join(self.log_dir, logfile), target_dir)
        print(f"FORCE log files copied to {target_dir}")

    def run_force_mosaic(self):
        """Runs the FORCE mosaic tool that creates .vrt mosaics
        of individual datacube tiles
        """
        print("Creation of same day mosaics...")
        cmd_list = [
            "force-mosaic",
            "-m",
            self.mosaic_dir_name,
            self.level2_dir,
        ]
        run_subprocess(cmd_list)
        print("Creation of same day mosaics finished")
        pass

    def postprocess(
        self, target_dir, x_min, y_min, x_max, y_max, n_procs=1, save_qai=False
    ):
        """
        Does subsetting and cloud filtering on top of the generated mosaics
        """
        print("Postprocessing to clear sky mosaics...")

        target_dir = makedirs(target_dir)
        # first: clip BOA and QAI mosaics to the final extent
        files_to_clip = []
        files_in_mosaic_dir = os.listdir(self.mosaic_path)
        if len(files_in_mosaic_dir) == 0:
            raise Exception(
                "No files found in FORCE mosaic "
                f"directory {self.mosaic_path}. "
                f"Check FORCE logs in {target_dir} for details."
            )
        for file in files_in_mosaic_dir:
            if file.endswith("BOA.vrt") or file.endswith("QAI.vrt"):
                outfile_name_tmp = file.replace("BOA.vrt", "BOA_clipped.vrt")
                outfile_name = outfile_name_tmp.replace(
                    "QAI.vrt", "QAI_clipped.vrt"
                )
                file_list = [
                    os.path.join(self.mosaic_path, file),
                    os.path.join(self.mosaic_path, outfile_name),
                ]
                files_to_clip.append(file_list)

        clipped_boa_files = []
        clipped_qai_files = []
        for in_out_file in files_to_clip:
            # this step takes no time because everything stays .vrt
            in_file = in_out_file[0]
            out_file = in_out_file[1]
            ds_gdal = gdal.Open(in_file)
            ds_gdal = gdal.Translate(
                out_file,
                ds_gdal,
                projWin=[x_min, y_max, x_max, y_min],
                projWinSRS="EPSG:4326",
            )
            ds_gdal = None
            if "BOA" in out_file:
                clipped_boa_files.append(out_file)
            elif "QAI" in out_file:
                clipped_qai_files.append(out_file)

        # next: use the QAI file to generate a NoData/1 clear sky
        # valid pixel mask
        # see also bit pattern: https://force-eo.readthedocs.io/en/latest/
        #                       howto/qai.html#quality-bits-in-force
        clearsky_files = []
        clearsky_cmd_list = []
        for qai_file in clipped_qai_files:
            clearsky_name = qai_file.replace("QAI_clipped.vrt", "clearsky.tif")
            clearsky_cmd = [
                "gdal_calc.py",
                "-A",
                qai_file,
                f"--outfile={clearsky_name}",
                '--calc="((A >> 1) & 3) == 0"',
                "--NoDataValue=0",
                "--type=Byte",
                "--creation-option=COMPRESS=ZSTD",
                "--creation-option=BIGTIFF=YES",
            ]
            clearsky_cmd_list.append(clearsky_cmd)
            clearsky_files.append(clearsky_name)
        run_subprocess_parallel(
            cmd_list_list=clearsky_cmd_list, num_processes=n_procs
        )

        # then: use the binary clearsky map to mask out
        # non-clearsky areas in the BOA.tif
        cloudfree_parallel_list = []
        boa_input_output = {}
        for i, clearsky_file in enumerate(clearsky_files):
            # check whether the binary clearsky file has values
            # (otherwise it is outside the AOI) and it is not needed
            ds_clearsky = gdal.Open(clearsky_file)
            band_clearsky = ds_clearsky.GetRasterBand(1)
            checksum = band_clearsky.Checksum()
            del ds_clearsky
            if checksum > 0:
                # clearsky files (cloud masks) are required
                # in the output as well
                shutil.copy(clearsky_file, target_dir)
                boa_file = clearsky_file.replace(
                    "clearsky.tif", "BOA_clipped.vrt"
                )
                out_boa_filename = os.path.basename(boa_file).replace(
                    "BOA_clipped.vrt", "BOA_clearsky.tif"
                )
                print(f"Creating clear sky mosaic {out_boa_filename}...")
                out_boa_file = os.path.join(target_dir, out_boa_filename)
                boa_input_output[boa_file] = out_boa_file
                cloudfree_cmd = [
                    "gdal_calc.py",
                    "-A",
                    boa_file,
                    "-B",
                    clearsky_file,
                    f"--outfile={out_boa_file}",
                    '--calc="A*B"',
                    "--allBands=A",
                    "--creation-option=COMPRESS=ZSTD",
                    "--creation-option=TILED=YES",
                    "--creation-option=PREDICTOR=2",
                    "--creation-option=BIGTIFF=YES",
                ]
                cloudfree_parallel_list.append(cloudfree_cmd)
                # optionally save the clipped qai files to the target dir
                # (need to be transformed from .vrt to Gtiff)
                if save_qai is True:
                    qai_file = clipped_qai_files[i]
                    qai_output_name = os.path.basename(qai_file).replace(
                        ".vrt", ".tif"
                    )
                    qai_output_file = os.path.join(target_dir, qai_output_name)
                    ds_gdal = gdal.Open(qai_file)
                    ds_gdal = gdal.Translate(
                        qai_output_file,
                        ds_gdal,
                        creationOptions=[
                            "BIGTIFF=YES",
                            "COMPRESS=ZSTD",
                            "TILED=YES",
                        ],
                    )
                    ds_gdal = None

        run_subprocess_parallel(
            cmd_list_list=cloudfree_parallel_list, num_processes=n_procs
        )
        # finally: update the band descriptions from the original files
        for boa_in, boa_out in boa_input_output.items():
            update_band_description_from_reference(
                target_raster=boa_out, reference_raster=boa_in
            )

        print(
            "Postprocessing of clear sky same day mosaics finished. "
            f"Results are saved to {target_dir}"
        )

    def cleanup(self):
        """Deletes all files created during the FORCE processing
        after finishing up and moving the results
        """
        try:
            shutil.rmtree(self.force_dir)
        except Exception as exception:
            raise Exception(
                f"Error deleting directory {self.force_dir}: " f"{exception}"
            )


"""
# Example usage:
test_force = ForceProcess(temp_dir="/path/to/temp/dir",
                          level1_dir="/path/to/dir/with/satellite/data")


# Setup WVDB. If it is already downloaded, specify it in the initialization of
# the class instance like test_force = ForceProcess(
    temp_dir="/path/to/temp/dir",
    level1_dir="/path/to/dir/with/satellite/data",
    wvdb_dir="/path/to/wvdb")
# or simply run the following command nonetheless (Download will be skipped)
test_force.setup_wvdb(target_dir="/path/to/wvdb")

# create a FORCE queue file required to loop over Level1 data
test_force.create_force_queue_file()

# create a FORCE config file.
# Adapt n_procs and n_threads according to your system.
# For few scenes it is recommended to use few procs and more threads
test_force.create_force_level2_config_file(
    dem_path="/path/to/DEM",
    target_proj_epsg=25832,
    n_procs=1,
    n_threads=6)
# alternatively, if you have a FORCE level-2 config file ready
# with your desired FORCE specifications,
# update it to be consistent with the initialized ForceProcess instance by
test_force.update_force_level2_config_file(
    user_file="/path/to/user_config_file",
    target_proj_epsg=25832)

# run the level2 processing, this step is time consuming:
test_force.run_force_level2()

# save the FORCE log files to a desired location
test_force.save_log_files(target_dir="/path/to/target_dir")

# create mosaics
test_force.run_force_mosaic()

# postprocess the mosaic by subsetting to the desired BBOX and
# limiting the valid pixels to clear sky areas.
# This step may take some time as well.
# optionally enable the save_qai=True to also output the FORCE QAI files
test_force.postprocess(
    target_dir="/path/to/target_dir",
    x_min=10.44,
    x_max=11.97,
    y_min=45.67,
    y_max=46.54,
    n_procs=1)

# finally, cleanup all FORCE data except the results.
# only run the cleanup if you don't want to keep intermediate FORCE files:
# test_force.cleanup()
"""
