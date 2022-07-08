#!/bin/bash

repo=${{ github.repository }}
END=5
for i in $(seq 1 $END);
  do docker build . -f Dockerfile_temp \
  --label  org.opencontainers.image.source=https://github.com/$repo --no-cache \
  --build-arg I=$i -t ghcr.io/$repo/temp:$i  ;
  docker push ghcr.io/$repo/temp:$i
done

# same tag different image by different build-arg
for i in $(seq 1 $END);
  do docker build . -f Dockerfile_temp \
  --label  org.opencontainers.image.source=https://github.com/$repo --no-cache \
  --build-arg I=2_$i -t ghcr.io/$repo/temp:$i  ;
  docker push ghcr.io/$repo/temp:$i
done
