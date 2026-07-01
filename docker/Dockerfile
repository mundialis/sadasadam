FROM davidfrantz/force:3.10.04
USER root

WORKDIR /src/sadasadam
COPY pyproject.toml README.md /src/sadasadam/
COPY sadasadam/ /src/sadasadam/sadasadam/

# Copy startup script into the image
COPY docker/start.sh /src/start.sh
RUN chmod +x /src/start.sh

RUN pip install . --break-system-packages
ENTRYPOINT ["/src/start.sh"]
CMD ["tail", "-f", "/dev/null"]