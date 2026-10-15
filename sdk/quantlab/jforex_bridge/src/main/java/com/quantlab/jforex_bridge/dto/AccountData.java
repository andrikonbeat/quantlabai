package com.quantlab.jforex_bridge.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;

/**
 * Account data DTO.
 */
public class AccountData {
    private final String accountId;
    private final String currency;
    private final double equity;
    private final double balance;
    private final double leverage;
    private final double usedMargin;
    private final double freeMargin;
    private final int marginCutLevel;
    private final String state;
    private final boolean connected;

    public AccountData(
        @JsonProperty("accountId") String accountId,
        @JsonProperty("currency") String currency,
        @JsonProperty("equity") double equity,
        @JsonProperty("balance") double balance,
        @JsonProperty("leverage") double leverage,
        @JsonProperty("usedMargin") double usedMargin,
        @JsonProperty("freeMargin") double freeMargin,
        @JsonProperty("marginCutLevel") int marginCutLevel,
        @JsonProperty("state") String state,
        @JsonProperty("connected") boolean connected
    ) {
        this.accountId = accountId;
        this.currency = currency;
        this.equity = equity;
        this.balance = balance;
        this.leverage = leverage;
        this.usedMargin = usedMargin;
        this.freeMargin = freeMargin;
        this.marginCutLevel = marginCutLevel;
        this.state = state;
        this.connected = connected;
    }

    public String getAccountId() { return accountId; }
    public String getCurrency() { return currency; }
    public double getEquity() { return equity; }
    public double getBalance() { return balance; }
    public double getLeverage() { return leverage; }
    public double getUsedMargin() { return usedMargin; }
    public double getFreeMargin() { return freeMargin; }
    public int getMarginCutLevel() { return marginCutLevel; }
    public String getState() { return state; }
    public boolean isConnected() { return connected; }

    public java.time.Instant getTimestamp() {
        return java.time.Instant.now();
    }
}
