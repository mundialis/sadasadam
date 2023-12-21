# SAme-Day SAtellite DAta Mosaics (SADASADAM)

**Table of contents:**

- [Introduction](#introduction)
- [Requirements](#requirements)
  - [FORCE](#force)
  - [GDAL](#gdal)
  - [Python libraries](#python-libraries)
- [Installation](#installation)
  - [eodag configuration](#eodag-configuration)
- [Usage](#usage)
  - [Overview](#overview)
    - [Download of satellite data](#download-of-satellite-data)
    - [FORCE processing](#force-processing)
    - [Postprocessing](#postprocessing)
    - [Output](#output)
  - [Config file](#config-file)
    - [Data filtering options](#data-filtering-options)
    - [FORCE & postprocessing options](#force--postprocessing-options)
    - [General process options](#general-process-options)
  - [Running SADASADAM](#running-sadasadam)

# Introduction

SADASADAM is a command line tool that generates Sentinel-2 and Landsat-8/9 same-day mosaics for a user-defined bounding box and temporal extent.
It uses the python package [eodag](https://eodag.readthedocs.io/en/stable/index.html) to search and download data and the
software [FORCE](https://force-eo.readthedocs.io/en/latest/index.html) for atmospheric correction, cloud detection, and mosaic creation.

# Requirements

### [FORCE](https://force-eo.readthedocs.io/en/latest/index.html)

needs to be installed on the system. FORCE in turn has many dependencies and takes some steps to install. See the detailed
installation instructions from the [FORCE documentation](https://force-eo.readthedocs.io/en/latest/setup/depend.html).
SADASADAM was developed and tested using FORCE v.3.7.11.

### [GDAL](https://gdal.org)

and its Python bindings need to be installed, but they should be a requirement for FORCE anyway. SADASADAM was developed
and tested using GDAL v.3.4.1. See also the [GDAL dependency of FORCE](https://force-eo.readthedocs.io/en/latest/setup/depend.html).
GDAL is often available in most systems but needs to be installed if not already present.

### Python libraries

SADASADAM requires the Python libraries `pyyaml`, `eodag`, `gdal`, `gdal-utils`, and `requests` which should be installed automatically
when installing SADASADAM (see next section)

# Installation

SADASADAM can be installed as follows:

```
# clone the repository from github
git clone git@github.com:mundialis/sadasadam.git

# change dir into the repository and run pip
cd sadasadam
pip install .
```

Note that `pip install .` command does install the packages locally from the current directory.

### eodag configuration

The steps above will automatically install the Python library [eodag](https://eodag.readthedocs.io/en/stable/index.html) as well.
Before running SADASADAM, eodag needs to be configured (see [eodag documentation](https://eodag.readthedocs.io/en/stable/getting_started_guide/configure.html)).
The eodag config file needs to be filled with credentials for satellite data providers. SADASADAM calls eodag to download only Sentinel-2
and Landsat-8/9 Level 1C data. Therefore, providing credentials to the `cop_dataspace` and `usgs` sections of the eodag config file
is recommended. It is recommended to define `extract: False` in the eodag config file as SADASADAM automatically extracts the downloaded data according to the input requirements of FORCE.

A priority of providers can be defined in the eodag config file. We noticed the unexpected behaviour that download of Sentinel-2
from `cop_dataspace` fails (error related to `peps` provider credentials), if both `cop_dataspace` and `usgs` have the same priority.
A functioning workaround seems to be to **set the priority of `cop_dataspace` to 2, and that of `usgs` to 1** - this way both Sentinel-2 and
Landsat download worked in our tests.

# Usage

### Overview

SADASADAM can be executed with one single command, but internally, the script can be divided into three consecutives steps:

##### Download of satellite data

SADASADAM will try to download all Sentinel-2 and Landsat-8/9 Level 1C scenes that match the filter options passed in the SADASADAM config file.
It makes use of user credentials and download paths defined in the eodag config file (see section above). The download path however can also be overwritten by
the `download_dir` parameter of the SADASADAM config file. All data are extracted, corrupt archives are removed and tried to download again.

##### FORCE processing

SADASADAM generates atmospherically corrected Level-2 same-day mosaics from the L1C data with [FORCE](https://force-eo.readthedocs.io/en/latest/index.html).
FORCE will take all scenes that are in the eodag download directory as input. Therefore, it is recommended to remove the downloaded scenes after each run using `clear_download: True`.
You can set `clear_download: False`, if something went wrong in the process and you would like to investigate the intermediate results.

SADASADAM will set up a FORCE-compatible temporary directory structure in the directory `temp_force_dir` configured in the SADASADAM config file. This folder
will contain all FORCE intermediate results, which may be persisted using `remove_force_dir: False` (setting this to `True` will remove the entire
temporary FORCE directory after processing). FORCE parametrization may either be done by defining a subset of FORCE parameters in the SADASADAM config file (all other FORCE parameters are set by SADASADAM automatically, see `create_force_level2_config_file` in [force.py](./sadasadam/force.py))
or by defining a path to a user-defined FORCE parameter file using `force_param_file` (SADASADAM will create an internal copy of this file and will only overwrite
the FORCE-internal directories). See also this [FORCE tutorial](https://force-eo.readthedocs.io/en/latest/howto/l2-ard.html#the-parameter-file) for more information on the FORCE Level 2 parameter file.

##### Postprocessing

In the final step, the mosaics are cropped to the final extent and clouds are removed using the `clear sky` information of the FORCE Quality Assurance Information ([QAI](https://force-eo.readthedocs.io/en/latest/howto/qai.html))
masks. GDAL methods `gdal_translate` and `gdal_calc.py` are used internally for this step. Resulting cloud masked same-day reflectance mosaics are saved as multiband GeoTiffs to the output folder defined in `output_dir` in the SADASADAM config file.
The clear sky binary mask (+ optionally the FORCE QAI masks) as well as FORCE log files are moved to the output folder as well.

##### Output

SADASADAM will produce the following output files in the `output_dir`:

- `<DATE>_LEVEL2_<SENSOR>_BOA_clearsky.tif`: Bottom of Atmosphere Reflectance mosaic as multiband GeoTIFF of a specific date and sensor, with valid pixels masked to clear sky only.
- `<DATE>_LEVEL2_<SENSOR>_clearsky.tif`: Binary clear sky mask mosaic of a specific date and sensor. Pixels may only have the value 1, Non-clear pixels are No Data.
- `<DATE>_LEVEL2_<SENSOR>_QAI_clipped.tif` (optional if `save_qai: True`): [Quality Assurance Information](https://force-eo.readthedocs.io/en/latest/howto/qai.html#tut-qai) mosaic of a specific date and sensor from FORCE.
- `<FILENAME>.log`: FORCE log file of each specific input scene.

### Config file

The parameters of the SADASADAM config file are described below in detail. See also the example config file [here](config_example.yaml).

##### Data filtering options

```
start: '2023-08-01'   # start date for temporal filter of satellite data download in format YYYY-MM-DD
end: '2023-08-31'     # end date for temporal filter of satellite data download in format YYYY-MM-DD
north: 46.6           # AOI boundary in decimal degree
south: 45.67          # AOI boundary in decimal degree
east: 11.97           # AOI boundary in decimal degree
west: 10.44           # AOI boundary in decimal degree
cloud_cover: 75       # maximum percentage of cloud cover in scene
```

##### FORCE & postprocessing options

```
download_dir: '/path/to/download_dir'           # Path to the download directory. FORCE will use all valid satellite
                                                # scenes (extracted Landsat-8/9 and Sentinel-2 in .SAFE format) in this directory as input.
temp_force_dir: '/path/to/temp_force_dir'       # Path to a directory that can hold intermediate FORCE results. A new FORCE directory with a timestamp will be created here.
wvdb_dir: '/path/to/wvdb_dir'                   # Path to store the water vapor database. This database is required for Landsat processing in FORCE.
                                                # SADASADAM will download it automatically if it cannot find it in the defined directory.
                                                # This directory should be persistent, such that the wvdb does not need to be download each run.
remove_force_data: True                         # Whether or not the FORCE working directory in temp_force_dir should be deleted after processing.
                                                # This directory holds the FORCE datacube and should be removed, unless insights in the FORCE processing are desired.
n_procs_postprocessing: 4                       # Number of parallel processes used for the post processing with GDAL.
target_proj_epsg: 25832                         # EPSG code of the desired output projection.
output_dir: '/path/to/output/dir'               # Directory that will hold the final mosaics, clear sky masks, and FORCE log files.
save_qai: False                                 # Whether or not the FORCE Quality Assurance Information masks should be saved as well.
```

The following parameters of the SADASADAM config file are steering FORCE processing in the FORCE parameter file (see [FORCE tutorial](https://force-eo.readthedocs.io/en/latest/howto/l2-ard.html#parameterization)):

```
dem_path: '/path/to/a/local/dem.tif'            # Path to a local digital elevation model used for topographic correction. It is required to use a DEM with an extent larger than
                                                # the AOI as FORCE processes the entire scenes. The DTM has to cover entirely all the scenes.
n_procs_force: 4                                # Number of parallel processes for FORCE. FORCE uses a multiprocessing/multithreading approach. The best combination of processes
                                                # and threads heavily depends on your system and the amount/size of scenes to process  (see also FORCE Level 2 ARD tutorial for recommendations).
n_threads_force: 2                              # Number of threads per process for multithreading in FORCE.
cloud_buffer: 300                               # Cloud buffer to be applied to the confident clouds in FORCE.
```

These are just a subset of many parameters in the FORCE parameter file - SADASADAM will create a default FORCE parameter file
and apply recommended values for the remaining parameters (see also `create_force_level2_config_file` in [force.py](./sadasadam/force.py)).

Alternatively, the user can provide a complete FORCE parameter file through the config parameter `force_param_file`:

```
force_param_file = '/path/to/local/force_param_file' # Path to a complete user-configured FORCE parameter file. The first block
                                                     # (INPUT/OUTPUT DIRECTORIES) does not need to be filled, SADASADAM will adapt
                                                     # it to match the local temporary FORCE directory structure
```

In this case, the parameters `dem_path`, `n_procs_force`, `n_threads_force`, and `cloud_buffer` are ignored.

##### General process options

```
clear_download: True  # Will clear the content of the download directory <download_dir> after processing. FORCE
                      # always uses the entire content of <download_dir> as input, so setting this to True is
                      # recommended. However, it may make sense to set it to False for debugging purposes, e.g.
                      # if FORCE processing failed and you don't want to start the entire process, but skip the
                      # download. Then the <force_only> parameter may be set to True as well.
download_only: False  # You may use SADASADAM to simply download satellite data without any further processing,
                      # in which case this parameter can be set to True.
force_only: False     # Setting this parameter to True skips the download and directly starts with FORCE processing
                      # and postprocessing, assuming there is satellite data in <download_dir>.
```

### Running SADASADAM

Run SADASADAM by simply passing the SADASADAM config.yaml file:

```commandline
sadasadam --config /path/to/sadasadam_conf_file.yaml
```

Note: This will start the entire process (data download, FORCE processing, postprocessing) and may take a lot of time
depending on data filtering and parallelization options defined in the config file.

#### Using SADASADAM with Singularity

Singularity is a free and open source container platform released with BSD license.

To run SADASADAM with Singularity you need first to create the container using the `sadasadam.def` receipt file. To build the container image you need to be root.

```commandline
sudo singularity build sadasadam.simg sadasadam.def
```

At this point it is possible to run SADASADAM into the created container.

```commandline
singularity exec sadasadam.simg sadasadam --config config.yaml
```

If you need to pass the EODAG configuration file you can use the `EODAG_CFG_FILE` environmental variable as written in [EODAG documentation](https://eodag.readthedocs.io/en/stable/getting_started_guide/configure.html#yaml-user-configuration-file)

```commandline
singularity exec --env EODAG_CFG_FILE=/PATH/TO/eodag.yml sadasadam.simg sadasadam --config config.yaml
```
