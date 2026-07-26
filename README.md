# Popcornition App

Prosta aplikacja terminalowa do sterowania robotem (silniki DRV8825) na Raspberry Pi.

## Sterowanie

- Strzałki: ruch robota
- `1`-`9`: zmiana prędkości (`9` = najszybciej)
- `t`: microstep `full`
- `y`: microstep `half`
- `u`: microstep `1/4`
- `i`: microstep `1/8`
- `o`: microstep `1/16`
- `p`: microstep `1/32`
- `q`: wyjście z programu

## Microstepping (DRV8825)

Microstepping można przełączać w trakcie pracy programu:

- `full` (`t`): najwyższy moment, największe przeskoki
- `half` (`y`): duży moment, mniejsze przeskoki niż `full`
- `1/4` (`u`): dobry kompromis między momentem i płynnością
- `1/8` (`i`): większy moment, mniej płynny ruch
- `1/16` (`o`): kompromis między momentem i płynnością
- `1/32` (`p`): najbardziej płynny ruch, mniejszy moment

W praktyce do bardzo płynnej jazdy używaj `1/32`, a gdy robot potrzebuje więcej siły, przełącz stopniowo na `1/16`, `1/8`, `1/4`, `half` lub `full`.
