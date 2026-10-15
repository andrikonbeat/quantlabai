package com.quantlab.jforex_bridge.controller;

import com.quantlab.jforex_bridge.dto.SwapData;
import com.quantlab.jforex_bridge.service.MarketDataService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Optional;

@RestController
@RequestMapping("/api/v1/swaps")
public class SwapController {

    private final MarketDataService marketDataService;

    @Autowired
    public SwapController(MarketDataService marketDataService) {
        this.marketDataService = marketDataService;
    }

    @GetMapping
    public ResponseEntity<List<SwapData>> getAllSwaps() {
        return ResponseEntity.ok(marketDataService.getAllSwaps());
    }

    @GetMapping("/{instrument}")
    public ResponseEntity<SwapData> getSwap(@PathVariable String instrument) {
        return marketDataService.getSwap(instrument.toUpperCase())
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }
}