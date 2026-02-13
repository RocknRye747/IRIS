from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Protocol


class State(Enum):
    SLEEP = auto()
    CHARGE_MONITOR = auto()
    SENSOR_READ = auto()
    TRANSMIT = auto()
    DATA_LOG = auto()


@dataclass(frozen=True)
class FirmwareConfig:
    v_brownout: float = 2.1
    v_wdog_reset: float = 2.0
    v_sensor_min: float = 2.2
    v_tx_min: float = 2.5
    temp_cold_f: float = 40.0

    tx_interval_1h_s: int = 3600
    tx_interval_6h_s: int = 21600
    tx_interval_24h_s: int = 86400

    default_sample_interval_s: int = 3600
    charge_time_window_size: int = 3


@dataclass
class SensorReading:
    timestamp_s: int
    vcap_v: float
    temperature_f: float
    humidity_pct: float
    thermal_mode: bool


@dataclass
class FrRecord:
    record_id: int
    reading: SensorReading
    acked: bool = False


class HardwareInterface(Protocol):
    def now_s(self) -> int: ...

    def read_supercap_voltage(self) -> float: ...

    def quick_temp_read_f(self) -> float: ...

    def read_temp_humidity(self) -> tuple[float, float]: ...

    def power_on_radio(self) -> None: ...

    def power_off_radio(self) -> None: ...

    def power_on_low_power_sensors(self) -> None: ...

    def power_off_low_power_sensors(self) -> None: ...

    def power_off_high_draw_sensors(self) -> None: ...

    def lora_send_with_ack(self, payload: FrRecord) -> bool: ...

    def enter_deep_sleep(self) -> None: ...

    def reset_system(self) -> None: ...

    def service_watchdog(self) -> None: ...


@dataclass
class FirmwareController:
    hw: HardwareInterface
    cfg: FirmwareConfig = field(default_factory=FirmwareConfig)

    state: State = State.SLEEP
    thermal_mode: bool = False

    base_tx_interval_s: int = field(init=False)
    effective_tx_interval_s: int = field(init=False)
    sample_interval_s: int = field(init=False)

    charge_t_low_s: Optional[int] = None
    charge_durations_s: List[int] = field(default_factory=list)

    last_sample_time_s: int = 0
    last_tx_time_s: int = 0

    fram: List[FrRecord] = field(default_factory=list)
    next_record_id: int = 1
    pending_reading: Optional[SensorReading] = None

    def __post_init__(self) -> None:
        self.base_tx_interval_s = self.cfg.tx_interval_24h_s
        self.effective_tx_interval_s = self.cfg.tx_interval_24h_s
        self.sample_interval_s = self.cfg.default_sample_interval_s

    def boot(self) -> None:
        self.hw.power_off_radio()
        self.hw.power_off_high_draw_sensors()
        self.state = State.SLEEP

    def run_once(self) -> State:
        if self.state == State.SLEEP:
            self._sleep()
        elif self.state == State.CHARGE_MONITOR:
            self._charge_monitor()
        elif self.state == State.SENSOR_READ:
            self._sensor_read()
        elif self.state == State.DATA_LOG:
            self._data_log()
        elif self.state == State.TRANSMIT:
            self._transmit()
        return self.state

    def _sleep(self) -> None:
        self.hw.enter_deep_sleep()
        self.state = State.CHARGE_MONITOR

    def _charge_monitor(self) -> None:
        vcap = self.hw.read_supercap_voltage()
        now_s = self.hw.now_s()

        if vcap <= self.cfg.v_brownout and self.charge_t_low_s is None:
            self.charge_t_low_s = now_s

        if vcap >= self.cfg.v_tx_min and self.charge_t_low_s is not None:
            duration = max(0, now_s - self.charge_t_low_s)
            self.charge_durations_s.append(duration)
            if len(self.charge_durations_s) > self.cfg.charge_time_window_size:
                self.charge_durations_s.pop(0)
            self.charge_t_low_s = None

        self._update_duty_cycle()
        self._update_thermal_mode(vcap)

        if self._sample_due(now_s) and vcap >= self.cfg.v_sensor_min:
            self.state = State.SENSOR_READ
        elif self._tx_due(now_s) and vcap >= self.cfg.v_tx_min:
            self.state = State.TRANSMIT
        else:
            self.state = State.SLEEP

    def _update_duty_cycle(self) -> None:
        if self.charge_durations_s:
            avg = sum(self.charge_durations_s) / len(self.charge_durations_s)
            if avg > self.cfg.tx_interval_24h_s:
                self.base_tx_interval_s = self.cfg.tx_interval_24h_s
            elif avg >= self.cfg.tx_interval_6h_s:
                self.base_tx_interval_s = self.cfg.tx_interval_6h_s
            else:
                self.base_tx_interval_s = self.cfg.tx_interval_1h_s

        if self.thermal_mode:
            self.effective_tx_interval_s = self.base_tx_interval_s * 2
            self.sample_interval_s = self.cfg.default_sample_interval_s * 4
        else:
            self.effective_tx_interval_s = self.base_tx_interval_s
            self.sample_interval_s = self.cfg.default_sample_interval_s

    def _update_thermal_mode(self, vcap: float) -> None:
        if vcap >= self.cfg.v_sensor_min:
            temp_f = self.hw.quick_temp_read_f()
            self.thermal_mode = temp_f < self.cfg.temp_cold_f
        else:
            self.thermal_mode = False

        if self.thermal_mode:
            self.effective_tx_interval_s = self.base_tx_interval_s * 2
            self.sample_interval_s = self.cfg.default_sample_interval_s * 4
        else:
            self.effective_tx_interval_s = self.base_tx_interval_s
            self.sample_interval_s = self.cfg.default_sample_interval_s

    def _sensor_read(self) -> None:
        self._guard_voltage_or_reset()

        self.hw.power_on_low_power_sensors()
        temp_f, humidity = self.hw.read_temp_humidity()
        self.hw.power_off_low_power_sensors()

        now_s = self.hw.now_s()
        self.pending_reading = SensorReading(
            timestamp_s=now_s,
            vcap_v=self.hw.read_supercap_voltage(),
            temperature_f=temp_f,
            humidity_pct=humidity,
            thermal_mode=self.thermal_mode,
        )
        self.last_sample_time_s = now_s
        self.state = State.DATA_LOG

    def _data_log(self) -> None:
        self._guard_voltage_or_reset()

        if self.pending_reading is None:
            self.state = State.SLEEP
            return

        self.fram.append(
            FrRecord(record_id=self.next_record_id, reading=self.pending_reading, acked=False)
        )
        self.next_record_id += 1
        self.pending_reading = None

        now_s = self.hw.now_s()
        vcap = self.hw.read_supercap_voltage()
        if self._tx_due(now_s) and vcap >= self.cfg.v_tx_min:
            self.state = State.TRANSMIT
        else:
            self.state = State.SLEEP

    def _transmit(self) -> None:
        self._guard_voltage_or_reset()

        vcap = self.hw.read_supercap_voltage()
        if vcap < self.cfg.v_tx_min:
            self.hw.power_off_radio()
            self.state = State.SLEEP
            return

        self.hw.power_on_radio()
        for record in self._pending_records():
            self._guard_voltage_or_reset()
            if self.hw.lora_send_with_ack(record):
                record.acked = True
            else:
                break
        self.hw.power_off_radio()

        self.last_tx_time_s = self.hw.now_s()
        self.state = State.SLEEP

    def _guard_voltage_or_reset(self) -> None:
        self.hw.service_watchdog()
        if self.hw.read_supercap_voltage() < self.cfg.v_wdog_reset:
            self.hw.power_off_radio()
            self.hw.power_off_low_power_sensors()
            self.hw.power_off_high_draw_sensors()
            self.hw.reset_system()

    def _pending_records(self) -> List[FrRecord]:
        return [record for record in self.fram if not record.acked]

    def _sample_due(self, now_s: int) -> bool:
        return (now_s - self.last_sample_time_s) >= self.sample_interval_s

    def _tx_due(self, now_s: int) -> bool:
        return (now_s - self.last_tx_time_s) >= self.effective_tx_interval_s
