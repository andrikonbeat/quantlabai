package com.quantlab.jforex_bridge.controller;

import com.quantlab.jforex_bridge.client.JForexClientManager;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/health")
public class HealthController {

    private final JForexClientManager clientManager;

    @Autowired
    public HealthController(JForexClientManager clientManager) {
        this.clientManager = clientManager;
    }

    @GetMapping
    public ResponseEntity<Map<String, Object>> health() {
        boolean connected = clientManager.isConnected();
        return ResponseEntity.ok(Map.of(
            "status", connected ? "UP" : "DOWN",
            "jforexConnected", connected,
            "timestamp", System.currentTimeMillis()
        ));
    }

    @PostMapping("/shutdown")
    public ResponseEntity<Map<String, String>> shutdown() {
        // Graceful shutdown
        new Thread(() -> {
            try {
                Thread.sleep(1000);
                System.exit(0);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }).start();
        return ResponseEntity.ok(Map.of("message", "Shutdown initiated"));
    }
}