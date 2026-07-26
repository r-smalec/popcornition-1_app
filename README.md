# Popcornition App

Prosta aplikacja terminalowa do sterowania robotem (silniki DRV8825) na Raspberry Pi.

## Sterowanie

- Strzałki: ruch robota
- `1`-`9`: zmiana prędkości (`9` = najszybciej)
- `i`: microstep `1/8`
- `o`: microstep `1/16`
- `p`: microstep `1/32`
- `q`: wyjście z programu

## Microstepping (DRV8825)

Microstepping można przełączać w trakcie pracy programu:

- `1/8` (`i`): większy moment, mniej płynny ruch
- `1/16` (`o`): kompromis między momentem i płynnością
- `1/32` (`p`): najbardziej płynny ruch, mniejszy moment

W praktyce do bardzo płynnej jazdy używaj `1/32`, a gdy robot potrzebuje więcej siły, przełącz na `1/16` lub `1/8`.
