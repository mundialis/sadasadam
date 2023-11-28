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
import zipfile

from eodag import EODataAccessGateway


def download_with_eodag(
    product_type, geom, start_date, end_date, download_dir, cloudcover=100
):
    """Function to download satellite data using eodag library"""
    # initialize eodag
    dag = EODataAccessGateway()
    # search for products
    items_per_page = 20
    search_kwargs = {
        "items_per_page": items_per_page,
        "productType": product_type,
        "geom": geom,
        "start": start_date,
        "end": end_date,
        "cloudCover": cloudcover,
    }
    search_results = dag.search_all(**search_kwargs)
    num_results = len(search_results)
    # iterate over pages
    print(
        f"Found {num_results} matching scenes "
        f"of type {product_type}, starting download..."
    )
    dag.download_all(search_results, outputs_prefix=download_dir)


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
                exception = None
                print(warning_text)
                corrupt_files.append(file_path)
                os.remove(file_path)
                if landsat_extract_dir:
                    shutil.rmtree(landsat_extract_dir)
                continue

    return corrupt_files


def download_and_extract(
    products,
    geom,
    start_date,
    end_date,
    download_dir,
    cloudcover=100,
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
