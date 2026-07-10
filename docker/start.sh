#!/bin/sh

########################################################################
#
# MODULE:       start.sh
#
# AUTHOR(S):    Jonas Pischke
#
# PURPOSE:      This script creates the eodag config file (eodag.yml)
#               from environment variables and then starts the container
#               command.
#
# SPDX-FileCopyrightText: (c) 2026 by mundialis GmbH & Co. KG
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
########################################################################

set -eu

: "${CDSE_USER:?CDSE_USER is required}"
: "${CDSE_PW:?CDSE_PW is required}"
: "${USGS_USER:?USGS_USER is required}"
: "${USGS_PW:?USGS_PW is required}"

mkdir -p ~/.config/eodag
cat <<EOF > ~/.config/eodag/eodag.yml
# Copyright 2018, CS GROUP - France, https://www.csgroup.eu/
#
# This file is part of EODAG project
#     https://www.github.com/CS-SI/EODAG
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
cop_dataspace:
  priority: 3
  search: # Search parameters configuration
  download:
    extract: False
    output_dir:
  auth:
    credentials:
      username: ${CDSE_USER}
      password: "${CDSE_PW}"
usgs:
  priority: 2 # Lower value means lower priority (Default: 0)
  api:
    extract: False
    output_dir:
    dl_url_params:
    product_location_scheme:
    credentials:
      username: ${USGS_USER}
      password: "${USGS_PW}"
EOF

if [ "$#" -eq 0 ]; then
	set -- tail -f /dev/null
elif [ "${1#-}" != "$1" ]; then
	set -- sadasadam "$@"
fi

exec "$@"
