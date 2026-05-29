package org.nova.vpn;

import android.content.Intent;
import android.net.VpnService;
import android.os.ParcelFileDescriptor;
import android.util.Log;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;

public class NovaVpnService extends VpnService {

    private static final String TAG = "NovaVpnService";
    private static NovaVpnService instance;

    private ParcelFileDescriptor vpnInterface;
    private Thread               xrayThread;
    private Process              xrayProcess;

    // ── Синглтон ─────────────────────────────────────────────────────

    public static NovaVpnService getInstance() {
        return instance;
    }

    @Override
    public void onCreate() {
        super.onCreate();
        instance = this;
        Log.d(TAG, "VpnService создан");
    }

    // ── Запуск ───────────────────────────────────────────────────────

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        Log.d(TAG, "VpnService запущен");

        // Создаём TUN интерфейс
        vpnInterface = buildTunInterface();

        if (vpnInterface == null) {
            Log.e(TAG, "Не удалось создать TUN интерфейс");
            stopSelf();
            return START_NOT_STICKY;
        }

        Log.d(TAG, "TUN fd: " + vpnInterface.getFd());
        return START_STICKY;
    }

    // ── TUN интерфейс ─────────────────────────────────────────────────

    public ParcelFileDescriptor buildTunInterface() {
        try {
            VpnService.Builder builder = new VpnService.Builder();

            builder.setSession("NOVA VPN")
                   // IP TUN интерфейса
                   .addAddress("10.0.0.2", 24)
                   // DNS через xray
                   .addDnsServer("1.1.1.1")
                   .addDnsServer("8.8.8.8")
                   // Роутинг — весь трафик через TUN
                   .addRoute("0.0.0.0", 0)
                   // Исключаем само приложение (антипетля)
                   .addDisallowedApplication(getPackageName())
                   // MTU
                   .setMtu(1500)
                   // Блокируем IPv6 (xray настроен на IPv4)
                   .addRoute("::", 0);

            vpnInterface = builder.establish();
            return vpnInterface;

        } catch (Exception e) {
            Log.e(TAG, "Ошибка создания TUN: " + e.getMessage());
            return null;
        }
    }

    // ── Остановка ─────────────────────────────────────────────────────

    @Override
    public void onDestroy() {
        Log.d(TAG, "VpnService остановлен");

        // Закрываем TUN
        if (vpnInterface != null) {
            try {
                vpnInterface.close();
            } catch (IOException e) {
                Log.e(TAG, "Ошибка закрытия TUN: " + e.getMessage());
            }
            vpnInterface = null;
        }

        instance = null;
        super.onDestroy();
    }

    // ── Вспомогательные ───────────────────────────────────────────────

    /**
     * Возвращает файловый дескриптор TUN для tun2socks
     */
    public int getTunFd() {
        if (vpnInterface != null) {
            return vpnInterface.getFd();
        }
        return -1;
    }

    /**
     * Защищает сокет от перехвата VPN (для подключения к серверу)
     */
    public static boolean protectSocket(int socketFd) {
        if (instance == null) return false;
        return instance.protect(socketFd);
    }
}
