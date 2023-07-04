FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

RUN apt-get update && apt-get install -y git htop build-essential \
    gdb lcov patchelf python3-pip python3-venv tcl \
    libexpat1-dev libffi-dev zlib1g-dev libgdbm-dev libgdbm-compat-dev \
    libssl-dev libsqlite3-dev uuid-dev \
    liblzma-dev libbz2-dev

RUN /usr/bin/python3 -mpip install -U pip setuptools

COPY ./scripts/portable-python.sh /usr/local/bin/portable-python
COPY ./scripts/portable-python-update-external-libraries.sh /usr/local/bin/portable-python-update-external-libraries
COPY ./scripts/bashrc.sh /root/.bashrc
WORKDIR /src

CMD ["/bin/bash"]
