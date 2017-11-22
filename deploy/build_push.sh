#!/bin/bash
pip3 install awscli
docker build -t bulletinchat .
docker tag bulletinchat $BASE_IMAGE_URI:$TAG
DOCKER_LOGIN=`aws ecr get-login --region eu-west-1`
eval $DOCKER_LOGIN
docker push $BASE_IMAGE_URI:$TAG
