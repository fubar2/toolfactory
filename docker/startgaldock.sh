docker run -d -p 8080:80 -p 8021:21 -p 8800:8800 -p 9009:9009 \
    --privileged=true -e DOCKER_PARENT=True \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v /s100/galaxy_storage/:/export/ \
    toolfactory
