FROM davidfrantz/force:3.10.04
USER root

WORKDIR /src/sadasadam
COPY pyproject.toml README.md /src/sadasadam/
COPY sadasadam/ /src/sadasadam/sadasadam/

# Copy startup script into the image
COPY docker/start.sh /src/start.sh
RUN chmod +x /src/start.sh && \
    pip install . --no-cache-dir --break-system-packages

# Create a non-root user and set ownership of the source directory
RUN useradd --create-home --shell /bin/bash user && \
    chown -R user:user /src
USER user

ENTRYPOINT ["/src/start.sh"]
CMD ["tail", "-f", "/dev/null"]
