import curses
import atexit
import signal
import sys
import time

try:
    import keyboard  # type: ignore[import-not-found]
except ModuleNotFoundError:
    keyboard = None

try:
    import pigpio  # type: ignore[import-not-found]
except ModuleNotFoundError:
    pigpio = None


ACTIVE_ROBOT_CONTROLLER = None


def _emergency_shutdown(reason="shutdown"):
    """Best-effort emergency stop used by signals/atexit/error paths."""
    global ACTIVE_ROBOT_CONTROLLER

    robot = ACTIVE_ROBOT_CONTROLLER
    if robot is None:
        return

    ACTIVE_ROBOT_CONTROLLER = None
    try:
        robot.close()
    except Exception:
        # Emergency path must never crash while stopping motors.
        pass


def _signal_handler(signum, _frame):
    _emergency_shutdown("signal:{0}".format(signum))
    raise SystemExit(128 + signum)


def _register_emergency_handlers():
    atexit.register(_emergency_shutdown)

    for sig_name in ("SIGINT", "SIGTERM", "SIGHUP"):
        sig = getattr(signal, sig_name, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, _signal_handler)
        except (ValueError, OSError, RuntimeError):
            # Some environments may not allow setting handlers.
            continue


class DRV8825:
    """Minimal DRV8825 driver using pigpio and hardware PWM on STEP pin."""

    def __init__(self, pi, dir_pin, step_pin, enable_pin, mode_pins):
        self.pi = pi
        self.dir_pin = dir_pin
        self.step_pin = step_pin
        self.enable_pin = enable_pin
        self.mode_pins = tuple(mode_pins)
        self._all_pins = (
            self.dir_pin,
            self.step_pin,
            self.enable_pin,
            *self.mode_pins,
        )

        for pin in self._all_pins:
            self.pi.set_mode(pin, pigpio.OUTPUT)
            self.pi.write(pin, 0)

        # Force full-step mode: M0=0, M1=0, M2=0.
        for pin in self.mode_pins:
            self.digital_write(pin, 0)

        # Keep the motor disabled until a movement command is received.
        self.stop()

    def digital_write(self, pin, value):
        """Write a logical value to a GPIO pin."""
        self.pi.write(pin, int(bool(value)))

    def set_direction(self, direction):
        if direction == "forward":
            self.digital_write(self.dir_pin, 0)
        elif direction == "backward":
            self.digital_write(self.dir_pin, 1)
        else:
            raise ValueError("Unknown direction: {0}".format(direction))

    def set_step_pwm(self, frequency_hz, duty_cycle=0.5):
        """Drive STEP using hardware PWM (duty range: 0..1_000_000)."""
        if frequency_hz <= 0:
            self.pi.hardware_PWM(self.step_pin, 0, 0)
            return

        duty = max(0.0, min(1.0, float(duty_cycle)))
        self.pi.hardware_PWM(self.step_pin, int(frequency_hz), int(duty * 1_000_000))

    def stop(self):
        """Disable output and stop step pulses."""
        self.set_step_pwm(0)
        self.digital_write(self.enable_pin, 0)

    def run(self, direction, frequency_hz):
        self.digital_write(self.enable_pin, 1)
        self.set_direction(direction)
        self.set_step_pwm(frequency_hz)


# Allow short input stalls (e.g. camera/RDP load) without dropping movement.
KEY_RELEASE_TIMEOUT = 0.25
MIN_STEP_FREQUENCY = 120
# Practical max chosen from observed stable behavior: old level 6.
MAX_STEP_FREQUENCY = 14243
RAMP_UP_SECONDS = 1.0
RAMP_STEPS = 10
RAMP_STEP_SECONDS = RAMP_UP_SECONDS / RAMP_STEPS

SERVO_GPIO = 23
SERVO_MIN_ANGLE = 95
SERVO_MAX_ANGLE = 120
SERVO_STEP_ANGLE = 5
SERVO_START_ANGLE = 100
SERVO_MIN_PULSE_US = 500
SERVO_MAX_PULSE_US = 2500


def clamp(value, min_value, max_value):
    return max(min_value, min(max_value, value))


def servo_pulse_for_angle(angle):
    """Convert angle in degrees to SG90 pulse width in microseconds."""
    bounded_angle = clamp(int(angle), SERVO_MIN_ANGLE, SERVO_MAX_ANGLE)
    span_angle = SERVO_MAX_ANGLE - SERVO_MIN_ANGLE
    span_pulse = SERVO_MAX_PULSE_US - SERVO_MIN_PULSE_US
    ratio = float(bounded_angle - SERVO_MIN_ANGLE) / float(span_angle)
    return int(SERVO_MIN_PULSE_US + ratio * span_pulse)


def step_frequency_for_level(level):
    """Map speed level 1..9 to step frequency where 9 is fastest."""
    level = max(1, min(9, level))

    if level == 1:
        return MIN_STEP_FREQUENCY
    if level == 9:
        return MAX_STEP_FREQUENCY

    # Log-like scaling gives more practical control at low levels
    # while still reaching the configured top speed at level 9.
    ratio = float(level - 1) / 8.0
    scale = (MAX_STEP_FREQUENCY / float(MIN_STEP_FREQUENCY)) ** ratio
    return int(MIN_STEP_FREQUENCY * scale)


class RobotController:
    def __init__(self):
        if pigpio is None:
            raise RuntimeError(
                "Brak modułu pigpio. Zainstaluj: sudo apt install python3-pigpio"
            )

        self.pi = pigpio.pi()
        if not self.pi.connected:
            raise RuntimeError(
                "Brak połączenia z pigpiod. Uruchom: sudo pigpiod"
            )

        self.right_motor = None
        self.left_motor = None
        self.servo_gpio = SERVO_GPIO
        self.servo_angle = SERVO_START_ANGLE

        try:
            # BCM pin mapping from the original script / Waveshare HAT.
            self.right_motor = DRV8825(
                pi=self.pi,
                dir_pin=13,
                step_pin=19,
                enable_pin=12,
                mode_pins=(16, 17, 20),
            )
            self.left_motor = DRV8825(
                pi=self.pi,
                dir_pin=24,
                step_pin=18,
                enable_pin=4,
                mode_pins=(21, 22, 27),
            )

            self.pi.set_mode(self.servo_gpio, pigpio.OUTPUT)
            self.set_servo_angle(self.servo_angle)
        except Exception:
            self.close()
            raise

    def drive(self, right_dir, left_dir, step_frequency_hz):
        self.right_motor.run(right_dir, step_frequency_hz)
        self.left_motor.run(left_dir, step_frequency_hz)

    def stop(self):
        if self.right_motor is not None:
            self.right_motor.stop()
        if self.left_motor is not None:
            self.left_motor.stop()
        self.set_servo_angle(self.servo_angle)

    def set_servo_angle(self, angle):
        if self.pi is None:
            return

        bounded_angle = clamp(int(angle), SERVO_MIN_ANGLE, SERVO_MAX_ANGLE)
        pulse = servo_pulse_for_angle(bounded_angle)
        self.pi.set_servo_pulsewidth(self.servo_gpio, pulse)
        self.servo_angle = bounded_angle

    def close(self):
        """Stop motors, release GPIO lines, and close gpiochip."""
        self.stop()

        if self.pi is not None:
            self.pi.set_servo_pulsewidth(self.servo_gpio, 0)

        self.right_motor = None
        self.left_motor = None

        if self.pi is not None:
            self.pi.stop()
            self.pi = None


def main(stdscr):
    global ACTIVE_ROBOT_CONTROLLER

    robot = RobotController()
    ACTIVE_ROBOT_CONTROLLER = robot

    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.keypad(True)

    stdscr.addstr(0, 0, "Robot control: arrow keys drive wheels, q = quit")
    stdscr.addstr(1, 0, "Up:    right->right, left->left")
    stdscr.addstr(2, 0, "Down:  right->left,  left->right")
    stdscr.addstr(3, 0, "Left:  both wheels left")
    stdscr.addstr(4, 0, "Right: both wheels right")
    stdscr.addstr(5, 0, "Speed: press 1..9 (9 = maximum)")
    stdscr.addstr(6, 0, "Full-step mode enabled (microstepping disabled)")
    stdscr.addstr(7, 0, "STEP driven by pigpio hardware_PWM on GPIO18/19")
    stdscr.addstr(10, 0, "Servo SG90: w/s = krok {0} st, zakres {1}-{2} st".format(
        SERVO_STEP_ANGLE,
        SERVO_MIN_ANGLE,
        SERVO_MAX_ANGLE,
    ))

    speed_level = 5
    step_frequency = step_frequency_for_level(speed_level)
    active_motion = None
    applied_state = None
    motion_started_at = None
    last_motion_key_at = 0.0
    servo_angle = SERVO_START_ANGLE
    robot.set_servo_angle(servo_angle)
    w_was_pressed = False
    s_was_pressed = False

    keyboard_hold_mode = False
    if keyboard is not None:
        try:
            # Check permissions/backend once. On Linux this may need root.
            keyboard.is_pressed("up")
            keyboard_hold_mode = True
        except Exception:
            keyboard_hold_mode = False

    stdscr.addstr(8, 0, "Waiting for key... Speed level: 5")
    stdscr.addstr(
        9,
        0,
        "Hold mode: {0}".format("keyboard module" if keyboard_hold_mode else "curses fallback"),
    )
    stdscr.refresh()

    try:
        while True:
            key = stdscr.getch()
            requested_motion = None

            if keyboard_hold_mode:
                try:
                    if keyboard.is_pressed("up"):
                        requested_motion = ("forward", "backward", "FORWARD")
                    elif keyboard.is_pressed("down"):
                        requested_motion = ("backward", "forward", "BACKWARD")
                    elif keyboard.is_pressed("left"):
                        requested_motion = ("backward", "backward", "LEFT")
                    elif keyboard.is_pressed("right"):
                        requested_motion = ("forward", "forward", "RIGHT")

                    w_pressed = keyboard.is_pressed("w")
                    s_pressed = keyboard.is_pressed("s")

                    if w_pressed and not w_was_pressed:
                        servo_angle = clamp(
                            servo_angle + SERVO_STEP_ANGLE,
                            SERVO_MIN_ANGLE,
                            SERVO_MAX_ANGLE,
                        )
                    if s_pressed and not s_was_pressed:
                        servo_angle = clamp(
                            servo_angle - SERVO_STEP_ANGLE,
                            SERVO_MIN_ANGLE,
                            SERVO_MAX_ANGLE,
                        )

                    w_was_pressed = w_pressed
                    s_was_pressed = s_pressed
                except Exception:
                    keyboard_hold_mode = False
                    stdscr.addstr(9, 0, "Hold mode: curses fallback                           ")

            if key == ord("q"):
                break
            elif ord("1") <= key <= ord("9"):
                speed_level = key - ord("0")
                step_frequency = step_frequency_for_level(speed_level)
                stdscr.addstr(
                    8,
                    0,
                    "Speed set to: {0} ({1} Hz)                      ".format(
                        speed_level, step_frequency
                    ),
                )
            if not keyboard_hold_mode:
                if key == curses.KEY_UP:
                    requested_motion = ("forward", "backward", "FORWARD")
                elif key == curses.KEY_DOWN:
                    requested_motion = ("backward", "forward", "BACKWARD")
                elif key == curses.KEY_LEFT:
                    requested_motion = ("backward", "backward", "LEFT")
                elif key == curses.KEY_RIGHT:
                    requested_motion = ("forward", "forward", "RIGHT")
                elif key in (ord("w"), ord("W")):
                    servo_angle = clamp(
                        servo_angle + SERVO_STEP_ANGLE,
                        SERVO_MIN_ANGLE,
                        SERVO_MAX_ANGLE,
                    )
                elif key in (ord("s"), ord("S")):
                    servo_angle = clamp(
                        servo_angle - SERVO_STEP_ANGLE,
                        SERVO_MIN_ANGLE,
                        SERVO_MAX_ANGLE,
                    )
                elif key == -1:
                    if (
                        active_motion is not None
                        and (time.monotonic() - last_motion_key_at)
                        > KEY_RELEASE_TIMEOUT
                    ):
                        active_motion = None
                        motion_started_at = None

                if requested_motion is not None:
                    if requested_motion != active_motion:
                        active_motion = requested_motion
                        motion_started_at = time.monotonic()
                    last_motion_key_at = time.monotonic()
            else:
                if requested_motion is not None:
                    if requested_motion != active_motion:
                        active_motion = requested_motion
                        motion_started_at = time.monotonic()
                    last_motion_key_at = time.monotonic()
                elif (
                    active_motion is not None
                    and (time.monotonic() - last_motion_key_at)
                    > KEY_RELEASE_TIMEOUT
                ):
                    active_motion = None
                    motion_started_at = None

            if active_motion is None:
                ramped_frequency = 0
            else:
                elapsed = time.monotonic() - motion_started_at
                ramp_stage = min(RAMP_STEPS, int(elapsed / RAMP_STEP_SECONDS) + 1)
                ramped_frequency = max(1, int(step_frequency * ramp_stage / RAMP_STEPS))

            target_state = (
                None
                if active_motion is None
                else (active_motion[0], active_motion[1], ramped_frequency)
            )

            if target_state != applied_state:
                if target_state is None:
                    robot.stop()
                else:
                    robot.drive(
                        right_dir=target_state[0],
                        left_dir=target_state[1],
                        step_frequency_hz=target_state[2],
                    )
                applied_state = target_state

            if servo_angle != robot.servo_angle:
                robot.set_servo_angle(servo_angle)

            if active_motion is not None:
                _, _, label = active_motion
                stdscr.addstr(
                    8,
                    0,
                    "Move: {0} | speed: {1} ({2}/{3} Hz)             ".format(
                        label, speed_level, ramped_frequency, step_frequency
                    ),
                )
            else:
                stdscr.addstr(
                    8,
                    0,
                    "Stop / waiting for arrow key... speed: {0} ({1} Hz) ".format(
                        speed_level, step_frequency
                    ),
                )

            stdscr.addstr(
                11,
                0,
                "Servo: {0} st (krok {1}, min/max {2}/{3})                ".format(
                    robot.servo_angle,
                    SERVO_STEP_ANGLE,
                    SERVO_MIN_ANGLE,
                    SERVO_MAX_ANGLE,
                ),
            )

            stdscr.refresh()
            time.sleep(0.01)
    finally:
        robot.close()
        ACTIVE_ROBOT_CONTROLLER = None


if __name__ == "__main__":
    _register_emergency_handlers()

    try:
        curses.wrapper(main)
    except BaseException:
        _emergency_shutdown("fatal-error")
        raise
