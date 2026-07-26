# Popcornition App

Prosta aplikacja terminalowa do sterowania robotem (silniki DRV8825) na Raspberry Pi.
Kod używa `pigpio` i sprzętowego PWM (`hardware_PWM`) do generowania impulsów STEP.

## Wymagania

- Raspberry Pi z aktywnym daemonem `pigpiod`
- biblioteka Python `pigpio`

Przykładowe uruchomienie na Raspberry Pi:

```bash
sudo apt install pigpio python3-pigpio
sudo pigpiod
python3 popcornition_app.py
```

## Sterowanie

- Strzałki: ruch robota
- `1`-`9`: zmiana prędkości (`9` = najszybciej)
- `q`: wyjście z programu

## Tryb pracy silników

Aplikacja działa w trybie pełnego kroku (`full-step`), bez microstepingu.
Sygnał STEP jest generowany przez `hardware_PWM` na pinach GPIO18 i GPIO19.
