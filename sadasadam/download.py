#!/usr/bin/env python3
#
############################################################################
#
# MODULE:      download.py
# AUTHOR(S):   Momen Mawad, Guido Riembauer, Jonas Pischke
#
# PURPOSE:     Handles download of satellite data using eodag
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


import os
import shutil
import sys
import zipfile

from eodag import EODataAccessGateway
from eodag import SearchResult


def download_with_eodag(
    product_type,
    geom,
    start_date,
    end_date,
    download_dir,
    cloudcover=100,
    s2_scene_ids=None,
    tile_id=None,
):
    """Function to download satellite data using eodag library"""
    # initialize eodag
    dag = EODataAccessGateway()
    # set preferred provider according to the product type
    provider_dict = {"S2_MSI_L1C": "cop_dataspace", "LANDSAT_C2L1": "usgs"}
    provider = provider_dict.get(product_type, None)
    # search for products
    items_per_page = 20
    if not s2_scene_ids:
        search_kwargs = {
            "items_per_page": items_per_page,
            "collection": product_type,
            "geom": geom,
            "start": start_date,
            "end": end_date,
            "eo:cloud_cover": cloudcover,
            "provider": provider,
        }
        print(
            f"Searching for {product_type} products with the following "
            "parameters:"
        )
        print(f"- Start date: {start_date}")
        print(f"- End date: {end_date}")
        print(f"- Cloud cover: {cloudcover}")
        if tile_id and product_type == "S2_MSI_L1C":
            search_kwargs["grid:code"] = f"MGRS-{tile_id}"
            print(f"- Tile ID: {tile_id}")
        search_results = dag.search_all(**search_kwargs)
    elif s2_scene_ids and product_type == "S2_MSI_L1C":
        search_kwargs = {
            "items_per_page": items_per_page,
            "collection": product_type,
            "provider": provider,
        }
        search_results_lst = []
        print(
            f"Searching for {product_type} products with the following "
            "Sentinel-2 Scene IDs:"
        )
        for scene_id in s2_scene_ids:
            print(f"- {scene_id}")
            search_kwargs["id"] = scene_id
            search_results_lst.extend(dag.search(**search_kwargs))
            search_results = SearchResult(search_results_lst)
    num_results = len(search_results)
    if num_results > 0:
        print(
            f"Found {num_results} matching scenes "
            f"of type {product_type}, starting download..."
        )
    else:
        print(
            f"No matching scenes found for {product_type} "
            f"with the given parameters. Please check your search criteria."
        )
        # stope program if no matching scenes are found
        sys.exit("Stopping SADASADAM.")
    dag.download_all(search_results, output_dir=download_dir, extract=False)


def extract_and_delete_tar_gz_files(directory):
    """
    Function to extract .tar.gz and .SAFE.zip files
    recursively from a directory and delete them
    """
    corrupt_files = []
    for file in os.listdir(directory):
        if file.endswith((".SAFE.zip", ".tar.gz", ".SAFE")):
            file_path = os.path.join(directory, file)
            warning_text = (
                "Warning: - "
                f"Unable to extract: {file_path}. "
                "Retrying Download..."
            )
            landsat_extract_dir = None
            remove = True
            try:
                if file.endswith(".tar.gz"):
                    landsat_extract_dir_name = file.split(".")[0]

                    # Create a directory with the same name as
                    # the file (without the .tar.gz extension)
                    os.makedirs(
                        os.path.join(directory, landsat_extract_dir_name),
                        exist_ok=True,
                    )

                    landsat_extract_dir = os.path.join(
                        directory, landsat_extract_dir_name
                    )

                    target_dir = landsat_extract_dir
                    unpack = True

                elif file.endswith(".SAFE.zip"):
                    zfile = zipfile.ZipFile(file_path)
                    zfile_test = zfile.testzip()
                    if zfile_test is not None:
                        print(warning_text)
                        corrupt_files.append(file_path)
                        unpack = False
                    else:
                        target_dir = directory
                        unpack = True

                elif file.endswith(".SAFE"):
                    # this should fail if the .SAFE is a corrupt
                    # downloaded file and not previously extracted
                    os.listdir(file_path)
                    unpack = False
                    remove = False

                if unpack is True:
                    shutil.unpack_archive(file_path, extract_dir=target_dir)
                # Delete file after extraction
                if remove is True:
                    os.remove(file_path)
            except Exception as exception:
                print(f"{warning_text}: {exception}")
                corrupt_files.append(file_path)
                os.remove(file_path)
                if landsat_extract_dir:
                    shutil.rmtree(landsat_extract_dir)
                continue

    return corrupt_files


def download_and_extract(
    products,
    geom,
    download_dir,
    start_date=None,
    end_date=None,
    cloudcover=100,
    s2_scene_ids=None,
    tile_id=None,
    max_tries=3,
):
    """
    Function to download satellite data using eodag library, extract,
    and retry download if files are corrupt
    """
    run_download = True
    count = 0
    while run_download is True:
        for product_name in products:
            download_with_eodag(
                product_type=product_name,
                geom=geom,
                start_date=start_date,
                end_date=end_date,
                cloudcover=cloudcover,
                download_dir=download_dir,
                s2_scene_ids=s2_scene_ids,
                tile_id=tile_id,
            )
        corrupt_files = extract_and_delete_tar_gz_files(download_dir)
        if len(corrupt_files) == 0:
            run_download = False
        count += 1
        if count == max_tries:
            run_download = False
            if len(corrupt_files) > 0:
                print(
                    f"Scene/s {'; '.join(corrupt_files)} seem to be "
                    f"corrupt even after {max_tries} downloads. "
                    "Files are removed and processing continues without them"
                )
