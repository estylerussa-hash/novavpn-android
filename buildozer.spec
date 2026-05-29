[app]
title           = NOVA VPN
package.name    = novavpn
package.domain  = org.nova

source.dir      = .
source.include_exts = py,png,jpg,kv,json

version         = 2.0

requirements    = python3==3.11,kivy==2.3.0,pyjnius==1.6.1,android

icon.filename   = assets/icon.png

orientation     = portrait
fullscreen      = 0

android.minapi  = 26
android.api     = 34
android.ndk     = 25b
android.ndk_api = 21
android.archs   = arm64-v8a

# Важно - используем build-tools 34 а не 37
android.build_tools_version = 34.0.0

android.permissions = INTERNET,FOREGROUND_SERVICE,RECEIVE_BOOT_COMPLETED

android.add_src = android_src

android.add_assets = assets/xray:xray

android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
