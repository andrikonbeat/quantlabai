package com.quantlab.jforex_bridge.controller;

import com.quantlab.jforex_bridge.dto.InstrumentData;
import com.quantlab.jforex_bridge.service.MarketDataService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Optional;

@RestController
@RequestMapping("/api/v1/instruments")
public class InstrumentController {

    private final MarketDataService marketDataService;

    @Autowired
    public InstrumentController(MarketDataService marketDataService) {
        this.marketDataService = marketDataService;
    }

    @GetMapping
    public ResponseEntity<List<InstrumentData>> getAllInstruments() {
        return ResponseEntity.ok(marketDataService.getAllInstruments());
    }

    @GetMapping("/{name}")
    public ResponseEntity<InstrumentData> getInstrument(@PathVariable String name) {
        return marketDataService.getInstrument(name.toUpperCase())
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }
}