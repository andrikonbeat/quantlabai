package com.quantlab.jforex_bridge.controller;

import com.quantlab.jforex_bridge.dto.AccountData;
import com.quantlab.jforex_bridge.service.MarketDataService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Optional;

@RestController
@RequestMapping("/api/v1/account")
public class AccountController {

    private final MarketDataService marketDataService;

    @Autowired
    public AccountController(MarketDataService marketDataService) {
        this.marketDataService = marketDataService;
    }

    @GetMapping
    public ResponseEntity<AccountData> getAccount() {
        AccountData account = marketDataService.getAccountData();
        return account != null 
            ? ResponseEntity.ok(account)
            : ResponseEntity.notFound().build();
    }
}