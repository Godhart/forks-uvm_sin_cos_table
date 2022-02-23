.PHONY: all
all: image

.PHONY: clean
clean:
	docker image rm ghdl-cocotb-pyuvm:upstream-1.6.2-2.7.0

.PHONY: image
image:
	docker build -t ghdl-cocotb-pyuvm:upstream-1.6.2-2.7.0 .
