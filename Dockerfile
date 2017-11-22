

FROM ubuntu
MAINTAINER Xavier Orduña <xorduna@gmail.com>

RUN apt-get update && apt-get -y upgrade
RUN apt-get -y install python3 python3-pip git npm
RUN ln -s /usr/bin/nodejs /usr/bin/node
ADD . /newsbot
WORKDIR /newsbot
RUN make install
