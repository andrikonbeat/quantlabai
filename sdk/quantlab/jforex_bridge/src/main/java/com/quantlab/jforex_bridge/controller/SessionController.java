package com.quantlab.jforex_bridge.controller;

import com.quantlab.jforex_bridge.dto.SessionData;
import com.quantlab.jforex_bridge.service.MarketDataService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Optional;

@RestController
@RequestMapping("/api/v1/sessions")
public class SessionController {

    private final MarketDataService marketDataService;

    @Autowired
    public SessionController(MarketDataService marketDataService) {
        this.marketDataService = marketDataService;
    }

    @GetMapping
    public ResponseEntity<List<SessionData>> getAllSessions() {
        return ResponseEntity.ok(marketDataService.getAllSessions());
    }

    @GetMapping("/{instrument}")
    public ResponseEntity<SessionData> getSession(@PathVariable String instrument) {
        return marketDataService.getSession(instrument.toUpperCase())
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }
}