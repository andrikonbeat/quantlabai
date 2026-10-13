package com.quantlab.jforex_bridge.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Financial instrument specification DTO.
 */
public class InstrumentData {
    private final String name;
    private final String description;
    private final String type;
    private final String primaryCurrency;
    private final String secondaryCurrency;
    private final double pipValue;
    private final int pipScale;
    private final int tickScale;
    private final double minTradeAmount;
    private final double tradeAmountIncrement;
    private final double amountPerContract;
    private final double leverage;
    private final String country;
    private final boolean exotic;
    private final String primaryJFCurrency;
    private final String secondaryJFCurrency;

    public InstrumentData(
        @JsonProperty("name") String name,
        @JsonProperty("description") String description,
        @JsonProperty("type") String type,
        @JsonProperty("primaryCurrency") String primaryCurrency,
        @JsonProperty("secondaryCurrency") String secondaryCurrency,
        @JsonProperty("pipValue") double pipValue,
        @JsonProperty("pipScale") int pipScale,
        @JsonProperty("tickScale") int tickScale,
        @JsonProperty("minTradeAmount") double minTradeAmount,
        @JsonProperty("tradeAmountIncrement") double tradeAmountIncrement,
        @JsonProperty("amountPerContract") double amountPerContract,
        @JsonProperty("leverage") double leverage,
        @JsonProperty("country") String country,
        @JsonProperty("exotic") boolean exotic,
        @JsonProperty("primaryJFCurrency") String primaryJFCurrency,
        @JsonProperty("secondaryJFCurrency") String secondaryJFCurrency
    ) {
        this.name = name;
        this.description = description;
        this.type = type;
        this.primaryCurrency = primaryCurrency;
        this.secondaryCurrency = secondaryCurrency;
        this.pipValue = pipValue;
        this.pipScale = pipScale;
        this.tickScale = tickScale;
        this.minTradeAmount = minTradeAmount;
        this.tradeAmountIncrement = tradeAmountIncrement;
        this.amountPerContract = amountPerContract;
        this.leverage = leverage;
        this.country = country;
        this.exotic = exotic;
        this.primaryJFCurrency = primaryJFCurrency;
        this.secondaryJFCurrency = secondaryJFCurrency;
    }

    public String getName() { return name; }
    public String getDescription() { return description; }
    public String getType() { return type; }
    public String getPrimaryCurrency() { return primaryCurrency; }
    public String getSecondaryCurrency() { return secondaryCurrency; }
    public double getPipValue() { return pipValue; }
    public int getPipScale() { return pipScale; }
    public int getTickScale() { return tickScale; }
    public double getMinTradeAmount() { return minTradeAmount; }
    public double getTradeAmountIncrement() { return tradeAmountIncrement; }
    public double getAmountPerContract() { return amountPerContract; }
    public double getLeverage() { return leverage; }
    public String getCountry() { return country; }
    public boolean isExotic() { return exotic; }
    public String getPrimaryJFCurrency() { return primaryJFCurrency; }
    public String getSecondaryJFCurrency() { return secondaryJFCurrency; }
}
