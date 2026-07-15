from RPi import GPIO
from time import sleep
from socket import socket, AF_INET, SOCK_STREAM
from signal import signal, SIGINT, SIGTERM
from .mixer import Mixer


class Led:
    def __init__(self, num: int) -> None:
        self.num = num
        GPIO.setup(num, GPIO.OUT, initial=GPIO.LOW)
        self.required_state = GPIO.LOW
        self.locked = False

    @property
    def state(self) -> bool:
        return GPIO.input(self.num) == GPIO.HIGH

    def on(self) -> None:
        GPIO.output(self.num, GPIO.HIGH)

    def off(self) -> None:
        GPIO.output(self.num, GPIO.LOW)


class Switch:
    def __init__(self, num: int) -> None:
        self.num = num
        GPIO.setup(num, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    @property
    def state(self) -> bool:
        return GPIO.input(self.num) == GPIO.HIGH


class Board:
    def __init__(self) -> None:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        self.leds = {
            "delay_red": Led(27),
            "delay_green": Led(22),
            "siren_red": Led(23),
            "siren_green": Led(24),
            "blocker": Led(25)
        }
        self.switches = {
            "delay": Switch(2),
            "siren": Switch(3),
            "blocker": Switch(4)
        }
        self.mixer = Mixer()
        signal(SIGTERM, self._clean)
        signal(SIGINT, self._clean)
        self._selftest()
        self._start_mixer()

    def _clean(self, sig, *args) -> None:
        self.clean()

    def _selftest(self) -> None:
        for led in self.leds:
            self.leds[led].on()
            sleep(.2)
        for led in self.leds:
            self.leds[led].off()
            sleep(.2)

    def _network_connected(self) -> bool:
        try:
            sock = socket(AF_INET, SOCK_STREAM)
            sock.settimeout(3)
            sock.connect(("10.10.1.1", 80))
            return True
        except TimeoutError:
            return False
        except OSError:
            return False

    def _wait_for_network(self) -> None:
        while not self._network_connected():
            self._selftest()

    def _start_mixer(self) -> None:
        self._wait_for_network()
        self.mixer.start()
        if self.mixer.connected:
            return None
        while True:
            # indicate connection failed
            self.leds["blocker"].on()
            sleep(.5)
            self.leds["blocker"].off()
            sleep(.5)

    def clean(self) -> None:
        self.mixer.stop()
        for led in self.leds:
            self.leds[led].off()
        GPIO.cleanup()

    def check_switches(self) -> None:
        if self.switches["blocker"].state:
            if not self.leds["blocker"].state:
                self.leds["blocker"].on()
            return None
        elif not self.switches["blocker"].state and self.leds["blocker"].state:
            self.leds["blocker"].off()
        if (
            self.switches["delay"].state
            and not self.leds["delay_red"].state
            and not self.leds["delay_green"].state
        ):
            self.leds["delay_red"].on()
            self.leds["delay_green"].required_state = True
            self.mixer.toggle_delay(False)
        elif (
            not self.switches["delay"].state
            and not self.leds["delay_red"].state
            and self.leds["delay_green"].state
        ):
            self.leds["delay_red"].on()
            self.leds["delay_green"].off()
            self.leds["delay_green"].required_state = False
            self.mixer.toggle_delay(True)
        if (
            self.switches["siren"].state
            and not self.leds["siren_red"].state
            and not self.leds["siren_green"].state
        ):
            self.leds["siren_red"].on()
            self.leds["siren_green"].required_state = True
            self.mixer.toggle_siren(False)
        elif (
            not self.switches["siren"].state
            and not self.leds["siren_red"].state
            and self.leds["siren_green"].state
        ):
            self.leds["siren_red"].on()
            self.leds["siren_green"].off()
            self.leds["siren_green"].required_state = False
            self.mixer.toggle_siren(True)

    def check_queue(self) -> None:
        while self.mixer.queue.qsize() > 0:
            msg = self.mixer.queue.get()
            if msg["component"] in ["delay", "siren"]:
                comp = msg["component"]
                if (
                    bool(msg["state"])
                    and self.leds[f"{comp}_red"].state
                    and self.leds[f"{comp}_green"].required_state
                ):
                    self.leds[f"{comp}_green"].on()
                    self.leds[f"{comp}_red"].off()
                elif (
                    not bool(msg["state"])
                    and self.leds[f"{comp}_red"].state
                    and not self.leds[f"{comp}_green"].required_state
                ):
                    self.leds[f"{comp}_red"].off()

    def start(self) -> None:
        while True:
            self.check_switches()
            self.check_queue()
