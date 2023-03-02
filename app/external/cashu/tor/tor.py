import os
import pathlib
import platform
import socket

from loguru import logger


class TorProxy:
    def __init__(self, timeout=False):
        self.base_path = pathlib.Path(__file__).parent.resolve()
        self.platform = platform.system()
        self.timeout = 60 * 60 if timeout else 0  # seconds
        self.tor_proc = None
        self.pid_file = os.path.join(self.base_path, "tor.pid")
        self.tor_pid = None
        self.startup_finished = True
        self.tor_running = self.is_running()

    def log_status(self):
        logger.debug(f"Tor binary path: {self.tor_path()}")
        logger.debug(f"Tor config path: {self.tor_config_path()}")
        logger.debug(f"Tor running: {self.tor_running}")
        logger.debug(
            f"Tor port open: {self.is_port_open()}",
        )
        logger.debug(f"Tor PID in tor.pid: {self.read_pid()}")
        logger.debug(f"Tor PID running: {self.signal_pid(self.read_pid())}")

    def tor_path(self):
        PATHS = {
            "Windows": os.path.join(self.base_path, "bundle", "win", "Tor", "tor.exe"),
            "Linux": os.path.join(self.base_path, "bundle", "linux", "tor"),
            "Darwin": os.path.join(self.base_path, "bundle", "mac", "tor"),
        }
        # make sure that file has correct permissions
        try:
            logger.debug(f"Setting permissions of {PATHS[platform.system()]} to 755")
            os.chmod(PATHS[platform.system()], 0o755)
        except:
            logger.debug("Exception: could not set permissions of Tor binary")
        return PATHS[platform.system()]

    def tor_config_path(self):
        return os.path.join(self.base_path, "torrc")

    def is_running(self):
        # another tor proxy is running
        if not self.is_port_open():
            return False
        # our tor proxy running from a previous session
        if self.signal_pid(self.read_pid()):
            return True
        # current attached process running
        return self.tor_proc and self.tor_proc.poll() is None

    def is_port_open(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        location = ("127.0.0.1", 9050)
        try:
            s.connect(location)
            s.close()
            return True
        except Exception as e:
            return False

    def read_pid(self):
        if not os.path.isfile(self.pid_file):
            return None
        with open(self.pid_file, "r") as f:
            pid = f.readlines()
        # check if pid is valid
        if len(pid) == 0 or not int(pid[0]) > 0:
            return None
        return pid[0]

    def signal_pid(self, pid, signal=0):
        """
        Checks whether a process with pid is running (signal 0 is not a kill signal!)
        or stops (signal 15) or kills it (signal 9).
        """
        if not pid:
            return False
        if not int(pid) > 0:
            return False
        pid = int(pid)
        try:
            os.kill(pid, signal)
        except:
            return False
        else:
            return True
