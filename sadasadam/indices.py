#!/usr/bin/env python3
#
############################################################################
#
# MODULE:      indices.py
# AUTHOR(S):   Luca Delucchi
#
# PURPOSE:     Create indices using gdal_calc.py
# COPYRIGHT:   (C) 2024 by Fondazione Edmund Mach
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
from sadasadam.force import makedirs
from sadasadam.force import run_subprocess_parallel

INDICES = {
    "NDVI": {"name": "Normalized Difference Vegetation Index",
             "formula": "((A.astype(float)-B)/(A.astype(float)+B))",
             "Sentinel-2": {"A": 4, "B": 8},
             "LANDSAT": {"A": 3, "B": 5}},
    "NDSI": {"name": "Normalized Difference Snow Index",
             "formula": "((A.astype(float)-B)/(A.astype(float)+B))",
             "Sentinel-2": {"A": 3, "B": 11},
             "LANDSAT": {"A": 4, "B": 6}},
    "NDMI": {"name": "Normalized Difference Moisture Index",
             "formula": {"((A.astype(float)-B)/(A.astype(float)+B))"},
             "Sentinel-2": {"A": 8, "B": 11},
             "LANDSAT": {"A": 5, "B": 6}}
}

class CreateIndices(object):

    def __init__(self, indir, outdir, index="NDVI"):
        """Create folder to store indices

        Args:
            indir (str): directory containing the Level 2 data
            outdir (str): directory containing the indices calculated
        """
        self.indir = indir
        self.outdir = makedirs(outdir)
        if index not in INDICES.keys():
            raise Exception(f"Index {index} not available in the list of supported indices")
        else:
            self.index = index

    def calculate(self, n_procs=1):
        all_files = os.listdir(self.indir)
        files_to_process = []
        for file in all_files:
            if file.endswith("BOA_clearsky.tif"):
                files_to_process.append(file)
        indices_cmd_list = []
        index = INDICES[self.index]
        formula = index['formula']
        for file in files_to_process:
            if "SEN2" in file:
                bands = INDICES[self.index]["Sentinel-2"]
            elif "LND" in file:
                bands = INDICES[self.index]["LANDSAT"]
            name_file = os.path.basename(file).replace("BOA_clearsky", self.index)
            out_file = os.path.join(self.outdir, name_file)
            in_file = os.path.join(self.indir, file)
            index_calc = [
                "gdal_calc.py",
                "-A",
                in_file,
                f"--a_band={bands['A']}",
                "-B",
                in_file,
                f"--b_band={bands['B']}",
                f"--outfile={out_file}",
                f'--calc="{formula}"',
                "--type=Float32",
                "--creation-option=COMPRESS=ZSTD",
                "--creation-option=TILED=YES",
                "--creation-option=PREDICTOR=2",
                "--creation-option=BIGTIFF=YES",
            ]
            print(" ".join(index_calc))
            indices_cmd_list.append(index_calc)
        run_subprocess_parallel(
            cmd_list_list=indices_cmd_list, num_processes=n_procs
        )