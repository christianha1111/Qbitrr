from __future__ import annotations

import atexit
import logging
import sys
import time
from multiprocessing import freeze_support
from pathos.multiprocessing import ProcessingPool as Pool0
from pathos.multiprocessing import Pool as Pool1
from pathos.pools import ParallelPool as Pool2
from pathos.parallel import ParallelPool as Pool3


import pathos
import qbittorrentapi
import requests
import pathlib
import shutil
from packaging import version as version_parser
from packaging.version import Version as VersionClass
from qbittorrentapi import APINames

from qBitrr.arss import ArrManager
from qBitrr.bundled_data import patched_version
from qBitrr.config import CONFIG, QBIT_DISABLED, SEARCH_ONLY, process_flags
from qBitrr.env_config import ENVIRO_CONFIG
from qBitrr.ffprobe import FFprobeDownloader
from qBitrr.logger import run_logs
from qBitrr.utils import ExpiringSet

CHILD_PROCESSES = []

logger = logging.getLogger("qBitrr")
run_logs(logger)


class qBitManager:
    min_supported_version = VersionClass("4.3.4")
    soft_not_supported_supported_version = VersionClass("4.4")
    max_supported_version = VersionClass("4.5")
    _head_less_mode = False

    def __init__(self):
        self.qBit_Host = CONFIG.get("QBit.Host", fallback="localhost")
        self.qBit_Port = CONFIG.get("QBit.Port", fallback=8105)
        self.qBit_UserName = CONFIG.get("QBit.UserName", fallback=None)
        self.qBit_Password = CONFIG.get("QBit.Password", fallback=None)
        self.logger = logging.getLogger(
            "qBitrr.Manager",
        )
        run_logs(self.logger)
        self.logger.debug(
            "QBitTorrent Config: Host: %s Port: %s, Username: %s, Password: %s",
            self.qBit_Host,
            self.qBit_Port,
            self.qBit_UserName,
            self.qBit_Password,
        )
        self._validated_version = False
        self.client = None
        self.current_qbit_version = None
        if not (QBIT_DISABLED or SEARCH_ONLY):
            self.client = qbittorrentapi.Client(
                host=self.qBit_Host,
                port=self.qBit_Port,
                username=self.qBit_UserName,
                password=self.qBit_Password,
                SIMPLE_RESPONSES=False,
            )
            try:
                self.current_qbit_version = version_parser.parse(self.client.app_version())
                self._validated_version = True
            except BaseException:
                self.current_qbit_version = self.min_supported_version
                self.logger.error(
                    "Could not establish qBitTorrent version, "
                    "you may experience errors, please report this error."
                )
            self._version_validator()
        self.expiring_bool = ExpiringSet(max_age_seconds=10)
        self.cache = {}
        self.name_cache = {}
        self.should_delay_torrent_scan = False  # If true torrent scan is delayed by 5 minutes.
        self.child_processes = []
        self.ffprobe_downloader = FFprobeDownloader()
        try:
            if not (SEARCH_ONLY or QBIT_DISABLED):
                self.ffprobe_downloader.update()
        except Exception as e:
            self.logger.error(
                "FFprobe manager error: %s while attempting to download/update FFprobe", e
            )
        counter_file = pathlib.Path.cwd().joinpath("counters")

        counter_file.mkdir(parents=True, exist_ok=True) #create folder, doesn't matter if already exists. makes sure next line doesn't fail
        shutil.rmtree(counter_file) #detele folder
        counter_file.mkdir(parents=True, exist_ok=True) #create folder,
        
        self.arr_manager = ArrManager(self).build_arr_instances()
        run_logs(self.logger)

    def _version_validator(self):
        if self.min_supported_version <= self.current_qbit_version < self.max_supported_version:
            if self.soft_not_supported_supported_version <= self.current_qbit_version:
                self.logger.warning(
                    "Current qBitTorrent version is not fully supported: %s, "
                    "historically there's been some issued with qBitTorrent 4.4+ and "
                    "qBitrr worked best with 4.3.9",
                    self.current_qbit_version,
                )
            elif self._validated_version:
                self.logger.hnotice(
                    "Current qBitTorrent version is supported: %s",
                    self.current_qbit_version,
                )
            else:
                self.logger.hnotice(
                    "Could not validate current qBitTorrent version, assuming: %s",
                    self.current_qbit_version,
                )
                time.sleep(10)
        else:
            self.logger.critical(
                "You are currently running qBitTorrent version %s, "
                "Supported version range is %s to < %s",
                self.current_qbit_version,
                self.min_supported_version,
                self.max_supported_version,
            )
            # sys.exit(1)

   
    def app_version(self, **kwargs):
        return self.client._get(
            _name=APINames.Application,
            _method="version",
            _retries=0,
            _retry_backoff_factor=0,
            **kwargs,
        )
    
    @property
    def is_alive(self) -> bool:
        try:
            if 1 in self.expiring_bool or self.client is None:
                return True
            self.client.app_version()
            self.logger.trace("Successfully connected to %s:%s", self.qBit_Host, self.qBit_Port)
            self.expiring_bool.add(1)
            return True
        except requests.RequestException:
            self.logger.warning("Could not connect to %s:%s", self.qBit_Host, self.qBit_Port)
        self.should_delay_torrent_scan = True
        return False

    def get_child_processes(self):
        run_logs(self.logger)
        self.logger.hnotice("Managing %s categories", len(self.arr_manager.managed_objects))
        count = 0
        procs = []
        for arr in self.arr_manager.managed_objects.values():
            numb, processes = arr.spawn_child_processes()
            count += numb
            procs.extend(processes)
        return procs

    def start_arrs(self, func):
        self.logger.notice("Starting child processes")
        func()
        self.logger.notice("Finishing child processes")

    def run(self):
        try:
            self.logger.notice("Starting %s child processes", len(self.child_processes))
            p = Pool1(2)
            dataset = range(0,10000)
            p.map(self.start_arrs, self.child_processes)
            
            #for p in self.child_processes:
            #    logger.notice("forforfor")
            #    p.start() 
            #[p.join() for p in self.child_processes]
        except KeyboardInterrupt:
            self.logger.hnotice("Detected Ctrl+C - Terminating process")
            sys.exit(0)
        except BaseException as e:
            self.logger.hnotice("Detected Ctrl+C - Terminating process: %r", e)
            sys.exit(1)


def run():
    global CHILD_PROCESSES
    early_exit = process_flags()
    if early_exit is True:
        sys.exit(0)
    logger.notice("Starting qBitrr: Version: %s.", patched_version)
    manager = qBitManager()
    run_logs(logger)
    #logger.debug("Environment variables: %r", ENVIRO_CONFIG)
    try:
        if CHILD_PROCESSES := manager.get_child_processes():
            manager.run()
        else:
            logger.warning(
                "No tasks to perform, if this is unintended double check your config file."
            )
    except KeyboardInterrupt:
        logger.hnotice("Detected Ctrl+C - Terminating process")
        sys.exit(0)
    except Exception:
        logger.notice("Attempting to terminate child processes, please wait a moment.")
        for child in manager.child_processes:
            child.kill()


def cleanup():
    for p in CHILD_PROCESSES:
        p.kill()
        p.terminate()


atexit.register(cleanup)


if __name__ == "__main__":
    freeze_support()
    run()
    logger.notice("All Done.")
