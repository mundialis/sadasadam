#!/usr/bin/env python3
#
############################################################################
#
# MODULE:      cli.py
# AUTHOR(S):   Momen Mawad, Guido Riembauer
#
# PURPOSE:     Command line interface of sadasadam
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

import argparse
import os
import shutil
import yaml

from sadasadam.force import ForceProcess
from sadasadam.download import download_and_extract
from sadasadam.indices import CreateIndices


def check_bool(variable):
    """
    Helper function that checks whether a variable is of type bool and raises
    and error otherwise
    """
    if not isinstance(variable, bool):
        raise Exception(f"{variable} is not of type boolean (True/False)")


def main():
    """
    Main processing function that connects parsing,
    download, FORCE processing, postprocessing and cleanup.
    """
    parser = argparse.ArgumentParser(
        description="Same Day Satellite DAta Mosaic generation: Automatic "
        "download of Sentinel-2 and Landsat-8/9 data using eodag, atmospheric "
        "correction, mosaic creation and cloud masking "
        "using FORCE."
    )

    # Argument for the config file
    parser.add_argument(
        "--config", type=str, help="Configuration file path", required=True
    )

    args = parser.parse_args()

    if args.config:
        # Load the configuration from the file
        with open(args.config, "r") as config_file:
            config = yaml.load(config_file, Loader=yaml.FullLoader)

        # Access the arguments from the configuration file
        north = config.get("north")
        south = config.get("south")
        east = config.get("east")
        west = config.get("west")
        if not north or not south or not east or not west:
            raise Exception("Please provide a bounding box for your area of interest")
        start = config.get("start")
        if not start:
            raise Exception("Please provide a start date for the temporal extent")
        end = config.get("end")
        if not end:
            raise Exception("Please provide an end date for the temporal extent")
        cloud_cover = config.get("cloud_cover")
        if not cloud_cover:
            raise Exception("Please provide a maximum cloud cover")
        output_dir = config.get("output_dir")
        if not output_dir:
            raise Exception("Please provide an output directory")
        download_dir = config.get("download_dir")
        if not download_dir:
            # create a download directory under the output directory
            download_dir = os.path.join(output_dir, "download")
            if not os.path.exists(download_dir):
                os.mkdir(download_dir)
            print("A download directory will be created " "under the output directory")
        temp_force_dir = config.get("temp_force_dir")
        if not temp_force_dir:
            # create a temporary directory under the output directory
            temp_force_dir = os.path.join(output_dir, "temp")
            if not os.path.exists(temp_force_dir):
                os.mkdir(temp_force_dir)
            print("A temporary directory will be created " "under the output directory")
        wvdb_dir = config.get("wvdb_dir")
        if not wvdb_dir:
            raise Exception("Please provide a path to the wvdb directory")
        target_proj_epsg = config.get("target_proj_epsg")
        if not target_proj_epsg:
            print(
                "No projection was given. "
                "A default projection of EPSG:25832 will be used"
            )
            target_proj_epsg = 25832

        use_param_file = False
        force_param_file = config.get("force_param_file")
        if force_param_file:
            if force_param_file == "None":
                use_param_file = False
            elif not os.path.isfile(force_param_file):
                print(
                    f"FORCE parameter file {force_param_file} not found, "
                    "using parameters from sadasam config file"
                )
            else:
                use_param_file = True
        if use_param_file is False:
            dem_path = config.get("dem_path")
            if not dem_path:
                raise Exception(
                    "Please provide a path to the DEM file, "
                    "or define a force_param_file"
                )
            n_procs_force = config.get("n_procs_force")
            if not n_procs_force:
                raise Exception(
                    "Please provide the number of "
                    "processes to use for FORCE, or "
                    "define a force_param_file"
                )
            n_threads_force = config.get("n_threads_force")
            if not n_threads_force:
                raise Exception(
                    "Please provide the number of "
                    "threads to use for FORCE, or "
                    "define a force_param_file"
                )
            cloud_buffer = config.get("cloud_buffer")
            if not cloud_buffer:
                raise Exception(
                    "Please provide a cloud buffer, " "or define a force_param_file"
                )

        n_procs_postprocessing = config.get("n_procs_postprocessing")
        if not n_procs_postprocessing:
            raise Exception(
                "Please provide the number of " "processes to use for postprocessing"
            )

        save_qai = config.get("save_qai")
        check_bool(save_qai)
        if not save_qai:
            print("QAI will not be saved")

        remove_force_data = config.get("remove_force_data")
        check_bool(remove_force_data)
        if not remove_force_data:
            print("FORCE temp data will not be removed")

        clear_download = config.get("clear_download")
        check_bool(clear_download)
        if not clear_download:
            print("Downloaded Satellite data will not be removed")

        download_only = config.get("download_only")
        check_bool(download_only)
        if download_only:
            print("Process will stop after downloading")

        force_only = config.get("force_only")
        check_bool(force_only)
        if force_only:
            print(
                "Process will skip downloading " "and only run FORCE and postprocessing"
            )
        indices_only = config.get("indices_only")
        check_bool(indices_only)
        if indices_only:
            print(
                "Process will skip downloading, FORCE "
                "and postprocessing and run only indices"
            )

        indices_dir = config.get("indices_dir")
        if not indices_dir:
            # create a indices directory under the output directory
            indices_dir = os.path.join(output_dir, "indices")
            if not os.path.exists(indices_dir):
                os.mkdir(indices_dir)
            print("A indices directory will be created " "under the output directory")
        indices_list = config.get("indices_list")
        if force_only is True and download_only is True:
            raise Exception(
                "Parameters <force_only> and <download_only> "
                "are both True. Nothing to do."
            )

        # Start Downloading

        if force_only is False and indices_only is False:
            # define satellite products
            products = ["S2_MSI_L1C", "LANDSAT_C2L1"]
            # define geometry
            geom = {
                "lonmin": west,
                "latmin": south,
                "lonmax": east,
                "latmax": north,
            }
            # start the download process
            download_and_extract(
                products=products,
                geom=geom,
                start_date=start,
                end_date=end,
                cloudcover=cloud_cover,
                download_dir=download_dir,
            )
        # Start FORCE
        if download_only is False and indices_only is False:
            print("Setting up FORCE processing...")
            # start FORCE process
            force_proc = ForceProcess(temp_dir=temp_force_dir, level1_dir=download_dir)
            force_proc.setup_wvdb(target_dir=wvdb_dir)
            force_proc.create_force_queue_file()
            if use_param_file is False:
                force_proc.create_force_level2_config_file(
                    dem_path=dem_path,
                    target_proj_epsg=target_proj_epsg,
                    n_procs=n_procs_force,
                    n_threads=n_threads_force,
                    cloud_buffer=cloud_buffer,
                )
            else:
                force_proc.update_force_level2_config_file(
                    user_file=force_param_file,
                    target_proj_epsg=target_proj_epsg,
                )
            force_proc.run_force_level2()
            force_proc.save_log_files(target_dir=output_dir)
            force_proc.run_force_mosaic()

            # Start Postprocessing

            force_proc.postprocess(
                target_dir=output_dir,
                x_min=west,
                x_max=east,
                y_min=south,
                y_max=north,
                n_procs=n_procs_postprocessing,
                save_qai=save_qai,
            )

            # Cleanup

            if remove_force_data is True:
                force_proc.cleanup()

        if download_only is False and force_only is False:
            for index in indices_list:
                indices_proc = CreateIndices(
                    indir=output_dir, outdir=indices_dir, index=index
                )
                indices_proc.calculate(n_procs=n_procs_postprocessing)

        if clear_download is True:
            for scene in os.listdir(download_dir):
                if scene.startswith(
                    (
                        "LC09",
                        "LC08",
                        "LO09",
                        "LO08",
                        "S2A",
                        "S2B",
                        "queue",
                        ".downloaded",
                    )
                ):
                    file_path = os.path.join(download_dir, scene)
                    if os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                    elif os.path.isfile(scene):
                        os.remove(file_path)


if __name__ == "__main__":
    main()
