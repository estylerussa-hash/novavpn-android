# -*- coding: utf-8 -*-
"""
NOVA VPN Android
Kivy UI + xray-core ARM + Android VpnService
"""

import os
import sys
import json
import threading
import time

# Kivy настройки ДО импорта
os.environ['KIVY_NO_ENV_CONFIG'] = '1'

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.switch import Switch
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.properties import StringProperty, BooleanProperty, ColorProperty
from kivy.uix.widget import Widget
from kivy.animation import Animation

# Платформа
try:
    from android import mActivity
    from android.permissions import (
        request_permissions, check_permission, Permission
    )
    IS_ANDROID = True
except ImportError:
    IS_ANDROID = False
    print("Не Android — режим разработки")

from vpn_service import VPNService
from xray_config import parse_vless

# ============================================================
# КОНСТАНТЫ
# ============================================================

APP_NAME    = "NOVA VPN"
APP_VERSION = "2.0"
CONFIG_FILE = "vpn_settings.json"

# Цветовая схема
C_BG        = (0.102, 0.102, 0.180, 1)   # #1a1a2e
C_PANEL     = (0.086, 0.129, 0.243, 1)   # #16213e
C_ACCENT    = (0.059, 0.204, 0.376, 1)   # #0f3460
C_GREEN     = (0.000, 0.824, 0.416, 1)   # #00d26a
C_RED       = (1.000, 0.278, 0.341, 1)   # #ff4757
C_YELLOW    = (1.000, 0.647, 0.008, 1)   # #ffa502
C_TEXT      = (0.878, 0.878, 0.878, 1)   # #e0e0e0
C_SUBTEXT   = (0.533, 0.533, 0.533, 1)   # #888888
C_BUTTON    = (0.914, 0.271, 0.376, 1)   # #e94560
C_BTN_OFF   = (0.176, 0.416, 0.310, 1)   # #2d6a4f

DEFAULT_SETTINGS = {
    "vless_string":  "",
    "mode":          "proxy",
    "sni":           "",
    "fingerprint":   "chrome",
    "fragment":      False,
    "fragment_size": "10-30",
    "fragment_int":  "10-20",
    "proxy_port":    10808,
    "http_port":     10809,
    "auto_connect":  False,
    "bypass_ru":     True,
    "last_ip":       "",
}

# ============================================================
# UI КОМПОНЕНТЫ
# ============================================================

class RoundedBox(Widget):
    """Виджет с закруглёнными углами и фоном"""

    def __init__(self, bg_color=C_PANEL, radius=12, **kwargs):
        super().__init__(**kwargs)
        self.bg_color = bg_color
        self.radius   = radius
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.bg_color)
            RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[self.radius]
            )


class Card(BoxLayout):
    """Карточка с заголовком и контентом"""

    def __init__(self, title="", bg=C_PANEL, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("padding",     [dp(14), dp(10)])
        kwargs.setdefault("spacing",     dp(6))
        super().__init__(**kwargs)

        with self.canvas.before:
            Color(*bg)
            self._rect = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[dp(10)]
            )

        self.bind(pos=self._update_rect, size=self._update_rect)

        if title:
            self.add_widget(Label(
                text=title,
                font_size=sp(11),
                color=C_SUBTEXT,
                bold=True,
                size_hint_y=None,
                height=dp(20),
                halign="left",
                text_size=(None, None)
            ))

    def _update_rect(self, *_):
        self._rect.pos  = self.pos
        self._rect.size = self.size


class NLabel(Label):
    """Label с удобными дефолтами"""

    def __init__(self, **kwargs):
        kwargs.setdefault("color",      C_TEXT)
        kwargs.setdefault("font_size",  sp(14))
        kwargs.setdefault("halign",     "left")
        kwargs.setdefault("valign",     "middle")
        super().__init__(**kwargs)
        self.bind(size=lambda *_: setattr(
            self, 'text_size', self.size
        ))


class NButton(Button):
    """Стилизованная кнопка"""

    def __init__(self, bg=C_BUTTON, **kwargs):
        kwargs.setdefault("font_size",      sp(14))
        kwargs.setdefault("bold",           True)
        kwargs.setdefault("color",          (1, 1, 1, 1))
        kwargs.setdefault("background_color", bg)
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("size_hint_y",    None)
        kwargs.setdefault("height",         dp(48))
        super().__init__(**kwargs)


class SmallButton(Button):
    """Маленькая кнопка"""

    def __init__(self, bg=C_ACCENT, **kwargs):
        kwargs.setdefault("font_size",          sp(12))
        kwargs.setdefault("color",              C_TEXT)
        kwargs.setdefault("background_color",   bg)
        kwargs.setdefault("background_normal",  "")
        kwargs.setdefault("size_hint_y",        None)
        kwargs.setdefault("height",             dp(34))
        kwargs.setdefault("size_hint_x",        None)
        kwargs.setdefault("width",              dp(100))
        super().__init__(**kwargs)


class StatusDot(Widget):
    """Цветной индикатор статуса"""

    def __init__(self, color=C_RED, **kwargs):
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("size",      (dp(16), dp(16)))
        super().__init__(**kwargs)
        self._color = color
        self.bind(pos=self._draw, size=self._draw)
        self._draw()

    def set_color(self, color):
        self._color = color
        self._draw()

    def _draw(self, *_):
        self.canvas.clear()
        with self.canvas:
            Color(*self._color)
            RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[dp(8)]
            )


class LogWidget(ScrollView):
    """Виджет лога с автопрокруткой"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.do_scroll_x = False

        self._label = Label(
            text="",
            font_size=sp(10),
            font_name="RobotoMono",
            color=(0.0, 1.0, 0.533, 1),
            halign="left",
            valign="top",
            size_hint_y=None,
            markup=True,
        )
        self._label.bind(
            texture_size=lambda _, ts: setattr(
                self._label, 'height', ts[1]
            )
        )
        self.add_widget(self._label)

    def append(self, line, level="INFO"):
        color_map = {
            "ERROR": "ff4757",
            "WARN":  "ffa502",
            "OK":    "00d26a",
            "INFO":  "00ff88",
        }
        color = color_map.get(level, "00ff88")
        escaped = line.replace("[", "[[").replace("]", "]]")
        entry   = f"[color=#{color}]{escaped}[/color]\n"

        def _do(*_):
            self._label.text += entry
            # Прокрутка вниз
            Clock.schedule_once(
                lambda *_: setattr(self, 'scroll_y', 0), 0.05
            )

        Clock.schedule_once(_do)

    def clear(self):
        Clock.schedule_once(
            lambda *_: setattr(self._label, 'text', "")
        )


# ============================================================
# ГЛАВНЫЙ ЭКРАН
# ============================================================

class MainScreen(Screen):

    def __init__(self, app_ref, **kwargs):
        super().__init__(**kwargs)
        self.app = app_ref
        self._build()

    def _build(self):
        root = BoxLayout(
            orientation="vertical",
            spacing=0,
            padding=0
        )

        # ── Шапка ──────────────────────────────────────────────────
        root.add_widget(self._build_header())

        # ── Контент (прокручиваемый) ────────────────────────────────
        scroll = ScrollView(do_scroll_x=False)
        content = BoxLayout(
            orientation="vertical",
            spacing=dp(8),
            padding=[dp(12), dp(8), dp(12), dp(12)],
            size_hint_y=None,
        )
        content.bind(
            minimum_height=content.setter('height')
        )

        content.add_widget(self._build_status_card())
        content.add_widget(self._build_vless_card())
        content.add_widget(self._build_mode_card())
        content.add_widget(self._build_connect_btn())
        content.add_widget(self._build_log_card())

        scroll.add_widget(content)
        root.add_widget(scroll)

        # ── Нижняя панель ───────────────────────────────────────────
        root.add_widget(self._build_bottom_bar())

        self.add_widget(root)

    def _build_header(self):
        hdr = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(56),
            padding=[dp(16), dp(8)],
        )
        with hdr.canvas.before:
            Color(*C_ACCENT)
            self._hdr_rect = Rectangle(pos=hdr.pos, size=hdr.size)
        hdr.bind(
            pos=lambda _, v: setattr(self._hdr_rect, 'pos', v),
            size=lambda _, v: setattr(self._hdr_rect, 'size', v)
        )

        hdr.add_widget(Label(
            text=f"🛡  {APP_NAME}",
            font_size=sp(20),
            bold=True,
            color=C_TEXT,
            halign="left",
        ))

        # Кнопка настроек
        settings_btn = Button(
            text="⚙",
            font_size=sp(20),
            background_color=(0, 0, 0, 0),
            color=C_TEXT,
            size_hint=(None, None),
            size=(dp(44), dp(44))
        )
        settings_btn.bind(on_press=lambda _: self.app.go_settings())
        hdr.add_widget(settings_btn)

        return hdr

    def _build_status_card(self):
        card = Card(bg=C_ACCENT, size_hint_y=None, height=dp(90))

        row = BoxLayout(spacing=dp(12))

        # Индикатор
        self.status_dot = StatusDot(color=C_RED)
        dot_wrap = BoxLayout(
            size_hint=(None, None),
            size=(dp(20), dp(20)),
            padding=[dp(2), dp(2)]
        )
        dot_wrap.add_widget(self.status_dot)

        col = BoxLayout(orientation="vertical", spacing=dp(4))

        self.status_lbl = Label(
            text="Отключено",
            font_size=sp(18),
            bold=True,
            color=C_TEXT,
            halign="left",
            size_hint_y=None,
            height=dp(28)
        )

        self.ip_lbl = Label(
            text="IP: —",
            font_size=sp(12),
            color=C_SUBTEXT,
            halign="left",
            size_hint_y=None,
            height=dp(20)
        )

        col.add_widget(self.status_lbl)
        col.add_widget(self.ip_lbl)

        row.add_widget(dot_wrap)
        row.add_widget(col)
        card.add_widget(row)

        return card

    def _build_vless_card(self):
        card = Card(
            title="VLESS СТРОКА",
            size_hint_y=None,
            height=dp(160)
        )

        # Поле ввода
        self.vless_input = TextInput(
            hint_text="vless://...",
            font_size=sp(11),
            font_name="RobotoMono",
            foreground_color=C_TEXT,
            hint_text_color=(*C_SUBTEXT[:3], 0.5),
            background_color=(0.05, 0.11, 0.165, 1),
            cursor_color=C_TEXT,
            multiline=False,
            password=True,
            size_hint_y=None,
            height=dp(44),
        )

        # Кнопки
        btn_row = BoxLayout(
            spacing=dp(6),
            size_hint_y=None,
            height=dp(36)
        )

        show_btn = SmallButton(text="👁 Показать", width=dp(110))
        show_btn.bind(on_press=self._toggle_vless_visibility)

        paste_btn = SmallButton(text="📋 Вставить", width=dp(110))
        paste_btn.bind(on_press=self._paste_vless)

        check_btn = SmallButton(
            text="✔ Проверить", width=dp(110), bg=C_ACCENT
        )
        check_btn.bind(on_press=self._check_vless)

        clear_btn = SmallButton(text="✖", width=dp(44), bg=C_RED)
        clear_btn.bind(on_press=lambda _: setattr(
            self.vless_input, 'text', ''
        ))

        btn_row.add_widget(show_btn)
        btn_row.add_widget(paste_btn)
        btn_row.add_widget(check_btn)
        btn_row.add_widget(clear_btn)

        self.vless_info = Label(
            text="",
            font_size=sp(10),
            color=C_SUBTEXT,
            halign="left",
            size_hint_y=None,
            height=dp(18)
        )

        card.add_widget(self.vless_input)
        card.add_widget(btn_row)
        card.add_widget(self.vless_info)

        return card

    def _build_mode_card(self):
        card = Card(
            title="РЕЖИМ",
            size_hint_y=None,
            height=dp(100)
        )

        self.mode_spinner = Spinner(
            text="🌐 Proxy (браузер)",
            values=[
                "🌐 Proxy (браузер)",
                "🔒 TUN (весь трафик)",
            ],
            font_size=sp(13),
            background_color=C_ACCENT,
            color=C_TEXT,
            background_normal="",
            size_hint_y=None,
            height=dp(40),
        )

        mode_desc = Label(
            text="Proxy: нужна настройка в браузере\n"
                 "TUN: весь трафик автоматически (Telegram, игры)",
            font_size=sp(11),
            color=C_SUBTEXT,
            halign="left",
            size_hint_y=None,
            height=dp(36),
        )
        mode_desc.bind(size=lambda w, _: setattr(
            w, 'text_size', w.size
        ))

        card.add_widget(self.mode_spinner)
        card.add_widget(mode_desc)

        return card

    def _build_connect_btn(self):
        self.connect_btn = NButton(
            text="⚡  ПОДКЛЮЧИТЬ",
            bg=C_BUTTON,
            height=dp(56),
            font_size=sp(16),
        )
        self.connect_btn.bind(on_press=self._toggle_connection)
        return self.connect_btn

    def _build_log_card(self):
        card = Card(
            title="ЛОГ",
            size_hint_y=None,
            height=dp(220)
        )

        clear_btn = SmallButton(
            text="Очистить", width=dp(90)
        )

        header = BoxLayout(
            size_hint_y=None, height=dp(28),
            spacing=dp(8)
        )
        header.add_widget(Widget())
        header.add_widget(clear_btn)

        self.log_widget = LogWidget()
        clear_btn.bind(
            on_press=lambda _: self.log_widget.clear()
        )

        card.add_widget(header)
        card.add_widget(self.log_widget)

        return card

    def _build_bottom_bar(self):
        bar = BoxLayout(
            size_hint_y=None,
            height=dp(28),
            padding=[dp(10), dp(4)],
        )
        with bar.canvas.before:
            Color(*C_ACCENT)
            self._bar_rect = Rectangle(pos=bar.pos, size=bar.size)
        bar.bind(
            pos=lambda _, v: setattr(self._bar_rect, 'pos', v),
            size=lambda _, v: setattr(self._bar_rect, 'size', v)
        )

        self.bottom_lbl = Label(
            text="Готов к подключению",
            font_size=sp(10),
            color=C_SUBTEXT,
            halign="left"
        )
        bar.add_widget(self.bottom_lbl)

        return bar

    # ── Действия ─────────────────────────────────────────────────────

    def _toggle_vless_visibility(self, *_):
        self.vless_input.password = not self.vless_input.password

    def _paste_vless(self, *_):
        try:
            if IS_ANDROID:
                from android import python_act
                clipboard = mActivity.getSystemService("clipboard")
                clip = clipboard.getPrimaryClip()
                if clip and clip.getItemCount() > 0:
                    text = str(clip.getItemAt(0).getText())
                    self.vless_input.text = text.strip()
            else:
                from kivy.core.clipboard import Clipboard
                text = Clipboard.paste()
                if text:
                    self.vless_input.text = text.strip()

            self._check_vless()
        except Exception as e:
            self.log(f"Ошибка вставки: {e}", "WARN")

    def _check_vless(self, *_):
        vless = self.vless_input.text.strip()
        if not vless:
            self.vless_info.text  = "⚠ Вставьте VLESS строку"
            self.vless_info.color = C_YELLOW
            return

        try:
            cfg  = parse_vless(vless)
            name = cfg.get('name') or cfg['host']
            self.vless_info.text  = (
                f"✅ {name} | {cfg['host']}:{cfg['port']}"
                f" | {cfg['security']}"
            )
            self.vless_info.color = C_GREEN
        except Exception as e:
            self.vless_info.text  = f"❌ {e}"
            self.vless_info.color = C_RED

    def _toggle_connection(self, *_):
        if self.app.vpn.connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        vless = self.vless_input.text.strip()
        if not vless:
            self._show_popup("Ошибка", "Вставьте VLESS строку!")
            return

        # Запрашиваем разрешения Android
        if IS_ANDROID:
            self._request_vpn_permission(vless)
        else:
            self._do_connect(vless)

    def _request_vpn_permission(self, vless):
        """Запрашивает разрешение VpnService у Android"""
        try:
            from android.permissions import Permission
            # Сначала INTERNET
            request_permissions(
                [Permission.INTERNET,
                 Permission.FOREGROUND_SERVICE],
                lambda perms, results: self._on_permissions(
                    perms, results, vless
                )
            )
        except Exception as e:
            self.log(f"Ошибка разрешений: {e}", "WARN")
            self._do_connect(vless)

    def _on_permissions(self, permissions, results, vless):
        if all(results):
            self._do_connect(vless)
        else:
            self._show_popup(
                "Разрешения",
                "Нет разрешений INTERNET.\nПредоставьте их в настройках."
            )

    def _do_connect(self, vless):
        """Запускает подключение в фоновом потоке"""
        self.connect_btn.text             = "⏳  Подключение..."
        self.connect_btn.background_color = C_YELLOW
        self.connect_btn.disabled         = True
        self.update_status("Подключение...", C_YELLOW)

        settings = self.app.get_settings()
        settings["vless_string"] = vless
        settings["mode"] = (
            "tun"
            if "TUN" in self.mode_spinner.text
            else "proxy"
        )

        def _worker():
            ok = self.app.vpn.start(vless, settings)

            def _after(*_):
                self.connect_btn.disabled = False
                if ok:
                    self.connect_btn.text = "⏹  ОТКЛЮЧИТЬ"
                    self.connect_btn.background_color = C_BTN_OFF
                    self.update_status("Подключено ✓", C_GREEN)
                    Clock.schedule_once(
                        lambda *_: self._fetch_ip(), 3
                    )
                else:
                    self.connect_btn.text = "⚡  ПОДКЛЮЧИТЬ"
                    self.connect_btn.background_color = C_BUTTON
                    self.update_status("Ошибка", C_RED)

            Clock.schedule_once(_after, 0)

        threading.Thread(target=_worker, daemon=True).start()

    def _disconnect(self):
        self.connect_btn.text     = "⏳  Отключение..."
        self.connect_btn.disabled = True

        def _worker():
            self.app.vpn.stop()

            def _after(*_):
                self.connect_btn.text             = "⚡  ПОДКЛЮЧИТЬ"
                self.connect_btn.background_color = C_BUTTON
                self.connect_btn.disabled         = False
                self.update_status("Отключено", C_RED)
                self.ip_lbl.text = "IP: —"

            Clock.schedule_once(_after, 0)

        threading.Thread(target=_worker, daemon=True).start()

    def _fetch_ip(self):
        def _worker():
            from vpn_service import get_external_ip
            port = self.app.settings.get("proxy_port", 10808)
            ip   = get_external_ip(proxy_port=port)

            def _after(*_):
                if ip:
                    self.ip_lbl.text = f"IP: {ip}"
                    self.log(f"Внешний IP: {ip}", "OK")
                else:
                    self.ip_lbl.text = "IP: не определён"

            Clock.schedule_once(_after, 0)

        threading.Thread(target=_worker, daemon=True).start()

    def update_status(self, text, color):
        def _do(*_):
            self.status_lbl.text = text
            self.status_dot.set_color(color)
        Clock.schedule_once(_do, 0)

    def log(self, line, level="INFO"):
        self.log_widget.append(line, level)
        Clock.schedule_once(
            lambda *_: setattr(
                self.bottom_lbl, 'text', line[:50]
            ), 0
        )

    def _show_popup(self, title, msg):
        content = BoxLayout(
            orientation="vertical",
            padding=dp(16),
            spacing=dp(10)
        )
        content.add_widget(Label(
            text=msg, color=C_TEXT,
            halign="center"
        ))
        btn = NButton(text="OK", bg=C_BUTTON)
        content.add_widget(btn)

        popup = Popup(
            title=title,
            content=content,
            size_hint=(0.85, None),
            height=dp(200),
            background_color=C_PANEL,
            title_color=C_TEXT,
        )
        btn.bind(on_press=popup.dismiss)
        popup.open()


# ============================================================
# ЭКРАН НАСТРОЕК
# ============================================================

class SettingsScreen(Screen):

    def __init__(self, app_ref, **kwargs):
        super().__init__(**kwargs)
        self.app = app_ref
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical")

        # Шапка
        hdr = BoxLayout(
            size_hint_y=None, height=dp(56),
            padding=[dp(8), dp(8)],
        )
        with hdr.canvas.before:
            Color(*C_ACCENT)
            rect = Rectangle(pos=hdr.pos, size=hdr.size)
        hdr.bind(
            pos=lambda _, v: setattr(rect, 'pos', v),
            size=lambda _, v: setattr(rect, 'size', v)
        )

        back_btn = Button(
            text="←",
            font_size=sp(20),
            background_color=(0, 0, 0, 0),
            color=C_TEXT,
            size_hint=(None, 1),
            width=dp(44)
        )
        back_btn.bind(on_press=lambda _: self.app.go_main())

        hdr.add_widget(back_btn)
        hdr.add_widget(Label(
            text="Настройки",
            font_size=sp(18),
            bold=True,
            color=C_TEXT
        ))
        root.add_widget(hdr)

        # Содержимое
        scroll = ScrollView(do_scroll_x=False)
        content = BoxLayout(
            orientation="vertical",
            spacing=dp(8),
            padding=[dp(12), dp(8)],
            size_hint_y=None
        )
        content.bind(
            minimum_height=content.setter('height')
        )

        content.add_widget(self._build_network_settings())
        content.add_widget(self._build_reality_settings())
        content.add_widget(self._build_fragment_settings())
        content.add_widget(self._build_misc_settings())
        content.add_widget(self._build_save_btn())

        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    def _row(self, label_text, widget, height=dp(44)):
        row = BoxLayout(
            size_hint_y=None,
            height=height,
            spacing=dp(8)
        )
        row.add_widget(Label(
            text=label_text,
            font_size=sp(13),
            color=C_TEXT,
            size_hint_x=0.4,
            halign="left"
        ))
        row.add_widget(widget)
        return row

    def _input(self, hint="", text="", is_num=False):
        return TextInput(
            text=str(text),
            hint_text=hint,
            font_size=sp(12),
            foreground_color=C_TEXT,
            background_color=(0.05, 0.11, 0.165, 1),
            cursor_color=C_TEXT,
            multiline=False,
            input_filter="int" if is_num else None,
            size_hint_y=None,
            height=dp(36),
        )

    def _build_network_settings(self):
        card = Card(title="СЕТЬ", size_hint_y=None, height=dp(160))

        s = self.app.settings

        self.sni_input = self._input("из VLESS", s.get("sni", ""))
        card.add_widget(self._row("SNI:", self.sni_input))

        self.proxy_port_input = self._input(
            "10808", s.get("proxy_port", 10808), is_num=True
        )
        card.add_widget(self._row("SOCKS порт:", self.proxy_port_input))

        self.http_port_input = self._input(
            "10809", s.get("http_port", 10809), is_num=True
        )
        card.add_widget(self._row("HTTP порт:", self.http_port_input))

        return card

    def _build_reality_settings(self):
        card = Card(title="REALITY", size_hint_y=None, height=dp(80))

        self.fp_spinner = Spinner(
            text=self.app.settings.get("fingerprint", "chrome"),
            values=["chrome", "firefox", "safari",
                    "edge", "ios", "android", "random"],
            background_color=C_ACCENT,
            background_normal="",
            color=C_TEXT,
            font_size=sp(13),
            size_hint_y=None,
            height=dp(38),
        )
        card.add_widget(self._row("Fingerprint:", self.fp_spinner))

        return card

    def _build_fragment_settings(self):
        card = Card(title="FRAGMENT", size_hint_y=None, height=dp(140))

        s = self.app.settings

        frag_row = BoxLayout(
            size_hint_y=None, height=dp(40), spacing=dp(8)
        )
        frag_row.add_widget(Label(
            text="Fragment:", font_size=sp(13),
            color=C_TEXT, size_hint_x=0.4, halign="left"
        ))
        self.frag_switch = Switch(
            active=s.get("fragment", False),
            size_hint_x=0.6
        )
        frag_row.add_widget(self.frag_switch)
        card.add_widget(frag_row)

        self.frag_size_input = self._input(
            "10-30", s.get("fragment_size", "10-30")
        )
        card.add_widget(self._row("Size:", self.frag_size_input))

        self.frag_int_input = self._input(
            "10-20", s.get("fragment_int", "10-20")
        )
        card.add_widget(self._row("Interval:", self.frag_int_input))

        return card

    def _build_misc_settings(self):
        card = Card(title="ПРОЧЕЕ", size_hint_y=None, height=dp(110))

        s = self.app.settings

        bypass_row = BoxLayout(
            size_hint_y=None, height=dp(44), spacing=dp(8)
        )
        bypass_row.add_widget(Label(
            text="Bypass RU:", font_size=sp(13),
            color=C_TEXT, size_hint_x=0.4, halign="left"
        ))
        self.bypass_switch = Switch(
            active=s.get("bypass_ru", True),
            size_hint_x=0.6
        )
        bypass_row.add_widget(self.bypass_switch)
        card.add_widget(bypass_row)

        auto_row = BoxLayout(
            size_hint_y=None, height=dp(44), spacing=dp(8)
        )
        auto_row.add_widget(Label(
            text="Автоподключение:", font_size=sp(13),
            color=C_TEXT, size_hint_x=0.4, halign="left"
        ))
        self.auto_switch = Switch(
            active=s.get("auto_connect", False),
            size_hint_x=0.6
        )
        auto_row.add_widget(self.auto_switch)
        card.add_widget(auto_row)

        return card

    def _build_save_btn(self):
        btn = NButton(text="💾  Сохранить", bg=C_BTN_OFF)
        btn.bind(on_press=self._save)
        return btn

    def _save(self, *_):
        s = self.app.settings
        s["sni"]           = self.sni_input.text.strip()
        s["fingerprint"]   = self.fp_spinner.text
        s["fragment"]      = self.frag_switch.active
        s["fragment_size"] = self.frag_size_input.text.strip()
        s["fragment_int"]  = self.frag_int_input.text.strip()
        s["bypass_ru"]     = self.bypass_switch.active
        s["auto_connect"]  = self.auto_switch.active

        try:
            s["proxy_port"] = int(self.proxy_port_input.text)
            s["http_port"]  = int(self.http_port_input.text)
        except ValueError:
            pass

        self.app.save_settings()
        self._show_saved()

    def _show_saved(self):
        popup = Popup(
            title="Сохранено",
            content=Label(text="Настройки сохранены ✓", color=C_TEXT),
            size_hint=(0.6, None),
            height=dp(150),
            background_color=C_PANEL,
            title_color=C_GREEN,
        )
        Clock.schedule_once(lambda *_: popup.dismiss(), 1.5)
        popup.open()

    def on_enter(self):
        """Обновляем поля при входе на экран"""
        s = self.app.settings
        self.sni_input.text       = s.get("sni", "")
        self.fp_spinner.text      = s.get("fingerprint", "chrome")
        self.frag_switch.active   = s.get("fragment", False)
        self.frag_size_input.text = s.get("fragment_size", "10-30")
        self.frag_int_input.text  = s.get("fragment_int",  "10-20")
        self.bypass_switch.active = s.get("bypass_ru", True)
        self.auto_switch.active   = s.get("auto_connect", False)
        try:
            self.proxy_port_input.text = str(s.get("proxy_port", 10808))
            self.http_port_input.text  = str(s.get("http_port",  10809))
        except Exception:
            pass


# ============================================================
# ГЛАВНОЕ ПРИЛОЖЕНИЕ
# ============================================================

class NovaVPNApp(App):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.settings = DEFAULT_SETTINGS.copy()
        self.vpn      = VPNService(log_callback=self._log_callback)
        self._load_settings()

    def build(self):
        Window.clearcolor = C_BG

        self.sm = ScreenManager(
            transition=FadeTransition(duration=0.15)
        )

        self.main_screen     = MainScreen(app_ref=self, name="main")
        self.settings_screen = SettingsScreen(app_ref=self, name="settings")

        self.sm.add_widget(self.main_screen)
        self.sm.add_widget(self.settings_screen)

        # Мониторинг xray
        Clock.schedule_interval(self._monitor, 5)

        # Автоподключение
        if (self.settings.get("auto_connect") and
                self.settings.get("vless_string")):
            Clock.schedule_once(
                lambda *_: self.main_screen._do_connect(
                    self.settings["vless_string"]
                ), 2
            )

        return self.sm

    def go_settings(self):
        self.sm.current = "settings"

    def go_main(self):
        self.sm.current = "main"

    def get_settings(self):
        return self.settings.copy()

    def _log_callback(self, line):
        level = "INFO"
        if "[ERROR]" in line:
            level = "ERROR"
        elif "[WARN]" in line:
            level = "WARN"
        elif "[OK]" in line:
            level = "OK"

        if hasattr(self, 'main_screen'):
            self.main_screen.log(line, level)

    def _monitor(self, dt):
        if self.vpn.connected and not self.vpn.is_alive():
            self.vpn.connected = False
            screen = self.main_screen

            def _crash(*_):
                screen.connect_btn.text             = "⚡  ПОДКЛЮЧИТЬ"
                screen.connect_btn.background_color = C_BUTTON
                screen.connect_btn.disabled         = False
                screen.update_status("Соединение прервано!", C_RED)
                screen.ip_lbl.text = "IP: —"
                screen.log("xray завершился неожиданно!", "ERROR")

            Clock.schedule_once(_crash, 0)

    # ── Настройки ─────────────────────────────────────────────────

    def _load_settings(self):
        try:
            path = os.path.join(self._get_data_dir(), CONFIG_FILE)
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    self.settings.update(json.load(f))
        except Exception as e:
            print(f"Ошибка загрузки настроек: {e}")

    def save_settings(self):
        try:
            path = os.path.join(self._get_data_dir(), CONFIG_FILE)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f,
                          indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка сохранения настроек: {e}")

    def _get_data_dir(self):
        if IS_ANDROID:
            from android import mActivity
            return str(mActivity.getFilesDir().getAbsolutePath())
        return os.path.expanduser("~")

    def on_stop(self):
        if self.vpn.connected:
            self.vpn.stop()


if __name__ == "__main__":
    NovaVPNApp().run()