from __future__ import annotations

from dataclasses import dataclass

from firmware_controller import FirmwareController, State


@dataclass
class FakeHardware:
    now: int = 0
    vcap: float = 2.6
    temp_quick_f: float = 60.0
    temp_sensor_f: float = 60.0
    humidity: float = 50.0
    ack_result: bool = True

    radio_on: bool = False
    low_sensor_on: bool = False
    reset_called: bool = False
    sleep_calls: int = 0
    watchdog_calls: int = 0

    def now_s(self) -> int:
        return self.now

    def read_supercap_voltage(self) -> float:
        return self.vcap

    def quick_temp_read_f(self) -> float:
        return self.temp_quick_f

    def read_temp_humidity(self) -> tuple[float, float]:
        return self.temp_sensor_f, self.humidity

    def power_on_radio(self) -> None:
        self.radio_on = True

    def power_off_radio(self) -> None:
        self.radio_on = False

    def power_on_low_power_sensors(self) -> None:
        self.low_sensor_on = True

    def power_off_low_power_sensors(self) -> None:
        self.low_sensor_on = False

    def power_off_high_draw_sensors(self) -> None:
        return None

    def lora_send_with_ack(self, payload) -> bool:
        return self.ack_result

    def enter_deep_sleep(self) -> None:
        self.sleep_calls += 1

    def reset_system(self) -> None:
        self.reset_called = True

    def service_watchdog(self) -> None:
        self.watchdog_calls += 1


def test_adaptive_duty_cycle_levels() -> None:
    hw = FakeHardware()
    ctrl = FirmwareController(hw=hw)

    ctrl.charge_durations_s = [26 * 3600]
    ctrl._update_duty_cycle()
    assert ctrl.base_tx_interval_s == 24 * 3600

    ctrl.charge_durations_s = [8 * 3600]
    ctrl._update_duty_cycle()
    assert ctrl.base_tx_interval_s == 6 * 3600

    ctrl.charge_durations_s = [2 * 3600]
    ctrl._update_duty_cycle()
    assert ctrl.base_tx_interval_s == 3600


def test_thermal_mode_doubles_tx_interval_and_reduces_sampling() -> None:
    hw = FakeHardware(vcap=2.3, temp_quick_f=30.0)
    ctrl = FirmwareController(hw=hw)

    ctrl.base_tx_interval_s = 3600
    ctrl._update_thermal_mode(hw.vcap)

    assert ctrl.thermal_mode is True
    assert ctrl.effective_tx_interval_s == 7200
    assert ctrl.sample_interval_s == ctrl.cfg.default_sample_interval_s * 4


def test_power_gating_prevents_transmit_when_below_2p5v() -> None:
    hw = FakeHardware(vcap=2.4)
    ctrl = FirmwareController(hw=hw)
    ctrl.state = State.TRANSMIT

    ctrl.run_once()

    assert ctrl.state == State.SLEEP
    assert hw.radio_on is False


def test_fram_records_persist_until_ack() -> None:
    hw = FakeHardware(vcap=2.6, ack_result=False)
    ctrl = FirmwareController(hw=hw)

    ctrl.state = State.SENSOR_READ
    ctrl.run_once()  # SENSOR_READ -> DATA_LOG
    ctrl.run_once()  # DATA_LOG -> SLEEP

    assert len(ctrl.fram) == 1
    assert ctrl.fram[0].acked is False

    ctrl.state = State.TRANSMIT
    ctrl.run_once()
    assert ctrl.fram[0].acked is False

    hw.ack_result = True
    ctrl.state = State.TRANSMIT
    ctrl.run_once()
    assert ctrl.fram[0].acked is True


def test_watchdog_resets_if_voltage_drops_below_2p0v() -> None:
    hw = FakeHardware(vcap=1.95)
    ctrl = FirmwareController(hw=hw)
    ctrl.state = State.SENSOR_READ

    ctrl.run_once()

    assert hw.reset_called is True
