# -*- coding: utf-8 -*-
"""
Генератор конфигов xray.
Общий для Windows и Android версий.
"""

import urllib.parse


def parse_vless(vless_str):
    vless_str = vless_str.strip()
    if not vless_str.startswith("vless://"):
        raise ValueError("Строка должна начинаться с vless://")

    rest = vless_str[8:]
    fragment = ""
    if "#" in rest:
        rest, fragment = rest.rsplit("#", 1)
        fragment = urllib.parse.unquote(fragment)

    at_pos = rest.find("@")
    if at_pos == -1:
        raise ValueError("Не найден символ @")

    uuid = rest[:at_pos]
    rest = rest[at_pos + 1:]

    hostport, params_str = (rest.split("?", 1) + [""])[:2]

    if hostport.startswith("["):
        bracket_end = hostport.find("]")
        host = hostport[1:bracket_end]
        port = int(hostport[bracket_end + 2:])
    else:
        host, port_str = hostport.rsplit(":", 1)
        port = int(port_str)

    params = {}
    for pair in params_str.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            params[k] = urllib.parse.unquote(v)

    return {
        "uuid":     uuid,
        "host":     host,
        "port":     port,
        "security": params.get("security", "none"),
        "sni":      params.get("sni", ""),
        "fp":       params.get("fp", "chrome"),
        "pbk":      params.get("pbk", ""),
        "sid":      params.get("sid", ""),
        "flow":     params.get("flow", ""),
        "network":  params.get("type", "tcp"),
        "spx":      params.get("spx", "/"),
        "name":     fragment,
    }


def _stream_settings(cfg, sni, fp, frag, frag_size, frag_int):
    rs = {
        "network":  "tcp",
        "security": "reality",
        "realitySettings": {
            "serverName":  sni or cfg["sni"],
            "fingerprint": fp,
            "publicKey":   cfg["pbk"],
            "shortId":     cfg["sid"],
            "spiderX":     cfg["spx"],
        }
    }
    if frag:
        rs["sockopt"] = {
            "fragment": {
                "packets":  "tlshello",
                "length":   frag_size,
                "interval": frag_int,
            }
        }
    return rs


def _bypass_ru_rules():
    return [
        {
            "type":        "field",
            "outboundTag": "direct",
            "ip":          ["geoip:ru"]
        },
        {
            "type":        "field",
            "outboundTag": "direct",
            "domain": [
                "suffix:.ru",        "suffix:.su",
                "suffix:.moscow",
                "domain:vk.com",     "domain:ok.ru",
                "domain:yandex.ru",  "domain:mail.ru",
                "domain:sber.ru",    "domain:gosuslugi.ru",
                "domain:ozon.ru",    "domain:wildberries.ru",
                "domain:avito.ru",   "domain:kinopoisk.ru",
            ]
        }
    ]


def build_proxy_config(cfg, settings):
    sni      = settings.get("sni") or cfg["sni"]
    fp       = settings.get("fingerprint", "chrome")
    frag     = settings.get("fragment", False)
    frag_sz  = settings.get("fragment_size", "10-30")
    frag_int = settings.get("fragment_int",  "10-20")
    p_port   = settings.get("proxy_port", 10808)
    h_port   = settings.get("http_port",  10809)
    bypass   = settings.get("bypass_ru", True)

    stream = _stream_settings(cfg, sni, fp, frag, frag_sz, frag_int)

    rules = [
        {
            "type":        "field",
            "outboundTag": "direct",
            "ip":          ["geoip:private"]
        }
    ]
    if bypass:
        rules += _bypass_ru_rules()

    return {
        "log": {"loglevel": "warning"},
        "dns": {
            "servers": ["1.1.1.1", "8.8.8.8"],
            "queryStrategy": "UseIPv4"
        },
        "inbounds": [
            {
                "tag":      "socks",
                "port":     p_port,
                "listen":   "127.0.0.1",
                "protocol": "socks",
                "settings": {"auth": "noauth", "udp": True},
                "sniffing": {
                    "enabled":      True,
                    "destOverride": ["http", "tls", "quic"]
                }
            },
            {
                "tag":      "http",
                "port":     h_port,
                "listen":   "127.0.0.1",
                "protocol": "http",
                "settings": {}
            }
        ],
        "outbounds": [
            {
                "tag":      "proxy",
                "protocol": "vless",
                "settings": {
                    "vnext": [{
                        "address": cfg["host"],
                        "port":    cfg["port"],
                        "users":   [{
                            "id":         cfg["uuid"],
                            "encryption": "none",
                            "flow":       cfg["flow"]
                        }]
                    }]
                },
                "streamSettings": stream
            },
            {
                "tag":      "direct",
                "protocol": "freedom",
                "settings": {"domainStrategy": "UseIPv4"}
            },
            {
                "tag":      "block",
                "protocol": "blackhole"
            }
        ],
        "routing": {
            "domainStrategy": "IPIfNonMatch",
            "rules":          rules
        }
    }


def build_tun_config(cfg, settings):
    """
    TUN конфиг для Android.
    На Android TUN создаётся через VpnService,
    xray получает трафик через SOCKS inbound.
    """
    sni      = settings.get("sni") or cfg["sni"]
    fp       = settings.get("fingerprint", "chrome")
    frag     = settings.get("fragment", False)
    frag_sz  = settings.get("fragment_size", "10-30")
    frag_int = settings.get("fragment_int",  "10-20")
    p_port   = settings.get("proxy_port", 10808)
    bypass   = settings.get("bypass_ru", True)

    stream = _stream_settings(cfg, sni, fp, frag, frag_sz, frag_int)

    rules = [
        {
            "type":        "field",
            "outboundTag": "dns-out",
            "port":        "53",
            "network":     "udp"
        },
        {
            "type":        "field",
            "outboundTag": "direct",
            "ip":          [cfg["host"]]
        },
        {
            "type":        "field",
            "outboundTag": "direct",
            "ip":          ["geoip:private"]
        },
    ]

    if bypass:
        rules += _bypass_ru_rules()

    rules.append({
        "type":        "field",
        "outboundTag": "proxy",
        "network":     "tcp,udp"
    })

    return {
        "log": {"loglevel": "warning"},
        "dns": {
            "servers": [
                {
                    "address":       "https://1.1.1.1/dns-query",
                    "domains":       ["geosite:geolocation-!cn"],
                    "skipFallback":  True,
                    "queryStrategy": "UseIPv4"
                },
                {
                    "address":       "8.8.8.8",
                    "queryStrategy": "UseIPv4"
                }
            ],
            "tag": "dns-in"
        },
        "inbounds": [
            {
                "tag":      "socks-in",
                "port":     p_port,
                "listen":   "127.0.0.1",
                "protocol": "socks",
                "settings": {"auth": "noauth", "udp": True},
                "sniffing": {
                    "enabled":      True,
                    "destOverride": ["http", "tls", "quic"],
                    "routeOnly":    False
                }
            }
        ],
        "outbounds": [
            {
                "tag":      "proxy",
                "protocol": "vless",
                "settings": {
                    "vnext": [{
                        "address": cfg["host"],
                        "port":    cfg["port"],
                        "users":   [{
                            "id":         cfg["uuid"],
                            "encryption": "none",
                            "flow":       cfg["flow"]
                        }]
                    }]
                },
                "streamSettings": stream,
                "mux": {"enabled": False, "concurrency": -1}
            },
            {
                "tag":      "direct",
                "protocol": "freedom",
                "settings": {"domainStrategy": "UseIPv4"}
            },
            {
                "tag":      "dns-out",
                "protocol": "dns"
            },
            {
                "tag":      "block",
                "protocol": "blackhole"
            }
        ],
        "routing": {
            "domainStrategy": "IPIfNonMatch",
            "rules":          rules
        }
    }