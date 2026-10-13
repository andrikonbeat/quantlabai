package com.quantlab.jforex_bridge.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;

/**
 * Spread data DTO.
 */
public class SpreadData {
    private final String instrument;
    private final double bid;
    private final double ask;
    private final double spreadPips;
    private final long timestamp;

    public SpreadData(
        @JsonProperty("instrument") String instrument,
        @JsonProperty("bid") double bid,
        @JsonProperty("ask") double ask,
        @JsonProperty("spreadPips") double spreadPips,
        @JsonProperty("timestamp") long timestamp
    ) {
        this.instrument = instrument;
        this.bid = bid;
        this.ask = ask;
        this.spreadPips = spreadPips;
        this.timestamp = timestamp;
    }

    public String getInstrument() { return instrument; }
    public double getBid() { return bid; }
    public double getAsk() { return ask; }
    public double getSpreadPips() { return spreadPips; }
    public long getTimestamp() { return timestamp; }

    public java.time.Instant getTimestampInstant() {
        return java.time.Instant.ofEpochMilli(timestamp);
    }
}
