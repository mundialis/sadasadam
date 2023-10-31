#!/usr/bin/env python3
#
############################################################################
#
# MODULE:      download.py
# AUTHOR(S):   Momen Mawad, Guido Riembauer
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

from eodag import EODataAccessGateway


def download_with_eodag(
    product_type, geom, start_date, end_date, cloudcover=100
):
    """Function to download satellite data using eodag library"""
    # initialize eodag
    dag = EODataAccessGateway()
    # search for products

    search_results, total_count = dag.search(
        productType=product_type,
        # accepts WKT polygons, shapely.geometry, ...
        geom=geom,
        start=start_date,
        end=end_date,
        # Set cloud cover
        cloudCover=cloudcover,
        raise_errors=True,
    )
    print(
        f"Found {total_count} matching scenes of type {product_type}, "
        "starting download..."
    )
    dag.download_all(search_results)


def extract_and_delete_tar_gz_files(directory):
    """
    Function to extract .tar.gz files recursively from a directory
    and delete them
    """
    for file in os.listdir(directory):
        if file.endswith((".SAFE.zip", ".tar.gz")):
            file_path = os.path.join(directory, file)
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

                    # Extract the .tar.gz file to the created directory
                    shutil.unpack_archive(
                        file_path, extract_dir=landsat_extract_dir
                    )

                elif file.endswith(".SAFE.zip"):
                    shutil.unpack_archive(file_path, extract_dir=directory)
                    # Delete the .tar.gz file after extraction
                os.remove(file_path)
            except Exception as exception:
                print(
                    f"Warning: {exception} - "
                    "Unable to extract or delete: {file_path}"
                )
                continue
