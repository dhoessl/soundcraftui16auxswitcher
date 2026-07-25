from soundcraftui16mqtt_mixer.main import MixerBase
from threading import Thread
from queue import Queue


class Listener(MixerBase):
    def __init__(self) -> None:
        super().__init__("10.10.1.1", 80)
        self.queue = Queue()
        self.recv_thread = Thread(
            target=self._receiving,
            args=()
        )

    def _receiving(self) -> None:
        buffer = ""
        while not self.exit.is_set():
            # save new data to buffer
            try:
                buffer += self.client.recv(2048).decode()
            except TimeoutError:
                if self.exit.is_set():
                    continue
                self.exit.set()
                continue
            if "\n" not in buffer:
                continue
            # split buffer on delimiter into parts
            parts = buffer.split("\n")
            # Save everything except last unfinished element
            data = parts[0:len(parts)-1]
            # set unfinished back in buffer
            buffer = parts[len(parts)-1]
            for message in data:
                if "SETD" in message:
                    _, body, value = message.split('^')
                    msg_parts = body.split('.')
                    if (
                        msg_parts[0] != "i"
                        or msg_parts[1] not in ["4", "6"]
                        or msg_parts[2] != "aux"
                        or msg_parts[3] != "0"
                        or msg_parts[4] != "mute"
                    ):
                        continue
                    self.queue.put({
                        "component": "delay" if msg_parts["4"] else "siren",
                        "state": value
                    })

    def start(self) -> None:
        self.connect()

    def stop(self) -> None:
        self.terminate()


class Sender(MixerBase):
    def __init__(self, action: str, state: bool) -> None:
        super().__init__("10.10.1.1", 80)
        self.start()
        if action == "delay":
            self.toggle_delay(state)
        else:
            self.toggle_siren(state)
        self.stop()

    def _send_setd(self, body: str, value: str | float) -> bool:
        if not self.connected:
            return False
        self.client.send(
            f"SETD^{body}^{value}\n".encode("UTF-8")
        )
        return True

    def start(self) -> None:
        self.connect()

    def stop(self) -> None:
        self.terminate()

    def toggle_delay(self, state: bool) -> None:
        self._send_setd("i.4.aux.0.mute", int(state))

    def toggle_siren(self, state: bool) -> None:
        self._send_setd("i.6.aux.0.mute", int(state))
