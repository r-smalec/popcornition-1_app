#!/usr/bin/env bash
set -euo pipefail

CAMERA_CMD='libcamera-hello --timeout 0'

launch_camera_in_second_terminal() {
	# Try common terminal emulators used on Raspberry Pi / Linux desktops.
	if command -v x-terminal-emulator >/dev/null 2>&1; then
		x-terminal-emulator -e bash -lc "$CAMERA_CMD" &
		return 0
	fi

	if command -v lxterminal >/dev/null 2>&1; then
		lxterminal -e "bash -lc '$CAMERA_CMD'" &
		return 0
	fi

	if command -v gnome-terminal >/dev/null 2>&1; then
		gnome-terminal -- bash -lc "$CAMERA_CMD" &
		return 0
	fi

	if command -v xfce4-terminal >/dev/null 2>&1; then
		xfce4-terminal --command="bash -lc '$CAMERA_CMD'" &
		return 0
	fi

	if command -v konsole >/dev/null 2>&1; then
		konsole -e bash -lc "$CAMERA_CMD" &
		return 0
	fi

	if command -v xterm >/dev/null 2>&1; then
		xterm -e bash -lc "$CAMERA_CMD" &
		return 0
	fi

	return 1
}

if ! launch_camera_in_second_terminal; then
	echo "Nie znaleziono emulatora terminala do uruchomienia kamery w drugim oknie." >&2
fi

sudo pigpiod
python3 popcornition_app.py
