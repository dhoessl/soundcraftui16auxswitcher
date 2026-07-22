from RPi import GPIO
from time import sleep
from socket import socket, AF_INET, SOCK_STREAM
from signal import signal, SIGINT, SIGTERM
from .mixer import Listener, Sender


class Led:
    def __init__(self, num: int) -> None:
        self.num = num
        GPIO.setup(num, GPIO.OUT, initial=GPIO.LOW)
        self.required_state = False

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
        self.mixer_mute = None

    @property
    def state(self) -> bool:
        return GPIO.input(self.num) == GPIO.HIGH

    def action_required(
        self,
        led_red: Led,
        led_green: Led
    ) -> tuple[bool | bool]:
        if self.mixer_mute is None:
            return (False, None)
        elif (
            self.state
            and not led_red.state
            and (
                not led_green.state
                or self.mixer_mute
            )
        ):
            # unmute action required
            led_red.on()
            return (True, False)
        elif (
            not self.state
            and not led_red.state
            and (
                led_green.state
                or not self.mixer_mute
            )
        ):
            # mute action required
            led_red.on()
            led_green.off()
            return (True, True)
        else:
            return (False, None)


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
        self.sender = Sender()
        self.listener = Listener()
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
        self.listener.start()
        self.sender.start()
        if self.listener.connected and self.sender.connected:
            return None
        while True:
            # indicate connection failed
            self.leds["blocker"].on()
            sleep(.2)
            self.leds["blocker"].off()
            sleep(.2)

    def clean(self) -> None:
        self.listener.stop()
        self.sender.stop()
        for led in self.leds:
            self.leds[led].off()
        GPIO.cleanup()

    def check_switches(self) -> None:
        if self.switches["blocker"].state:
            if self.leds["blocker"].state:
                # turn blocker led on if blocker switch is on
                self.leds["blocker"].on()
            # block any other action if blocker is on
            return None
        elif not self.switches["blocker"].state and self.leds["blocker"].state:
            # turn blocker led off if bocker switch is off
            self.leds["blocker"].off()
        for comp in ["delay", "siren"]:
            action_required, action = self.switches[f"{comp}"].action_required(
                self.leds[f"{comp}_red"], self.leds[f"{comp}_green"]
            )
            if not action_required:
                # Skip action if not action is required
                return None
            if comp == "delay":
                # delay mute (action == true) or unmute (action == False)
                self.sender.toggle_delay(action)
            else:
                # siren mute (action == true) or unmute (action == False)
                self.sender.toggle_siren(action)

    def check_queue(self) -> None:
        while self.listener.queue.qsize() > 0:
            msg = self.listener.queue.get()
            comp = msg["component"]
            if comp not in ["delay", "siren"]:
                continue
            if (
                msg["state"] == "0"
                and self.switches["blocker"].state
                and self.switches[f"{comp}"].mixer_mute
            ):
                self.leds[f"{comp}_red"].off()
                self.leds[f"{comp}_green"].off()
                self.switches[f"{comp}"].mixer_mute = False
                continue
            elif (
                msg["state"] == "1"
                and self.switches["blocker"].state
                and not self.switches[f"{comp}"].mixer_mute
            ):
                self.leds[f"{comp}_red"].off()
                self.leds[f"{comp}_green"].off()
                self.switches[f"{comp}"].mixer_mute = True
                continue
            if msg["state"] == "0":
                # show unmute of siren/delay to echo
                self.switches[f"{comp}"].mixer_mute = False
                self.leds[f"{comp}_green"].on()
                self.leds[f"{comp}_red"].off()
            elif msg["state"] == "1":
                # show mute of siren/delay to echo
                self.switches[f"{comp}"].mixer_mute = True
                self.leds[f"{comp}_red"].off()
                self.leds[f"{comp}_green"].off()

    def start(self) -> None:
        while True:
            self.check_switches()
            self.check_queue()
