FROM davidfrantz/force:3.11.00
USER root

COPY . /src/sadasadam/

# Copy startup script into the image
COPY --chmod=755 docker/start.sh /src/start.sh
WORKDIR /src/sadasadam
RUN apt-get update && \
    apt-get install --no-install-recommends --yes python3-pip && \
    rm -rf /var/lib/apt/lists/* && \
    python3 -m pip install . --no-cache-dir --break-system-packages

# Create a non-root user and set ownership of the source directory
RUN useradd --create-home --shell /bin/bash user && \
    chown -R user:user /src
USER user
ENV HOME=/home/user

WORKDIR /src

ENTRYPOINT ["/src/start.sh"]
CMD ["tail", "-f", "/dev/null"]
