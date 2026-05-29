# -*- coding: utf-8 -*-
"""
VPN сервис для Android
Управляет xray-core ARM бинарником
"""

import os
import sys
import json
import subprocess
import threading
import time
import socket
import urllib.request
import tempfile

try:
    from android import mActivity
    IS_ANDROID = True
except ImportError:
    IS_ANDROID = False

from xray_config import parse_vless, build_proxy_config, build_tun_config


def get_xray_path():
    """Находит xray бинарник"""
    if IS_ANDROID:
        # В Android приложении xray лежит в assets → files
        files_dir = str(mActivity.getFilesDir().getAbsolutePath())
        candidates = [
            os.path.join(files_dir, "xray"),
        ]
    else:
        script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        candidates = [
            os.path.join(script_dir, "xray"),
            os.path.join(script_dir, "xray.exe"),
            "xray",
        ]

    for p in candidates:
        if os.path.isfile(p):
            # На Android нужны права на выполнение
            if IS_ANDROID:
                os.chmod(p, 0o755)
            return p

    return None


def get_external_ip(proxy_port=None, timeout=10):
    """Получает внешний IP"""
    try:
        args = [
            "curl", "--silent",
            "--max-time", str(timeout),
            "--connect-timeout", "5"
        ]
        if proxy_port:
            args += ["--proxy",
                     f"socks5h://127.0.0.1:{proxy_port}"]
        args.append("https://api.ipify.org")

        r = subprocess.run(
            args, capture_output=True, text=True,
            timeout=timeout + 3
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass

    return None


class AndroidVpnHelper:
    """
    Вспомогательный класс для Android VpnService.
    На Android VpnService нужен Java код — используем
    subprocess для вызова через am start-service.
    """

    @staticmethod
    def start_vpn_service():
        """Запускает Android VpnService"""
        if not IS_ANDROID:
            return True

        try:
            from jnius import autoclass
            Context      = autoclass('android.content.Context')
            Intent       = autoclass('android.content.Intent')
            VpnService   = autoclass(
                'org.nova.vpn.NovaVpnService'
            )

            intent = Intent(mActivity, VpnService)
            mActivity.startService(intent)
            return True
        except Exception as e:
            print(f"VpnService error: {e}")
            return False

    @staticmethod
    def stop_vpn_service():
        if not IS_ANDROID:
            return

        try:
            from jnius import autoclass
            Intent     = autoclass('android.content.Intent')
            VpnService = autoclass(
                'org.nova.vpn.NovaVpnService'
            )

            intent = Intent(mActivity, VpnService)
            mActivity.stopService(intent)
        except Exception as e:
            print(f"Stop VpnService error: {e}")

    @staticmethod
    def setup_tun_android(socks_port=10808):
        """
        На Android TUN создаётся через VpnService.Builder.
        Возвращает файловый дескриптор TUN интерфейса.
        """
        if not IS_ANDROID:
            return None

        try:
            from jnius import autoclass

            VpnService = autoclass(
                'org.nova.vpn.NovaVpnService'
            )
            fd = VpnService.getInstance().buildTunInterface()
            return fd
        except Exception as e:
            print(f"TUN setup error: {e}")
            return None


class VPNService:
    """
    Основной класс управления VPN.

    Android особенности:
    - xray запускается как subprocess (ARM бинарник)
    - TUN создаётся через Android VpnService Java API
    - Нет прав root (используем VpnService permission)
    - Конфиги хранятся в app files dir
    """

    def __init__(self, log_callback=None):
        self.log_cb    = log_callback
        self.xray_proc = None
        self.connected = False
        self.mode      = "proxy"
        self._cfg_path = None
        self._stop_evt = threading.Event()

    def log(self, msg, level="INFO"):
        ts   = time.strftime("%H:%M:%S")
        line = f"[{ts}] [{level}] {msg}"
        print(line)
        if self.log_cb:
            self.log_cb(line)

    def start(self, vless_str, settings):
        if self.connected:
            return False

        self.log("Начало подключения...")
        self._stop_evt.clear()

        # Парсим VLESS
        try:
            cfg = parse_vless(vless_str)
            self.log(
                f"Сервер: {cfg['host']}:{cfg['port']}"
            )
        except Exception as e:
            self.log(f"Ошибка VLESS: {e}", "ERROR")
            return False

        # Ищем xray
        xray = get_xray_path()
        if not xray:
            self.log(
                "xray не найден!\n"
                "Поместите xray (ARM64) в папку приложения",
                "ERROR"
            )
            return False

        self.log(f"xray: {xray}")
        self.mode = settings.get("mode", "proxy")

        # Генерируем конфиг
        try:
            if self.mode == "tun":
                xray_cfg = build_tun_config(cfg, settings)
            else:
                xray_cfg = build_proxy_config(cfg, settings)
        except Exception as e:
            self.log(f"Ошибка конфига: {e}", "ERROR")
            return False

        # Сохраняем конфиг
        cfg_path = self._save_config(xray_cfg)
        if not cfg_path:
            return False

        # Запускаем xray
        if not self._start_xray(xray, cfg_path):
            return False

        # TUN режим на Android
        if self.mode == "tun":
            self._setup_android_tun(settings)

        self.connected = True
        self.log("✅ Подключено!", "OK")
        return True

    def _save_config(self, config_dict):
        """Сохраняет конфиг в папку приложения"""
        try:
            if IS_ANDROID:
                files_dir = str(
                    mActivity.getFilesDir().getAbsolutePath()
                )
                path = os.path.join(files_dir, "xray_config.json")
            else:
                fd, path = tempfile.mkstemp(suffix=".json")
                os.close(fd)

            with open(path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f,
                          indent=2, ensure_ascii=False)

            self._cfg_path = path
            self.log(f"Конфиг: {path}")
            return path

        except Exception as e:
            self.log(f"Ошибка сохранения конфига: {e}", "ERROR")
            return None

    def _start_xray(self, xray_path, config_path):
        """Запускает xray процесс"""
        try:
            self.xray_proc = subprocess.Popen(
                [xray_path, "run", "-c", config_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )

            # Читаем вывод в фоне
            threading.Thread(
                target=self._read_output,
                daemon=True
            ).start()

            time.sleep(2)

            if self.xray_proc.poll() is not None:
                self.log(
                    "xray завершился сразу после запуска!",
                    "ERROR"
                )
                return False

            self.log(
                f"xray запущен (PID: {self.xray_proc.pid})",
                "OK"
            )
            return True

        except PermissionError:
            self.log(
                "Нет прав на запуск xray!\n"
                "chmod +x xray выполнен автоматически...",
                "WARN"
            )
            try:
                os.chmod(xray_path, 0o755)
                return self._start_xray(xray_path, config_path)
            except Exception as e:
                self.log(f"Ошибка chmod: {e}", "ERROR")
                return False

        except Exception as e:
            self.log(f"Ошибка запуска xray: {e}", "ERROR")
            return False

    def _setup_android_tun(self, settings):
        """Настраивает TUN на Android"""
        self.log("Настройка TUN (Android VpnService)...")

        socks_port = settings.get("proxy_port", 10808)

        # Запускаем VpnService
        ok = AndroidVpnHelper.start_vpn_service()
        if ok:
            self.log("Android VpnService запущен", "OK")
        else:
            self.log(
                "VpnService недоступен — используется Proxy режим",
                "WARN"
            )
            self.mode = "proxy"

    def _read_output(self):
        """Читает вывод xray"""
        try:
            for line in self.xray_proc.stdout:
                decoded = line.decode(errors='replace').rstrip()
                if decoded:
                    lvl = ("WARN"
                           if "error" in decoded.lower()
                           else "INFO")
                    self.log(f"[xray] {decoded}", lvl)
        except Exception:
            pass

    def stop(self):
        self.log("Отключение...")
        self._stop_evt.set()

        # Останавливаем VpnService
        if IS_ANDROID and self.mode == "tun":
            AndroidVpnHelper.stop_vpn_service()

        # Убиваем xray
        if self.xray_proc and self.xray_proc.poll() is None:
            self.xray_proc.terminate()
            try:
                self.xray_proc.wait(timeout=4)
            except subprocess.TimeoutExpired:
                self.xray_proc.kill()
        self.xray_proc = None

        # Удаляем конфиг
        if self._cfg_path and os.path.exists(self._cfg_path):
            try:
                os.unlink(self._cfg_path)
            except Exception:
                pass
        self._cfg_path = None

        self.connected = False
        self.log("⏹ Отключено", "OK")

    def is_alive(self):
        return (self.xray_proc is not None and
                self.xray_proc.poll() is None)