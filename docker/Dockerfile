FROM davidfrantz/force:3.10.04
USER root

ARG CDSE_USER
ARG CDSE_PW
ARG USGS_USER
ARG USGS_PW

WORKDIR /src/sadasadam
COPY pyproject.toml README.md /src/sadasadam/
COPY sadasadam/ /src/sadasadam/sadasadam/

# Copy and execute setup script during image build
COPY docker/setup_eodag.sh /src/setup_eodag.sh
RUN chmod +x /src/setup_eodag.sh && \
	CDSE_USER="${CDSE_USER}" \
	CDSE_PW="${CDSE_PW}" \
	USGS_USER="${USGS_USER}" \
	USGS_PW="${USGS_PW}" \
	/src/setup_eodag.sh

RUN pip install . --break-system-packages
CMD ["tail", "-f", "/dev/null"]