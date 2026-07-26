import curses
import time
import RPi.GPIO as GPIO


class DRV8825(object):
	"""Minimal DRV8825 driver used by this app (no debug prints)."""

	def __init__(self, dir_pin, step_pin, enable_pin, mode_pins):
		self.dir_pin = dir_pin
		self.step_pin = step_pin
		self.enable_pin = enable_pin
		self.mode_pins = mode_pins

		GPIO.setmode(GPIO.BCM)
		GPIO.setwarnings(False)
		GPIO.setup(self.dir_pin, GPIO.OUT)
		GPIO.setup(self.step_pin, GPIO.OUT)
		GPIO.setup(self.enable_pin, GPIO.OUT)

		for pin in self.mode_pins:
			GPIO.setup(pin, GPIO.OUT)

		# Force full-step mode (M0=0, M1=0, M2=0).
		for pin in self.mode_pins:
			self.digital_write(pin, 0)

	def digital_write(self, pin, value):
		GPIO.output(pin, value)

	def Stop(self):
		# Disable motor outputs.
		self.digital_write(self.enable_pin, 0)


STEP_BATCH = 60
KEY_RELEASE_TIMEOUT = 0.08
MIN_STEP_DELAY = 0.0
MAX_STEP_DELAY = 0.0035


def step_delay_for_level(level):
	"""Map speed level 1..9 to step delay where 9 is fastest."""
	if level < 1:
		level = 1
	elif level > 9:
		level = 9

	if level == 9:
		return MIN_STEP_DELAY

	# Linear map: 1 -> MAX_STEP_DELAY, 9 -> MIN_STEP_DELAY.
	ratio = float(level - 1) / 8.0
	return MAX_STEP_DELAY - ratio * (MAX_STEP_DELAY - MIN_STEP_DELAY)


class RobotController(object):
	def __init__(self):
		# Pin mapping based on test.py
		self.right_motor = DRV8825(
			dir_pin=13,
			step_pin=19,
			enable_pin=12,
			mode_pins=(16, 17, 20),
		)
		self.left_motor = DRV8825(
			dir_pin=24,
			step_pin=18,
			enable_pin=4,
			mode_pins=(21, 22, 27),
		)

	def _set_direction(self, motor, direction):
		if direction == 'forward':
			motor.digital_write(motor.enable_pin, 1)
			motor.digital_write(motor.dir_pin, 0)
		elif direction == 'backward':
			motor.digital_write(motor.enable_pin, 1)
			motor.digital_write(motor.dir_pin, 1)

	def drive(self, right_dir, left_dir, steps=STEP_BATCH, step_delay=0.003):
		self._set_direction(self.right_motor, right_dir)
		self._set_direction(self.left_motor, left_dir)

		for _ in range(steps):
			self.right_motor.digital_write(self.right_motor.step_pin, True)
			self.left_motor.digital_write(self.left_motor.step_pin, True)
			if step_delay > 0.0:
				time.sleep(step_delay)
			self.right_motor.digital_write(self.right_motor.step_pin, False)
			self.left_motor.digital_write(self.left_motor.step_pin, False)
			if step_delay > 0.0:
				time.sleep(step_delay)

	def stop(self):
		self.right_motor.Stop()
		self.left_motor.Stop()


def main(stdscr):
	robot = RobotController()

	curses.curs_set(0)
	stdscr.nodelay(True)
	stdscr.keypad(True)

	stdscr.addstr(0, 0, 'Robot control: arrow keys drive wheels, q = quit')
	stdscr.addstr(1, 0, 'Up:    right->right, left->left')
	stdscr.addstr(2, 0, 'Down:  right->left,  left->right')
	stdscr.addstr(3, 0, 'Left:  both wheels left')
	stdscr.addstr(4, 0, 'Right: both wheels right')
	stdscr.addstr(5, 0, 'Speed: press 1..9 (9 = maximum)')
	stdscr.addstr(6, 0, 'Full-step mode enabled (microstepping disabled)')

	speed_level = 5
	step_delay = step_delay_for_level(speed_level)
	active_motion = None
	last_motion_key_at = 0.0
	stdscr.addstr(7, 0, 'Waiting for key... Speed level: 5')
	stdscr.refresh()

	try:
		while True:
			key = stdscr.getch()

			if key == ord('q'):
				break
			elif key >= ord('1') and key <= ord('9'):
				speed_level = key - ord('0')
				step_delay = step_delay_for_level(speed_level)
				stdscr.addstr(7, 0, 'Speed set to: {0}                               '.format(speed_level))
				active_motion = None
			elif key == curses.KEY_UP:
				active_motion = ('forward', 'backward', 'FORWARD')
				last_motion_key_at = time.monotonic()
			elif key == curses.KEY_DOWN:
				active_motion = ('backward', 'forward', 'BACKWARD')
				last_motion_key_at = time.monotonic()
			elif key == curses.KEY_LEFT:
				active_motion = ('backward', 'backward', 'LEFT')
				last_motion_key_at = time.monotonic()
			elif key == curses.KEY_RIGHT:
				active_motion = ('forward', 'forward', 'RIGHT')
				last_motion_key_at = time.monotonic()
			elif key == -1:
				if active_motion is not None and (time.monotonic() - last_motion_key_at) > KEY_RELEASE_TIMEOUT:
					active_motion = None

			if active_motion is not None:
				right_dir, left_dir, label = active_motion
				# Drive only one step batch and poll keyboard again to react quickly to key release.
				robot.drive(right_dir=right_dir, left_dir=left_dir, steps=1, step_delay=step_delay)
				stdscr.addstr(7, 0, 'Move: {0} | speed: {1}                          '.format(label, speed_level))
			else:
				robot.stop()
				stdscr.addstr(7, 0, 'Stop / waiting for arrow key... speed: {0}       '.format(speed_level))

			stdscr.refresh()
			time.sleep(0.001)
	finally:
		robot.stop()
		GPIO.cleanup()


if __name__ == '__main__':
	curses.wrapper(main)
