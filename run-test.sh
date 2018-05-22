#!/bin/bash

docker run \
  --interactive \
  --tty \
  --name sync-osmtw1 \
  --volume ~/osm-data:/root/osm-data \
  --workdir /root/app \
  mapsforge-writer:18.04
