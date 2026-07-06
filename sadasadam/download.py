#!/usr/bin/env python3
# ruff: noqa: TRY003, PTH208, PLR0913, PLR0917, PTH118, PTH103, PTH107
############################################################################
#
# MODULE:      download.py
# AUTHOR(S):   Momen Mawad, Guido Riembauer, Jonas Pischke
#
# PURPOSE:     Handles download of satellite data using eodag
# COPYRIGHT:   (C) 2023 by mundialis GmbH & Co. KG
#
# SPDX-FileCopyrightText: (c) 2026 by mundialis GmbH & Co. KG
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
############################################################################

"""Module to handle download of satellite data using eodag library."""

from __future__ import annotations

import os
import shutil
import sys
import zipfile

from eodag import EODataAccessGateway, SearchResult


def download_with_eodag(
    product_type: str,
    geom: dict,
    start_date: str,
    end_date: str,
    download_dir: str,
    cloudcover: int = 100,
    s2_scene_ids: list | None = None,
    tile_id: str | None = None,
) -> None:
    """Download satellite data using the eodag library."""
    # initialize eodag
    dag = EODataAccessGateway()
    # set preferred provider according to the product type
    provider_dict = {"S2_MSI_L1C": "cop_dataspace", "LANDSAT_C2L1": "usgs"}
    provider = provider_dict.get(product_type)
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
            "parameters:",
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
            "Sentinel-2 Scene IDs:",
        )
        for scene_id in s2_scene_ids:
            print(f"- {scene_id}")
            search_kwargs["id"] = scene_id
            search_results_lst.extend(dag.search(**search_kwargs))
            search_results = SearchResult(search_results_lst)
    else:
        raise ValueError(
            "s2_scene_ids can only be used with product_type S2_MSI_L1C",
        )
    num_results = len(search_results)
    if num_results > 0:
        print(
            f"Found {num_results} matching scenes "
            f"of type {product_type}, starting download...",
        )
    else:
        print(
            f"No matching scenes found for {product_type} "
            f"with the given parameters. Please check your search criteria.",
        )
        # stope program if no matching scenes are found
        sys.exit("Stopping SADASADAM.")
    dag.download_all(search_results, output_dir=download_dir, extract=False)


def extract_and_delete_tar_gz_files(directory: str) -> list:
    """Extract .tar.gz and .SAFE.zip files."""
    corrupt_files = []
    for file in os.listdir(directory):
        if file.endswith((".SAFE.zip", ".tar.gz", ".SAFE")):
            file_path = os.path.join(directory, file)
            warning_text = (
                "Warning: - "
                f"Unable to extract: {file_path}. "
                "Retrying Download...",
            )
            landsat_extract_dir = None
            remove = True
            target_dir = None
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
                        directory,
                        landsat_extract_dir_name,
                    )

                    target_dir = landsat_extract_dir
                    unpack = True

                elif file.endswith(".SAFE.zip"):
                    with zipfile.ZipFile(file_path) as zfile:
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
                else:
                    unpack = False
                if unpack is True:
                    shutil.unpack_archive(file_path, extract_dir=target_dir)
                # Delete file after extraction
                if remove is True:
                    os.remove(file_path)
            except (
                OSError,
                zipfile.BadZipFile,
                shutil.ReadError,
            ) as exception:
                print(f"{warning_text}: {exception}")
                corrupt_files.append(file_path)
                os.remove(file_path)
                if landsat_extract_dir:
                    shutil.rmtree(landsat_extract_dir)
                continue

    return corrupt_files


def download_and_extract(
    products: list,
    geom: dict,
    download_dir: str,
    start_date: str | None = None,
    end_date: str | None = None,
    cloudcover: int = 100,
    s2_scene_ids: list | None = None,
    tile_id: str | None = None,
    max_tries: int = 3,
) -> None:
    """Download and extract satellite data."""
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
                    "Files are removed and processing continues without them",
                )
