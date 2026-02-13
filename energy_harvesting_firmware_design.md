# Ultra-Low-Power Firmware Design for MFC Energy-Harvesting Sensor Node

## Assumptions and Constants
- Energy source: microbial fuel cell (MFC) charging a 10–25 F supercapacitor through a boost harvester.
- Supercapacitor operating window: `2.1 V` (brownout floor) to `2.7 V` (upper operating limit).
- LoRa packet transmit energy: `0.2 J` per packet.
- Minimum safe transmit voltage: `2.5 V`.
- MCU deep sleep current target: `< 10 µA`.
- Watchdog reset trigger during active work: `< 2.0 V`.
- Temperature cold threshold: `40 °F` (≈ `4.4 °C`).

Derived useful values (example capacitor sizes):
- Stored energy in capacitor: `E = 0.5 * C * V^2`
- Available energy from `2.7 V` to `2.5 V`:
  - `C=10 F`: `0.5*10*(2.7^2 - 2.5^2) ≈ 5.2 J`
  - `C=25 F`: `0.5*25*(2.7^2 - 2.5^2) ≈ 13.0 J`
- Energy margin from `2.5 V` to `2.1 V`:
  - `C=10 F`: `0.5*10*(2.5^2 - 2.1^2) ≈ 9.2 J`
  - `C=25 F`: `0.5*25*(2.5^2 - 2.1^2) ≈ 23.0 J`

---

## 1) Firmware State Machine

States:
1. `SLEEP`
2. `CHARGE_MONITOR`
3. `SENSOR_READ`
4. `TRANSMIT`
5. `DATA_LOG`

### State behaviors
- **SLEEP**
  - MCU in deepest sleep, RTC or low-power timer wake.
  - Radio and high-draw sensors power-gated OFF.
  - Wake periodically (e.g., every 5–15 min) into `CHARGE_MONITOR`.

- **CHARGE_MONITOR**
  - Read supercap voltage using ADC.
  - Update charge profile timing (`2.1 V → 2.5 V` duration estimator).
  - Evaluate thermal flag (`temp < 40 °F`).
  - Decide if enough energy to sample and/or transmit.

- **SENSOR_READ**
  - If `Vcap >= 2.2 V`, power and sample low-power T/H sensor.
  - If high-draw sensors exist, only enable when `Vcap >= 2.5 V`.
  - Package reading with timestamp and status flags.

- **DATA_LOG**
  - Write measurement record into FRAM queue/ring buffer.
  - Mark record as `pending_tx`.

- **TRANSMIT**
  - Only enter if `Vcap >= 2.5 V` and transmit timer expired.
  - Bring up radio, send oldest `pending_tx` payload(s).
  - Wait for ACK (with timeout/retry bounds).
  - On ACK, mark corresponding FRAM records as `acked` (or delete from queue).
  - If no ACK, leave as pending and return to `SLEEP`.

---

## 2) Adaptive Duty Cycling Logic

Measure time to charge from `2.1 V` to `2.5 V`:
- Track timestamp when voltage first falls to/below `2.1 V` (`t_low`).
- Track timestamp when voltage next reaches/exceeds `2.5 V` (`t_ready`).
- `charge_time = t_ready - t_low`.

Transmit interval selection:
- `charge_time > 24 h` → base interval `24 h`
- `6 h <= charge_time <= 24 h` → base interval `6 h`
- `charge_time < 6 h` → base interval `1 h`

Optional robustness: use moving average over last N cycles (e.g., N=3) to avoid oscillation.

---

## 3) Power Gating Rules

- If `Vcap < 2.5 V`:
  - Radio OFF.
  - High-draw sensors OFF.
- If `Vcap >= 2.2 V`:
  - Permit low-power temperature/humidity read.
- If `Vcap < 2.2 V`:
  - Skip sensor read; only housekeeping and sleep.

All peripheral rails should be controlled by GPIO load switches or regulator enable pins.

---

## 4) Thermal Mode Flag

When `Temperature < 40 °F`:
- `thermal_mode = TRUE`
- Effective transmit interval = `2 × base_interval`
- Sensor sampling rate reduced by `75%` (i.e., sample interval multiplied by 4)

When `Temperature >= 40 °F`:
- `thermal_mode = FALSE`
- Use base duty-cycle schedule.

Rationale: cold conditions typically reduce effective power generation and can impact RF/system efficiency.

---

## 5) Data Integrity with FRAM

FRAM record fields (example):
- `record_id`
- `timestamp`
- `vcap_mV`
- `temperature`
- `humidity`
- `thermal_mode`
- `status` (`pending_tx`, `acked`)
- `crc`

Policy:
- Every sensor read is written to FRAM before any transmit attempt.
- Transmission always uses oldest `pending_tx` first (FIFO).
- Only set `acked` upon confirmed ACK from gateway/network.
- On reboot, resume from FRAM queue and retransmit pending data.

---

## 6) Watchdog and Brownout Handling

- Enable watchdog timer in active states.
- During `SENSOR_READ`, `DATA_LOG`, `TRANSMIT`, continuously validate voltage.
- If `Vcap < 2.0 V` at any active step:
  - Immediate safe shutdown of radio/sensors.
  - Trigger software reset (or allow watchdog reset) to return to a known low-power boot path.
- Boot path should prioritize entering `SLEEP` if `Vcap < 2.2 V`.

---

## Pseudocode

```pseudo
constants:
  V_BROWNOUT = 2.1
  V_WDOG_RESET = 2.0
  V_SENSOR_MIN = 2.2
  V_TX_MIN = 2.5
  TEMP_COLD_F = 40.0

  TX_INT_1H  = 1 hour
  TX_INT_6H  = 6 hours
  TX_INT_24H = 24 hours

state = SLEEP
thermal_mode = false
base_tx_interval = TX_INT_24H
effective_tx_interval = TX_INT_24H
sample_interval = DEFAULT_SAMPLE_INTERVAL

charge_t_low = INVALID
charge_t_ready = INVALID
charge_time_estimate = UNKNOWN

on_boot:
  init_adc_rtc_watchdog_fram()
  power_off_radio()
  power_off_high_draw_sensors()
  go_to_state(SLEEP)

main_loop:
  while true:
    switch(state):

      case SLEEP:
        enter_deep_sleep_until_rtc_or_interrupt()
        go_to_state(CHARGE_MONITOR)

      case CHARGE_MONITOR:
        vcap = read_supercap_voltage()

        if vcap <= V_BROWNOUT and charge_t_low is INVALID:
          charge_t_low = now()

        if vcap >= V_TX_MIN and charge_t_low is valid:
          charge_t_ready = now()
          charge_time_estimate = moving_average(charge_t_ready - charge_t_low)
          charge_t_low = INVALID
          charge_t_ready = INVALID

        if charge_time_estimate is known:
          if charge_time_estimate > 24h:
            base_tx_interval = TX_INT_24H
          else if charge_time_estimate >= 6h:
            base_tx_interval = TX_INT_6H
          else:
            base_tx_interval = TX_INT_1H

        if vcap >= V_SENSOR_MIN:
          t_f = quick_temp_read_fahrenheit_low_power()
          thermal_mode = (t_f < TEMP_COLD_F)
        else:
          thermal_mode = false  // default conservative if no temp read

        if thermal_mode:
          effective_tx_interval = 2 * base_tx_interval
          sample_interval = 4 * DEFAULT_SAMPLE_INTERVAL
        else:
          effective_tx_interval = base_tx_interval
          sample_interval = DEFAULT_SAMPLE_INTERVAL

        if time_since(last_sample_time) >= sample_interval and vcap >= V_SENSOR_MIN:
          go_to_state(SENSOR_READ)
        else if time_since(last_tx_time) >= effective_tx_interval and vcap >= V_TX_MIN:
          go_to_state(TRANSMIT)
        else:
          go_to_state(SLEEP)

      case SENSOR_READ:
        service_watchdog()
        vcap = read_supercap_voltage()
        if vcap < V_WDOG_RESET:
          safe_shutdown_and_reset()

        power_on_low_power_sensors()
        reading = read_temp_humidity()
        power_off_low_power_sensors()

        reading.vcap = vcap
        reading.thermal_mode = thermal_mode
        reading.timestamp = now()
        last_sample_time = now()

        go_to_state(DATA_LOG)

      case DATA_LOG:
        service_watchdog()
        vcap = read_supercap_voltage()
        if vcap < V_WDOG_RESET:
          safe_shutdown_and_reset()

        fram_append(record=reading, status=pending_tx, crc=calc_crc(reading))

        if time_since(last_tx_time) >= effective_tx_interval and vcap >= V_TX_MIN:
          go_to_state(TRANSMIT)
        else:
          go_to_state(SLEEP)

      case TRANSMIT:
        service_watchdog()
        vcap = read_supercap_voltage()
        if vcap < V_TX_MIN:
          power_off_radio()
          go_to_state(SLEEP)

        power_on_radio()
        pending = fram_get_oldest_pending()

        while pending exists:
          vcap = read_supercap_voltage()
          if vcap < V_WDOG_RESET:
            power_off_radio()
            safe_shutdown_and_reset()

          ok = lora_send_with_ack(pending, timeout, retries)
          if ok:
            fram_mark_acked(pending.record_id)
            pending = fram_get_oldest_pending()
          else:
            break

        power_off_radio()
        last_tx_time = now()
        go_to_state(SLEEP)
```

---

## State Diagram (Text)

```text
                    +-------------------+
                    |       SLEEP       |
                    | deep sleep <10 µA |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    | CHARGE_MONITOR    |
                    | read Vcap, temp,  |
                    | update intervals  |
                    +--+------------+---+
                       |            |
     sample due & V>=2.2V          | tx due & V>=2.5V
                       v            v
                +----------+   +-----------+
                |SENSOR_READ|   | TRANSMIT |
                +-----+----+   +-----+-----+
                      |              |
                      v              |
                 +---------+         |
                 | DATA_LOG|---------+
                 +----+----+
                      |
                      v
                    SLEEP

Guard rails:
- If Vcap < 2.5V => radio/high-draw sensors OFF
- If Vcap < 2.0V in active state => safe shutdown + reset
```

---

## Power Budget Table (Representative)

| Mode / Action | Current (example) | Voltage (V) | Duration per event | Energy per event (approx) | Notes |
|---|---:|---:|---:|---:|---|
| Deep sleep (MCU+RTC) | 6 µA | 2.3 | continuous | 13.8 µW | Meets `<10 µA` requirement |
| CHARGE_MONITOR (ADC + logic) | 150 µA | 2.3 | 100 ms | 34.5 µJ | Keep wake checks brief |
| Low-power T/H sample | 600 µA | 2.3 | 50 ms | 69 µJ | Allowed only `Vcap >= 2.2V` |
| FRAM write record | 2 mA | 2.3 | 5 ms | 23 µJ | Includes metadata + CRC |
| LoRa TX packet + overhead | — | — | per packet | 0.2 J (given) | Allowed only `Vcap >= 2.5V` |
| Radio idle/listen window | 12 mA | 2.5 | 100 ms | 3.0 mJ | Keep ACK window short |

### Daily energy examples for transmit policy
Assuming 1 packet each transmit event:
- 1/day: `0.2 J/day`
- 4/day (every 6 h): `0.8 J/day`
- 24/day (hourly): `4.8 J/day`

Use adaptive schedule to remain energy-neutral with observed charge time.
