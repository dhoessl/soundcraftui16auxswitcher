from soundcraftui16mqtt_mixer import MixerBase
from threading import Thread
from queue import Queue


class Mixer(MixerBase):
    def __init__(self) -> None:
        super().__init__("10.10.1.1", "80")
        self.queue = Queue()
        self.recv_thread = Thread(
            target=self._receiving,
            args=()
        )

    def _read_messag(self, message: str) -> None:
        msg_type, body, value = message.split('^')
        parts = body.split('.')
        if (
            parts[0] != "i"
            or parts[1] not in ["4", "6"]
            or parts[2] != "a"
            or parts[3] != "0"
            or parts[4] != "mute"
        ):
            return None
        # self.queue.put({"component": "delay", "state": value})
        # self.queue.put({"component": "siren", "state": value})
        print(f"{msg_type} -> {parts} -> {value}")

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
                # If no message delimiter is found wait for new messages
                continue
            # split buffer on delimiter into parts
            parts = buffer.split("\n")
            # Save everything except last unfinished element
            data = parts[0:len(parts)-1]
            # set unfinished back in buffer
            buffer = parts[len(parts)-1]
            for message in data:
                if "SETD" in message:
                    # Send message using mqtt
                    self._read_message(message)

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
        self._send_setd("i.4.a.0.mute", int(state))

    def toggle_siren(self, state: bool) -> None:
        self._send_setd("i.6.a.0.mute", int(state))
