FROM archlinux

RUN  pacman -Sy --noconfirm \
     make \
     gcc \
     python \
     python-pip \
     ghdl-gcc \
     && python3 -m pip install cocotb==1.6.2 \
     && python3 -m pip install cocotb[bus]==1.6.2 \
     && python3 -m pip install pyuvm==2.7.0 \
     && python3 -m pip install pytest
