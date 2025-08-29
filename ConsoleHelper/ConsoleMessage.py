# -----------------------------------------------------------------------------
# File Name   : ConsoleHelper/ConsoleMessage.py
# Description : Defines the ConsoleMessage class for logging messages to both
#               the console (with colored output) and a log file. Useful for
#               debugging and structured logging in CLI-based Python tools.
#
# Author      : X
# Created On  : 05/08/2025
# Last Updated: 17/08/2025
# Import Style: from ConsoleHelper.ConsoleMessage import ConsoleMessage
# -----------------------------------------------------------------------------

import logging
from datetime import datetime
from colorama import init, Fore, Style

init(autoreset=True)

# Register custom log level "LOG"
LOG_LEVEL = 25
logging.addLevelName(LOG_LEVEL, "LOG")

class ConsoleMessage:
    _instance = None  # Singleton to prevent duplicate handlers

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ConsoleMessage, cls).__new__(cls)
        return cls._instance

    def __init__(self, log_file: str = "ConsoleMessage.log", app_name: str = "Garuda Cloud Monitor", file_logging: bool = True):
        if hasattr(self, "logger"):
            return  # Prevent reinitialization

        self.app_name = app_name
        self.logger = logging.getLogger(app_name)
        self.logger.setLevel(logging.DEBUG)

        if not self.logger.handlers:
            # File Handler
            if file_logging:
                file_formatter = logging.Formatter(
                    '%(asctime)s %(levelname)-8s %(name)s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                file_handler = logging.FileHandler(log_file)
                file_handler.setLevel(logging.DEBUG)
                file_handler.setFormatter(file_formatter)
                self.logger.addHandler(file_handler)

            # Console Handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)
            console_handler.setFormatter(self.ColorFormatter(app_name))
            self.logger.addHandler(console_handler)

    class ColorFormatter(logging.Formatter):
        def __init__(self, app_name: str):
            super().__init__()
            self.app_name = app_name

        def format(self, record):
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            message = record.getMessage()

            color_map = {
                "INFO": Fore.BLUE,
                "DEBUG": Fore.CYAN,
                "WARNING": Fore.YELLOW,
                "ERROR": Fore.RED,
                "CRITICAL": Fore.MAGENTA + Style.BRIGHT,
                "LOG": Fore.WHITE,   # White for plain logs
            }

            if record.levelname == "LOG":
                # Replace "LOG" with "Appname" in console
                level_text = self.app_name
                color = Fore.WHITE
            else:
                level_text = record.levelname
                color = color_map.get(record.levelname, "")

            level_colored = f"{color}{level_text:<8}{Style.RESET_ALL}"
            return f"{timestamp} {level_colored}:  {self.app_name} {message}"

    # Log level wrappers
    def info(self, msg): self.logger.info(msg)
    def debug(self, msg): self.logger.debug(msg)
    def warning(self, msg): self.logger.warning(msg)
    def error(self, msg): self.logger.error(msg)
    def critical(self, msg): self.logger.critical(msg)

    def log(self, msg):
        self.logger.log(LOG_LEVEL, msg)

# -----------------------------------------------------------------------------
# End of File: ConsoleMessage.py
# -----------------------------------------------------------------------------
