# This file builds a Docker base image for its use in other projects

# Copyright (C) 2020-2021 Gergely Padányi-Gulyás (github user fegyi001),
#                         David Frantz
#                         Fabian Lehmann

FROM ubuntu:22.04 as builder

LABEL version="0.1"
LABEL description="This is a docker file to run sadasadam with last FORCE and GDAL 3.4.1"

# disable interactive frontends
ENV DEBIAN_FRONTEND=noninteractive

# Refresh package list & upgrade existing packages
RUN apt-get -y update && apt-get -y dist-upgrade && \
# Add PPA for Python 3.x and R 4.0
apt -y install software-properties-common dirmngr && \
apt-key adv --keyserver keyserver.ubuntu.com --recv-keys E298A3A825C0D65DFD57CBB651716619E084DAB9 && \
add-apt-repository "deb https://cloud.r-project.org/bin/linux/ubuntu $(lsb_release -sc)-cran40/"

RUN apt-get -y install \
  bash \
  wget \
  unzip \
  dos2unix \
  curl \
  git \
  build-essential \
  libgdal-dev \
  gdal-bin \
  #python-gdal \
  libarmadillo-dev \
  libfltk1.3-dev \
  libgsl0-dev \
  lockfile-progs \
  rename \
  parallel \
  apt-utils \
  cmake \
  libgtk2.0-dev \
  pkg-config \
  libavcodec-dev \
  libavformat-dev \
  libswscale-dev \
  python3 \
  python3-pip \
  python3-numpy \
  python3-scipy \
  python3-gdal \
  pandoc \
  r-base \
  aria2

RUN ln -sf /bin/bash /bin/sh

# gsutil for level1-csd, landsatlinks for level1-landsat (requires gdal/requests/tqdm)
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir  \
        gsutil \
        git+https://github.com/ernstste/landsatlinks.git && \
#
# Install R packages
Rscript -e 'install.packages("rmarkdown",   repos="https://cloud.r-project.org")' && \
Rscript -e 'install.packages("plotly",      repos="https://cloud.r-project.org")' && \
Rscript -e 'install.packages("stringi",     repos="https://cloud.r-project.org")' && \
Rscript -e 'install.packages("stringr",     repos="https://cloud.r-project.org")' && \
Rscript -e 'install.packages("tm",          repos="https://cloud.r-project.org")' && \
Rscript -e 'install.packages("knitr",       repos="https://cloud.r-project.org")' && \
Rscript -e 'install.packages("dplyr",       repos="https://cloud.r-project.org")' && \
Rscript -e 'install.packages("bib2df",      repos="https://cloud.r-project.org")' && \
Rscript -e 'install.packages("wordcloud",   repos="https://cloud.r-project.org")' && \
Rscript -e 'install.packages("network",     repos="https://cloud.r-project.org")' && \
Rscript -e 'install.packages("intergraph",  repos="https://cloud.r-project.org")' && \
Rscript -e 'install.packages("igraph",      repos="https://cloud.r-project.org")' && \
Rscript -e 'install.packages("htmlwidgets", repos="https://cloud.r-project.org")' && \
Rscript -e 'install.packages("raster",      repos="https://cloud.r-project.org")' && \
Rscript -e 'install.packages("sp",          repos="https://cloud.r-project.org")' && \
Rscript -e 'install.packages("rgdal",       repos="https://cloud.r-project.org")' && \
Rscript -e 'install.packages("snow",        repos="https://cloud.r-project.org")' && \
Rscript -e 'install.packages("snowfall",    repos="https://cloud.r-project.org")'
#
# Clear installation data
RUN apt-get install -y python3-opencv libopencv-dev libopencv-ml-dev && apt-get clean && rm -r /var/cache/

# Install folder
ENV INSTALL_DIR /opt/install/src

# Build OpenCV from source
# RUN mkdir -p $INSTALL_DIR/opencv && cd $INSTALL_DIR/opencv && \
# wget https://github.com/opencv/opencv/archive/4.1.2.zip \
#   && unzip 4.1.2.zip && \
# mkdir -p $INSTALL_DIR/opencv/opencv-4.1.2/build && \
# cd $INSTALL_DIR/opencv/opencv-4.1.2/build && \
# cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local .. \
#   && make -j7 \
#   && make install \
#   && make clean && \

# Build SPLITS from source
RUN mkdir -p $INSTALL_DIR/splits && \
cd $INSTALL_DIR/splits && \
wget http://sebastian-mader.net/wp-content/uploads/2017/11/splits-1.9.tar.gz && \
tar -xzf splits-1.9.tar.gz && \
cd $INSTALL_DIR/splits/splits-1.9 && \
./configure CPPFLAGS="-I /usr/include/gdal" CXXFLAGS=-fpermissive \
  && make \
  && make install \
  && make clean && \
#
# Cleanup after successfull builds
rm -rf $INSTALL_DIR
#RUN apt-get purge -y --auto-remove apt-utils cmake git build-essential software-properties-common

# Create a dedicated 'docker' group and user
RUN groupadd docker && \
  useradd -m docker -g docker -p docker && \
  chmod 0777 /home/docker && \
  chgrp docker /usr/local/bin && \
  mkdir -p /home/docker/bin && chown docker /home/docker/bin
# Use this user by default
USER docker

ENV HOME /home/docker
ENV PATH "$PATH:/home/docker/bin:/home/docker/.local/bin"

ENV SOURCE_DIR $HOME/src/force
ENV INSTALL_DIR $HOME/bin
ARG debug=disable

RUN mkdir -p $SOURCE_DIR
WORKDIR $SOURCE_DIR
RUN wget https://github.com/davidfrantz/force/archive/refs/tags/v3.7.12.tar.gz
RUN tar xf v3.7.12.tar.gz
RUN mv force-3.7.12/* .
RUN rm -rf v3.7.12.tar.gz force-3.7.12/

RUN ls -lh

RUN echo "building FORCE" && \
  ./splits.sh enable && \
  ./debug.sh $debug && \
  sed -i "/^BINDIR=/cBINDIR=$INSTALL_DIR/" Makefile && \
  sed -i "/^OPENCV=/cOPENCV=-I/usr/include/opencv4 -L/usr/lib -Wl,-rpath=/usr/lib/" Makefile && \
  make -j && \
  make install && \
  make clean && \
  cd $HOME && \
  rm -rf $SOURCE_DIR && \
  force

WORKDIR $HOME
# clone FORCE UDF
RUN git clone https://github.com/davidfrantz/force-udf.git

#FROM ubuntu:22.04 as force

#COPY --chown=docker:docker --from=force_builder $HOME/bin $HOME/bin
RUN mv $HOME/force-udf $HOME/udf

ENV SADA_DIR $HOME/src/sadasadam
RUN mkdir -p $SADA_DIR
WORKDIR $SADA_DIR
COPY --chown=docker:docker . .

RUN export -p

RUN export GDAL_VER=$(gdal-config --version); echo $GDAL_VER && \
    sed -i -e "s/gdal-utils/gdal-utils == $GDAL_VER/g" pyproject.toml && \
    sed -i "s/\"gdal\"/\"gdal == $GDAL_VER\"/g" pyproject.toml

RUN cat pyproject.toml

RUN pip install .

CMD ["sadasadam", "--help"]