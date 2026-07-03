import socket
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.brain import replay_client


class ReplayClientTests(unittest.TestCase):
    def test_replay_file_sends_each_line_with_newline_to_tcp_server(self):
        received = []
        ready = threading.Event()

        def server():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("127.0.0.1", 0))
                port_holder.append(sock.getsockname()[1])
                sock.listen(1)
                ready.set()
                conn, _ = sock.accept()
                with conn:
                    buffer = b""
                    while True:
                        chunk = conn.recv(4096)
                        if not chunk:
                            break
                        buffer += chunk
                received.extend(buffer.decode("utf-8").splitlines())

        port_holder = []
        thread = threading.Thread(target=server, daemon=True)
        thread.start()
        self.assertTrue(ready.wait(2), "test TCP server did not start")

        with TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "fixture.jsonl"
            fixture.write_text('{"wanted":0}\n{"wanted":1}\n', encoding="utf-8")

            count = replay_client.replay_file(
                fixture,
                host="127.0.0.1",
                port=port_holder[0],
                delay_s=0,
            )

        thread.join(2)
        self.assertEqual(count, 2)
        self.assertEqual(received, ['{"wanted":0}', '{"wanted":1}'])


if __name__ == "__main__":
    unittest.main()
