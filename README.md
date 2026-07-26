# Popcornition App

Prosta aplikacja terminalowa do sterowania robotem (silniki DRV8825) na Raspberry Pi.

## Sterowanie

- Strzałki: ruch robota
- `1`-`9`: zmiana prędkości (`9` = najszybciej)
- `q`: wyjście z programu

## Tryb pracy silników

Aplikacja działa w trybie pełnego kroku (`full-step`), bez microstepingu.
Dla poziomu prędkości `9` opóźnienie impulsów jest wyłączone, co daje maksymalną częstotliwość kroków możliwą do uzyskania przez ten kod i bibliotekę GPIO.
