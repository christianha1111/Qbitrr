import configparser
import pathlib
from datetime import datetime

CONFIG = configparser.ConfigParser(
    converters={
        "list": lambda x: [i.strip() for i in x.split(",")],
        "int": lambda x: int(x),
        "float": lambda x: float(x),
        "boolean": lambda x: x.lower().strip() in {"1", "true", "on", "enabled"},
        "upper": lambda x: str(x).upper().strip(),
        "year": lambda x: int(str(x).strip()) if x else datetime.now().year,
    }
)
CONFIG.read("./config.ini")
APPDATA_FOLDER = pathlib.Path().home().joinpath(".config", "qBitManager")
APPDATA_FOLDER.mkdir(parents=True, exist_ok=True)

# Settings Config Values
FAILED_CATEGORY = CONFIG.get("Settings", "FailedCategory", fallback="failed")
RECHECK_CATEGORY = CONFIG.get("Settings", "RecheckCategory", fallback="recheck")
CONSOLE_LOGGING_LEVEL_STRING = CONFIG.getupper("Settings", "ConsoleLevel", fallback="NOTICE")
COMPLETED_DOWNLOAD_FOLDER = CONFIG.get("Settings", "CompletedDownloadFolder")
NO_INTERNET_SLEEP_TIMER = CONFIG.getint("Settings", "NoInternetSleepTimer", fallback=60)
LOOP_SLEEP_TIMER = CONFIG.getint("Settings", "LoopSleepTimer", fallback=5)
PING_URLS = CONFIG.getlist(
    "Settings",
    "PingURLS",
    fallback=["one.one.one.one"],
)
IGNORE_TORRENTS_YOUNGER_THAN = CONFIG.getint("Settings", "IgnoreTorrentsYoungerThan", fallback=600)
