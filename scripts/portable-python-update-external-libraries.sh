#!/bin/sh
set -e

CPYTHON3_VERSION="${1}"
CPYTHON3_VERSION="${CPYTHON3_VERSION:=3.10.8}"

CPYTHON3_EXTERNAL_PACKAGES="${2}"

echo "
  Building CPython: ${CPYTHON3_VERSION}
External libraries: ${CPYTHON3_EXTERNAL_PACKAGES}
"

TMP_PATH="/tmp/portable-python"

portable-python -c portable-python.yml build ${CPYTHON3_VERSION} -m libffi,zlib,xz,bzip2,readline,openssl,sqlite,bdb,gdbm,uuid

if [ "${CPYTHON3_EXTERNAL_PACKAGES}" == "" ]; then
    echo "Build finished (without external libraries)"
    exit
fi

if [ ! -x /src/dist/cpython-${CPYTHON3_VERSION}-linux-x86_64.tar.gz ]; then
    set -x
    mkdir -p "${TMP_PATH}"
    tar -C ${TMP_PATH}/ -xf /src/dist/cpython-${CPYTHON3_VERSION}-linux-x86_64.tar.gz
    ${TMP_PATH}/${CPYTHON3_VERSION}/bin/pip3 install ${CPYTHON3_EXTERNAL_PACKAGES}
    tar -czvf /src/dist/cpython-${CPYTHON3_VERSION}-linux-x86_64_UPDATED.tar.gz -C ${TMP_PATH}/ ${CPYTHON3_VERSION}
fi
