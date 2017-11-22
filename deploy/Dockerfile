

FROM ubuntu
MAINTAINER Sergey Chvalyuk <grubberr@gmail.com>

RUN apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv EA312927
RUN echo "deb http://repo.mongodb.org/apt/ubuntu xenial/mongodb-org/3.2 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-3.2.list
RUN apt-get update && apt-get -y upgrade
RUN apt-get install -y mongodb-org=3.2.11 mongodb-org-server=3.2.11 mongodb-org-shell=3.2.11 mongodb-org-mongos=3.2.11 mongodb-org-tools=3.2.11
RUN apt-get -y install python3 python3-pip git npm
RUN mkdir -p /data/db && \
    ln -s /usr/bin/nodejs /usr/bin/node
