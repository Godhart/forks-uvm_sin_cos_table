CWD=$(shell pwd)
COCOTB_REDUCED_LOG_FMT = True
SIM ?= ghdl
TOPLEVEL_LANG ?= vhdl
ifeq ($(TOPLEVEL_LANG),verilog)
    VERILOG_SOURCES =$(CWD)/../sin_cos_table.sv
else ifeq ($(TOPLEVEL_LANG),vhdl)
    VHDL_SOURCES=$(CWD)/../sin_cos_table.vhd
else
    $(error "A valid value (verilog or vhdl) was not provided for TOPLEVEL_LANG=$(TOPLEVEL_LANG)")
endif
MODULE := testbench
TOPLEVEL = sin_cos_table
GHDL_ARGS := --ieee=synopsys
COCOTB_HDL_TIMEUNIT = 100ps
COCOTB_HDL_TIMEPRECISION = 100ps
include $(shell cocotb-config --makefiles)/Makefile.sim
include ./cleanall.mk
