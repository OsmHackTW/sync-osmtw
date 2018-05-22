FROM ubuntu:18.04

ARG APT_MIRROR='https://free.nchc.org.tw'
ARG OSMOSIS_VER='0.45'
ARG MAPSFORGE_VER='0.8.0'

# Install packages.
RUN cd /etc/apt && \
  cp sources.list sources.list.orig && \
  sed "s/https\?:\/\/\(archive\|security\).ubuntu.com/${APT_MIRROR}/" sources.list.orig > sources.list && \
  apt-get update && apt-get install -y \
  wget \
  unzip \
  python3-pip \
  python3-gdal \
  openjdk-8-jre-headless

# Install osmosis & mapsforge writer plugin.
ENV PATH "$PATH:/usr/local/osmosis/bin"
RUN cd /root && \
  wget -q https://bretth.dev.openstreetmap.org/osmosis-build/osmosis-${OSMOSIS_VER}.zip && \
  unzip osmosis-${OSMOSIS_VER}.zip -d /usr/local/osmosis && \
  rm -f osmosis-${OSMOSIS_VER}.zip && \
  mkdir -p /root/.openstreetmap/osmosis/plugins && \
  cd /root/.openstreetmap/osmosis/plugins && \
  wget -q http://central.maven.org/maven2/org/mapsforge/mapsforge-map-writer/${MAPSFORGE_VER}/mapsforge-map-writer-${MAPSFORGE_VER}-jar-with-dependencies.jar

# Install Python 3 packages.
RUN pip3 install --upgrade pip && \
  pip3 install requests beautifulsoup4 && \
  mkdir /root/app

COPY app /root/app
