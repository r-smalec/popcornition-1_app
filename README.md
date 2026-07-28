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
- `w`: obrót serwa SG90 przeciwnie do ruchu wskazówek zegara (CCW)
- `s`: obrót serwa SG90 zgodnie z ruchem wskazówek zegara (CW)
- `1`-`9`: zmiana prędkości (`9` = najszybciej)
- `q`: wyjście z programu

## Serwo SG90

- pin sygnałowy serwa: GPIO23 (fizyczny pin 16)
- podczas trzymania `w`/`s` serwo obraca się w wybranym kierunku
- po puszczeniu klawisza serwo zatrzymuje się

## Tryb pracy silników

Aplikacja działa w trybie pełnego kroku (`full-step`), bez microstepingu.
Sygnał STEP jest generowany przez `hardware_PWM` na pinach GPIO18 i GPIO19.
