import serial
import time
import threading

# Serial configuration
PORT = "/dev/ttyUSB0"
BAUD_RATE = 9600

# Command labels
LABEL_ROBOT_PING             = 'p'
LABEL_ROBOT_RESET            = 'r'
LABEL_ROBOT_START_WITH_WD    = 'W'
LABEL_ROBOT_START_WITHOUT_WD = 'u'
LABEL_ROBOT_RELOAD_WD        = 'w'
LABEL_ROBOT_MOVE             = 'M'
LABEL_ROBOT_TURN             = 'T'
LABEL_ROBOT_GET_BATTERY      = 'v'
LABEL_ROBOT_GET_STATE        = 'b'
LABEL_ROBOT_POWEROFF         = 'z'

LABEL_ROBOT_OK               = 'O'
LABEL_ROBOT_ERROR            = 'E'
LABEL_ROBOT_UNKNOWN_COMMAND  = 'C'

LABEL_ROBOT_SEPARATOR_CHAR   = '='
LABEL_ROBOT_ENDING_CHAR      = 0x0D  # carriage return (\r)


class Robot:
    """
    Handles serial communication with the robot.

    Usage:
        robot = Network()
        if robot.open():
            robot.init()
            robot.move(100)
            robot.close()
    """

    def __init__(self, port=PORT, baud_rate=BAUD_RATE):
        self.port = port
        self.baud_rate = baud_rate
        self._ser = None
        self._lock = threading.Lock()
        self.open()

    # ------------------------------------------------------------------ #
    #  Connection                                                          #
    # ------------------------------------------------------------------ #

    def open(self) -> bool:
        """Open the serial port. Returns True on success, False on failure."""
        try:
            self._ser = serial.Serial(self.port, self.baud_rate, timeout=1)
            print(f"[SERIAL] Opened {self.port} at {self.baud_rate} baud")
            return True
        except serial.SerialException as e:
            print(f"[SERIAL] Cannot open {self.port}: {e}")
            self._ser = None
            return False

    def close(self):
        """Close the serial port if open."""
        if self._ser and self._ser.is_open:
            self._ser.close()
            print("[SERIAL] Port closed")
        self._ser = None

    def is_open(self) -> bool:
        return self._ser is not None and self._ser.is_open

    # ------------------------------------------------------------------ #
    #  Low-level serial helpers                                            #
    # ------------------------------------------------------------------ #

    def _add_checksum(self, s: str) -> str:
        checksum = 0
        for c in s:
            checksum ^= ord(c)
        return s + chr(checksum) + chr(LABEL_ROBOT_ENDING_CHAR)

    def _build_message(self, label: str, param=None) -> str | None:
        if label in (LABEL_ROBOT_MOVE, LABEL_ROBOT_TURN):
            if param is None:
                print(f"[WARN] Label '{label}' requires a param")
                return None
            raw = f'{label}{LABEL_ROBOT_SEPARATOR_CHAR}{param}'
        elif label in (
            LABEL_ROBOT_PING, LABEL_ROBOT_RESET,
            LABEL_ROBOT_START_WITH_WD, LABEL_ROBOT_START_WITHOUT_WD,
            LABEL_ROBOT_RELOAD_WD, LABEL_ROBOT_GET_BATTERY,
            LABEL_ROBOT_GET_STATE, LABEL_ROBOT_POWEROFF
        ):
            raw = label
        else:
            print(f"[WARN] Unknown label: '{label}'")
            return None
        return self._add_checksum(raw)

    def _send_and_read(self, label: str, param=None) -> str:
        """Send a command and return the response content (checksum byte stripped)."""
        if not self.is_open():
            print("[ERROR] Serial port not open")
            return ""
        msg = self._build_message(label, param)
        if msg is None:
            return ""
        with self._lock:
            self._ser.write(msg.encode())
            print(f"[TX] {msg.strip()}")
            time.sleep(0.2)
            response = self._ser.readline().decode(errors='ignore').strip()
            print(f"[RX] {response}")
        return response[:-1] if len(response) >= 2 else ""

    def _flush_read(self):
        """Discard all pending bytes in the receive buffer."""
        time.sleep(0.2)
        while self._ser and self._ser.in_waiting:
            data = self._ser.readline().decode(errors='ignore').strip()
            print(f"[FLUSH] {data}")
            time.sleep(0.05)

    # ------------------------------------------------------------------ #
    #  High-level robot commands                                           #
    # ------------------------------------------------------------------ #

    def init(self) -> bool:
        """
        Boot sequence: flush, start without watchdog, wait, then ping.
        Returns True if robot is ready, False otherwise.
        """
        print("=== INIT ROBOT ===")
        self._flush_read()

        rep = self._send_and_read(LABEL_ROBOT_START_WITHOUT_WD)
        print(f"[START] response = '{rep}'")
        time.sleep(3)
        self._flush_read()

        rep = self._send_and_read(LABEL_ROBOT_PING)
        print(f"[PING] response = '{rep}'")

        if rep != LABEL_ROBOT_OK:
            print("[ERROR] Network not ready after init")
            return False

        print("[OK] Network ready!")
        return True

    def ping(self) -> bool:
        return self._send_and_read(LABEL_ROBOT_PING) == LABEL_ROBOT_OK

    def reset(self):
        self._send_and_read(LABEL_ROBOT_RESET)

    def start_without_watchdog(self) -> bool:
        return self._send_and_read(LABEL_ROBOT_START_WITHOUT_WD) == LABEL_ROBOT_OK

    def start_with_watchdog(self) -> bool:
        return self._send_and_read(LABEL_ROBOT_START_WITH_WD) == LABEL_ROBOT_OK

    def reload_watchdog(self) -> bool:
        return self._send_and_read(LABEL_ROBOT_RELOAD_WD) == LABEL_ROBOT_OK

    def move(self, speed: int) -> bool:
        return self._send_and_read(LABEL_ROBOT_MOVE, param=speed) == LABEL_ROBOT_OK

    def turn(self, angle: int) -> bool:
        return self._send_and_read(LABEL_ROBOT_TURN, param=angle) == LABEL_ROBOT_OK

    def poweroff(self):
        self._send_and_read(LABEL_ROBOT_POWEROFF)

    def get_battery(self) -> tuple[str | None, str | None]:
        """
        Returns (raw_value, human_label) e.g. ('2', 'HAUTE / EN CHARGE COMPLÈTE').
        Returns (None, None) on failure.
        """
        content = self._send_and_read(LABEL_ROBOT_GET_BATTERY)
        match content:
            case '2':
                level = "HAUTE / EN CHARGE COMPLÈTE"
            case '1':
                level = "MOYENNE / EN CHARGE"
            case '0':
                level = "FAIBLE / CRITIQUE"
            case _:
                print(f"[BATTERY] Unknown value: '{content}'")
                return None, None
        print(f"[BATTERY] {content} → {level}")
        return content, level

    def get_state(self) -> tuple[str | None, str | None]:
        """
        Returns (raw_value, human_label) e.g. ('1', 'BUSY').
        Returns (None, None) on failure.
        """
        content = self._send_and_read(LABEL_ROBOT_GET_STATE)
        match content:
            case '1':
                state = "BUSY"
            case '0':
                state = "FREE"
            case _:
                print(f"[STATE] Unknown value: '{content}'")
                return None, None
        print(f"[STATE] {content} → {state}")
        return content, state