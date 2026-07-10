FROM davidfrantz/force:3.10.04
USER root

COPY . /src/sadasadam/

# Copy startup script into the image
COPY docker/start.sh /src/start.sh
WORKDIR /src/sadasadam
RUN chmod +x /src/start.sh && \
    pip install . --no-cache-dir --break-system-packages

# Create a non-root user and set ownership of the source directory
RUN useradd --create-home --shell /bin/bash user && \
    chown -R user:user /src
USER user

WORKDIR /src

ENTRYPOINT ["/src/start.sh"]
CMD ["tail", "-f", "/dev/null"]
