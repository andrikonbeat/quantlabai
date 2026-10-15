package com.quantlab.jforex_bridge.controller;

import com.quantlab.jforex_bridge.dto.SpreadData;
import com.quantlab.jforex_bridge.service.MarketDataService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Optional;

@RestController
@RequestMapping("/api/v1/spreads")
public class SpreadController {

    private final MarketDataService marketDataService;

    @Autowired
    public SpreadController(MarketDataService marketDataService) {
        this.marketDataService = marketDataService;
    }

    @GetMapping
    public ResponseEntity<List<SpreadData>> getAllSpreads() {
        return ResponseEntity.ok(marketDataService.getAllSpreadsAll());
    }

    @GetMapping("/{instrument}")
    public ResponseEntity<SpreadData> getSpread(@PathVariable String instrument) {
        return marketDataService.getSpread(instrument.toUpperCase())
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }
}