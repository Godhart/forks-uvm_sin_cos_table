from cocotb.triggers import Join, Combine
from pyuvm import *
import random
import cocotb
import pyuvm
# All testbenches use sin_cos_table_utils, so store it in a central
# place and add its path to the sys path so we can import it
import sys
from pathlib import Path
sys.path.append(str(Path("..").resolve()))
from sin_cos_table_utils import SinCosTableBfm, Phases, sin_value, cos_value, sincostable_prediction

# Sequence classes


class SinCosTableSeqItem(uvm_sequence_item):

    def __init__(self, name, phase, phase_v):
        super().__init__(name)
        self._phase = phase
        self.phase_v = phase_v
        self._sin = None
        self._sin_overridden = False
        self._cos = None
        self._cos_overridden = False
        self.allow_override = False

    @property
    def phase(self):
        return self._phase

    @phase.setter
    def phase(self, value):
        self._phase = value
        self._sin = None
        self._sin_overridden = False
        self._cos = None
        self._cos_overridden = False

    @property
    def sin(self):
        if self.phase is None:
            return None
        if self._sin is None:
            self._sin = sin_value(self._phase)
        return self._sin

    @sin.setter
    def sin(self, value):
        if not self.allow_override:
            raise PermissionError("[ERROR]   SinCosTableSeqItem: "
                                  "attempt to override 'sin' field without 'allow_override' set")
        self._sin = value
        self._sin_overridden = True

    @property
    def cos(self):
        if self.phase is None:
            return None
        if self._cos is None:
            self._cos = cos_value(self._phase)
        return self._cos

    @cos.setter
    def cos(self, value):
        if not self.allow_override:
            raise PermissionError("[ERROR]   SinCosTableSeqItem: "
                                  "attempt to override 'cos' field without 'allow_override' set")
        self._cos = value
        self._cos_overridden = True

    @property
    def overridden(self):
        return self._sin_overridden or self._cos_overridden

    def randomize_phase(self):
        self.phase = random.randint(0, 4095)

    def randomize_phase_v(self):
        tmp = [0]*5
        tmp[random.randint(0, 4)] = 1
        self.phase_v = tmp

    def randomize(self):
        self.randomize_phase()
        self.randomize_phase_v()

    def __eq__(self, other):
        for prop in ("phase", "phase_v", "sin", "cos"):
            # TODO: not sure if phase_v should be here as it flow control related
            #  so captured value (list) wont be same as driven value (list)
            if getattr(self, prop) != getattr(other, prop):
                return False
        return True

    def __str__(self):
        return f"{self.get_name()} : phase: {self.phase}, \
            phase_v: {self.phase_v}, sin: {self.sin}, cos: {self.cos}"


_PHASE_TOTAL_VALUES = len(Phases) + 2
# NOTE: +2 due to sequential delays in DUT. Otherwise test stops before last values are captured by monitor

_PHASE_VALUES_STEP = 1
# NOTE: increase step to skip some values and speed-up tests (but coverage won't be checked in that case)


class SequentialSeq(uvm_sequence):
    async def body(self):
        for phase in range(0, _PHASE_TOTAL_VALUES, _PHASE_VALUES_STEP):
            seqi = SinCosTableSeqItem("sincos_tr", phase, None)
            await self.start_item(seqi)
            seqi.randomize_phase_v()
            await self.finish_item(seqi)


class RandomSeq(uvm_sequence):
    async def body(self):
        for phase in random.sample(list(range(0, _PHASE_TOTAL_VALUES, _PHASE_VALUES_STEP)),
                                   int(_PHASE_TOTAL_VALUES / _PHASE_VALUES_STEP)):
            seqi = SinCosTableSeqItem("sincos_tr", phase, None)
            await self.start_item(seqi)
            seqi.randomize_phase_v()
            await self.finish_item(seqi)


class TestAllSeq(uvm_sequence):

    async def body(self):
        seqr = ConfigDB().get(None, "", "SEQR")
        sequent = SequentialSeq("sequential")
        random = RandomSeq("random")
        await sequent.start(seqr)
        await random.start(seqr)


class TestAllForkSeq(uvm_sequence):

    async def body(self):
        seqr = ConfigDB().get(None, "", "SEQR")
        sequent = SequentialSeq("sequential")
        random = RandomSeq("random")
        sequent_task = cocotb.fork(sequent.start(seqr))
        random_task = cocotb.fork(random.start(seqr))
        await Combine(Join(sequent_task), Join(random_task))


class SinCosTableSeq(uvm_sequence):
    # NOTE: wasn't used since sincos below isn't used
    def __init__(self, name, phase, phase_v):
        super().__init__(name)
        self.phase = phase
        self.phase_v = phase_v
        self.sin = None
        self.cos = None

    async def body(self):
        seq_item = SinCosTableSeqItem("seq_item", self.phase, self.phase_v)
        await self.start_item(seq_item)
        await self.finish_item(seq_item)
        self.sin = seq_item.sin
        self.cos = seq_item.cos


async def sincos(seqr, phase, phase_v):
    # NOTE: wasn't used
    seq = SinCosTableSeq("seq", phase, phase_v)
    await seq.start(seqr)
    return seq.sin, seq.cos


class Driver(uvm_driver):
    def build_phase(self):
        self.ap = uvm_analysis_port("ap", self)

    def start_of_simulation_phase(self):
        self.bfm = SinCosTableBfm()

    async def launch_tb(self):
        await self.bfm.reset()
        self.bfm.start_bfm()

    async def run_phase(self):
        await self.launch_tb()
        while True:
            input_data = await self.seq_item_port.get_next_item()
            await self.bfm.issue_input_data(input_data.phase, input_data.phase_v)
            result = await self.bfm.get_result()
            self.ap.write(result)
            input_data.allow_override = True
            input_data.sin = result[0]
            input_data.cos = result[1]
            self.seq_item_port.item_done()


class Coverage(uvm_subscriber):

    def end_of_elaboration_phase(self):
        self.cvg = set()

    def write(self, input_data):
        (phase, _) = input_data
        self.cvg.add(phase)

    def report_phase(self):
        try:
            disable_errors = ConfigDB().get(
                self, "", "DISABLE_COVERAGE_ERRORS")
        except UVMConfigItemNotFound:
            disable_errors = False
        if not disable_errors:
            if _PHASE_VALUES_STEP == 1:
                if len(set(Phases) - self.cvg) > 0:
                    self.logger.error(
                        f"Functional coverage error. Missed: {set(Phases)-self.cvg}")
                    assert False
                else:
                    self.logger.info("Covered all phases")
                    assert True


class Scoreboard(uvm_component):

    def build_phase(self):
        self.input_data_fifo = uvm_tlm_analysis_fifo("input_data_fifo", self)
        self.result_fifo = uvm_tlm_analysis_fifo("result_fifo", self)
        self.input_data_get_port = uvm_get_port("input_data_get_port", self)
        self.result_get_port = uvm_get_port("result_get_port", self)
        self.input_data_export = self.input_data_fifo.analysis_export
        self.result_export = self.result_fifo.analysis_export

    def connect_phase(self):
        self.input_data_get_port.connect(self.input_data_fifo.get_export)
        self.result_get_port.connect(self.result_fifo.get_export)

    def check_phase(self):
        passed = True
        try:
            self.errors = ConfigDB().get(self, "", "CREATE_ERRORS")
        except UVMConfigItemNotFound:
            self.errors = False
        while self.result_get_port.can_get():
            (_, actual_result) = self.result_get_port.try_get()
            (get_success, input_data) = self.input_data_get_port.try_get()
            # TODO: how is determined value for 'get_success' ?
            if not get_success:
                self.logger.critical(f"no input data registered for response {actual_result}")
            else:
                (phase, phase_v) = input_data
                predicted_result = sincostable_prediction(phase, phase_v, self.errors)
                # TODO: probably sequence items ('ideal' and actual) should be compared
                #  instead of predicted and actual results
                if predicted_result == actual_result:
                    self.logger.info(f"PASSED: sin({phase})={actual_result[0]}; "
                                     f"cos({phase})={actual_result[1]}")
                else:
                    self.logger.error(f"FAILED: sin({phase})={actual_result[0]}, expected({predicted_result[0]}); "
                                      f"cos({phase})={actual_result[1]}, expected({predicted_result[1]})")
                    passed = False
        assert passed


class Monitor(uvm_component):
    def __init__(self, name, parent, method_name):
        super().__init__(name, parent)
        self.method_name = method_name

    def build_phase(self):
        self.ap = uvm_analysis_port("ap", self)
        self.bfm = SinCosTableBfm()
        self.get_method = getattr(self.bfm, self.method_name)

    async def run_phase(self):
        while True:
            datum = await self.get_method()
            self.logger.debug(f"MONITORED {datum}")
            self.ap.write(datum)


class SinCosTableEnv(uvm_env):

    def build_phase(self):
        self.seqr = uvm_sequencer("seqr", self)
        ConfigDB().set(None, "*", "SEQR", self.seqr)
        self.driver = Driver.create("driver", self)
        self.input_data_mon = Monitor("input_data_mon", self, "get_input_data")
        self.coverage = Coverage("coverage", self)
        self.scoreboard = Scoreboard("scoreboard", self)

    def connect_phase(self):
        self.driver.seq_item_port.connect(self.seqr.seq_item_export)
        self.input_data_mon.ap.connect(self.scoreboard.input_data_export)
        self.input_data_mon.ap.connect(self.coverage.analysis_export)
        self.driver.ap.connect(self.scoreboard.result_export)


@pyuvm.test()
class SinCosTableTest(uvm_test):
    """Test SinCosTable with sequential and random values"""

    def build_phase(self):
        self.env = SinCosTableEnv("env", self)

    def end_of_elaboration_phase(self):
        self.test_all = TestAllSeq.create("test_all")

    async def run_phase(self):
        self.raise_objection()
        await self.test_all.start()
        self.drop_objection()


@pyuvm.test()
class ParallelTest(SinCosTableTest):
    """Test ALU random and max forked"""

    def build_phase(self):
        uvm_factory().set_type_override_by_type(TestAllSeq, TestAllForkSeq)
        super().build_phase()


@pyuvm.test(expect_fail=True)
class SinCosTableTestErrors(SinCosTableTest):
    """Test ALU with errors on all operations"""

    def start_of_simulation_phase(self):
        ConfigDB().set(None, "*", "CREATE_ERRORS", True)
