[app]
title           = NOVA VPN
package.name    = novavpn
package.domain  = org.nova

source.dir      = .
source.include_exts = py,png,jpg,kv,json

# ВАЖНО: Явно указываем Buildozer положить бинарник xray и папку assets в APK
source.include_patterns = assets/*, assets/xray

version         = 2.0

requirements    = python3,kivy==2.3.0,pyjnius==1.6.1,android

icon.filename   = assets/icon.png

orientation     = portrait
fullscreen      = 0

android.minapi  = 26
android.api     = 34

# ВАЖНО: Снизили NDK до 25b, иначе pyjnius не скомпилируется!
android.ndk     = 25b
android.ndk_api = 21
android.archs   = arm64-v8a

android.build_tools_version = 34.0.0

# ВАЖНО: Добавлено POST_NOTIFICATIONS для работы FOREGROUND_SERVICE в API 33+
android.permissions = INTERNET,FOREGROUND_SERVICE,RECEIVE_BOOT_COMPLETED,POST_NOTIFICATIONS

android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
