package com.quantlab.jforex_bridge.client;

import com.dukascopy.api.system.ClientFactory;
import com.dukascopy.api.system.IClient;
import com.dukascopy.api.system.ISystemListener;
import com.dukascopy.api.JFException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.annotation.PostConstruct;
import javax.annotation.PreDestroy;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.Consumer;

/**
 * Manages the JForex IClient lifecycle: connect, disconnect, reconnect, health checks.
 * This manages the low-level connection to the JForex platform.
 * The IContext (for data access) is obtained separately via the strategy's onStart().
 */
@Component
public class JForexClientManager {

    private static final Logger log = LoggerFactory.getLogger(JForexClientManager.class);

    @Value("${jforex.jnlp-url}")
    private String jnlpUrl;

    @Value("${jforex.username}")
    private String username;

    @Value("${jforex.password}")
    private String password;

    @Value("${jforex.demo:true}")
    private boolean demo;

    @Value("${jforex.connection.max-retries:5}")
    private int maxRetries;

    @Value("${jforex.connection.retry-delay-ms:5000}")
    private long retryDelayMs;

    @Value("${jforex.connection.timeout-ms:30000}")
    private long timeoutMs;

    private final AtomicReference<IClient> clientRef = new AtomicReference<>();
    private final AtomicBoolean connecting = new AtomicBoolean(false);
    private final AtomicBoolean shuttingDown = new AtomicBoolean(false);

    private final ScheduledExecutorService scheduler = Executors.newSingleThreadScheduledExecutor(r -> {
        Thread t = new Thread(r, "jforex-reconnect-scheduler");
        t.setDaemon(true);
        return t;
    });

    private Consumer<IClient> onConnectedCallback;
    private Consumer<Throwable> onDisconnectedCallback;

    @PostConstruct
    public void init() {
        log.info("STEP 0: init() called, demo={}", demo);
        // Auto-connect after bean initialization
        try {
            log.info("STEP 1: Scheduling auto-connection to JForex...");
            log.info("About to start connection thread");
            new Thread(() -> {
                try {
                    log.info("Thread started - Application ready - auto-connecting to JForex...");
                    connect().exceptionally(e -> {
                        log.error("Auto-connection to JForex failed: {}", e.getMessage());
                        return null;
                    });
                } catch (Exception e) {
                    log.error("Auto-connection to JForex failed: {}", e.getMessage(), e);
                }
            }, "jforex-auto-connect").start();
            log.info("Auto-connection to JForex scheduled");
        } catch (Exception e) {
            log.error("Failed to schedule auto-connection to JForex: {}", e.getMessage(), e);
        }
        log.info("init() completed");
    }

    @PreDestroy
    public void shutdown() {
        log.info("Shutting down JForexClientManager...");
        shuttingDown.set(true);
        scheduler.shutdownNow();
        disconnect().join();
        log.info("JForexClientManager shutdown complete");
    }

    /**
     * Connect to JForex platform.
     */
    public CompletableFuture<IClient> connect() {
        if (connecting.getAndSet(true)) {
            return CompletableFuture.completedFuture(clientRef.get());
        }

        return CompletableFuture.supplyAsync(() -> {
            try {
                IClient client = createClient();
                clientRef.set(client);
                log.info("JForex client created, connecting...");
                client.connect(getJnlpUrl(), username, password);

                // Wait for connection
                long start = System.currentTimeMillis();
                while (!client.isConnected()) {
                    if (System.currentTimeMillis() - start > timeoutMs) {
                        throw new IllegalStateException("Connection timeout after " + timeoutMs + "ms");
                    }
                    Thread.sleep(100);
                }

                log.info("JForex client connected successfully");
                if (onConnectedCallback != null) {
                    onConnectedCallback.accept(client);
                }
                return client;
            } catch (Exception e) {
                log.error("Failed to connect to JForex: {}", e.getMessage(), e);
                throw new RuntimeException("JForex connection failed", e);
            } finally {
                connecting.set(false);
            }
        });
    }

    /**
     * Disconnect from JForex platform.
     */
    public CompletableFuture<Void> disconnect() {
        return CompletableFuture.runAsync(() -> {
            IClient client = clientRef.getAndSet(null);
            if (client != null) {
                try {
                    log.info("Disconnecting JForex client...");
                    client.disconnect();
                    long start = System.currentTimeMillis();
                    while (client.isConnected() && System.currentTimeMillis() - start < 5000) {
                        Thread.sleep(100);
                    }
                    log.info("JForex client disconnected");
                } catch (Exception e) {
                    log.warn("Error during JForex disconnect: {}", e.getMessage());
                }
            }
            if (onDisconnectedCallback != null) {
                onDisconnectedCallback.accept(null);
            }
        });
    }

    /**
     * Check if currently connected.
     */
    public boolean isConnected() {
        IClient client = clientRef.get();
        return client != null && client.isConnected();
    }

    /**
     * Get the current client (if connected).
     */
    public IClient getClient() {
        return clientRef.get();
    }

    /**
     * Set callback for successful connection.
     */
    public void setOnConnectedCallback(Consumer<IClient> callback) {
        this.onConnectedCallback = callback;
    }

    /**
     * Set callback for disconnection.
     */
    public void setOnDisconnectedCallback(Consumer<Throwable> callback) {
        this.onDisconnectedCallback = callback;
    }

    /**
     * Schedule a reconnection attempt.
     */
    public void scheduleReconnect(long delayMs) {
        if (shuttingDown.get()) return;

        scheduler.schedule(() -> {
            if (!shuttingDown.get() && !isConnected()) {
                log.info("Attempting JForex reconnection...");
                connect().exceptionally(e -> {
                    log.error("Reconnection failed: {}", e.getMessage());
                    scheduleReconnect(retryDelayMs);
                    return null;
                });
            }
        }, delayMs, TimeUnit.MILLISECONDS);
    }

    /**
     * Check health and reconnect if needed.
     */
    public void healthCheck() {
        if (!shuttingDown.get() && !isConnected() && !connecting.get()) {
            log.warn("JForex health check failed - not connected, scheduling reconnect");
            scheduleReconnect(0);
        }
    }

    private IClient createClient() {
        try {
            return ClientFactory.getDefaultInstance();
        } catch (ClassNotFoundException | IllegalAccessException | InstantiationException e) {
            throw new RuntimeException("Failed to create JForex client", e);
        }
    }

    private String getJnlpUrl() {
        return demo
            ? "https://demo-jforex.dukascopy.com/client/jforex.jnlp"
            : jnlpUrl;
    }

    // Configuration setters for runtime updates
    public void setCredentials(String username, String password) {
        this.username = username;
        this.password = password;
    }

    public void setDemo(boolean demo) {
        this.demo = demo;
    }
}