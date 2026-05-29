[app]
title           = NOVA VPN
package.name    = novavpn
package.domain  = org.nova

source.dir      = .
source.include_exts = py,png,jpg,kv,json,java

version         = 2.0

requirements    = python3==3.11,\
                  kivy==2.3.0,\
                  pyjnius==1.6.1,\
                  android

# Иконка
icon.filename   = assets/icon.png

orientation     = portrait
fullscreen      = 0

# Android
android.minapi  = 26
android.api     = 34
android.ndk     = 25b
android.ndk_api = 21
android.archs   = arm64-v8a

android.permissions = \
    INTERNET,\
    FOREGROUND_SERVICE,\
    FOREGROUND_SERVICE_SPECIAL_USE,\
    RECEIVE_BOOT_COMPLETED

# Java исходники
android.add_src = android_src

# xray бинарник
android.add_assets = assets/xray:xray

# Подпись (для debug не нужна)
android.debug   = 1

[buildozer]
log_level = 2
warn_on_root = 1