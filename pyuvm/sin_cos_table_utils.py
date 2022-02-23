import cocotb
from cocotb.triggers import FallingEdge
from cocotb.queue import QueueEmpty, Queue
import math
import logging
from cocotb.binary import BinaryValue, BinaryRepresentation

from pyuvm import utility_classes

logging.basicConfig(level=logging.NOTSET)
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


Phases = list(range(0, 4096))

_PRECALCULATE = False


def _sin_value(phase):
    return round(32767*math.sin(2*math.pi*phase/(1*4096)))


def _cos_value(phase):
    return round(32767*math.cos(2*math.pi*phase/(1*4096)))


if _PRECALCULATE:
    # NOTE: a table with precalculated values to avoid extra calculations while running
    _sin_values = [_sin_value(v) for v in Phases]
    _cos_values = [_cos_value(v) for v in Phases]


def sin_value(phase):
    if _PRECALCULATE:
        return _sin_values[phase]
    return _sin_value(phase)


def cos_value(phase):
    if _PRECALCULATE:
        return _cos_values[phase]
    return _cos_value(phase)


def sincostable_prediction(phase, phase_v, error=False):
    """Python model of the SinCosTable"""

    assert 0 <= phase <= 4095,\
        "SinCosTable Phase must be in range 0 - 4095"
    if isinstance(phase_v, (list, tuple)):
        assert all(v in (0, 1) for v in phase_v),\
            "SinCosTable Phase_V items should be of ones or zeros"
        assert sum(phase_v) == 1,\
            "SinCosTable Phase_V items should contain only single one item"
    else:
        assert phase_v in (0, 1), "SinCosTable Phase_V item should be one or zero"

    if not error:
        result = (sin_value(phase), cos_value(phase))
    else:
        result = (sin_value(phase + (len(Phases) >> 4)), cos_value(phase + (len(Phases) >> 4)))

    return result


def get_uint(signal):
    try:
        sig = int(signal.value)
    except ValueError:
        sig = 0
    return sig


def get_sint(signal):
    try:
        val = BinaryValue(
            value=signal.value.binstr,
            n_bits=signal.value.n_bits,
            bigEndian=signal.value.big_endian,
            binaryRepresentation=BinaryRepresentation.TWOS_COMPLEMENT)
        sig = int(val.value)
    except ValueError:
        sig = 0
    return sig


class SinCosTableBfm(metaclass=utility_classes.Singleton):  # TODO: why singleton? (IS it scalable for complex uses?)
    def __init__(self):
        self.dut = cocotb.top                               # TODO: how to attach to nested units?
        self.driver_queue = Queue(maxsize=1)                # TODO: queue sizes?
        self.input_mon_queue = Queue(maxsize=0)             # TODO: queue sizes?
        self.result_mon_queue = Queue(maxsize=0)            # TODO: queue sizes?

    async def issue_input_data(self, phase, phase_v):
        phase_tuple = (phase % 4096, phase_v)
        await self.driver_queue.put(phase_tuple)

    async def get_input_data(self):
        value = await self.input_mon_queue.get()
        return value

    async def get_result(self):
        result = await self.result_mon_queue.get()
        return result

    async def reset(self):
        # Nothing to reset. Just set zeros on input and wait for clock
        self.dut.iPhase.value = 0
        self.dut.iPHASE_V.value = 0
        await FallingEdge(self.dut.iCLK)    # TODO: why falling edge? is it problems with rising?

    async def driver_bfm(self):
        self.dut.iPHASE.value = 0
        self.dut.iPHASE_V.value = 0
        while True:
            await FallingEdge(self.dut.iCLK)
            try:
                (phase, phase_v) = self.driver_queue.get_nowait()
            except QueueEmpty:
                self.dut.iPHASE_V.value = 0
                continue

            self.dut.iPHASE.value = phase
            for pv in phase_v:
                self.dut.iPHASE_V.value = pv
                await FallingEdge(self.dut.iCLK)

    async def input_data_mon_bfm(self):
        while True:
            await FallingEdge(self.dut.iCLK)
            valid = get_uint(self.dut.iPHASE_V)
            if valid == 1:
                phase_tuple = (get_uint(self.dut.iPHASE), valid)
                self.input_mon_queue.put_nowait(phase_tuple)

    async def result_mon_bfm(self):
        while True:
            await FallingEdge(self.dut.iCLK)
            valid = get_uint(self.dut.oSINCOS_V)
            if valid:
                result = (get_sint(self.dut.oSIN),
                          get_sint(self.dut.oCOS))
                self.result_mon_queue.put_nowait(result)

    def start_bfm(self):
        cocotb.start_soon(self.driver_bfm())
        cocotb.start_soon(self.input_data_mon_bfm())
        cocotb.start_soon(self.result_mon_bfm())

    # TODO: ensure interface is covered by BFM (all required signals present on DUT, no unknown signals)
