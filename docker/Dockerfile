FROM ubuntu:20.04

RUN  apt-get update && \
     DEBIAN_FRONTEND=noninteractive apt-get install \
     -y --no-install-recommends \
     make \
     gcc \
     g++ \
     python3 \
     python3-dev \
     python3-pip \
     ghdl \
     && rm -rf /var/lib/apt/lists/* \
     && python3 -m pip install cocotb==1.6.2 \
     && python3 -m pip install cocotb[bus]==1.6.2 \
     && python3 -m pip install pyuvm==2.7.0 \
     && python3 -m pip install pytest
