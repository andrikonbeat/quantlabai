package com.quantlab.jforex_bridge.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;

/**
 * Tick data DTO.
 */
public class TickData {
    private final String instrument;
    private final long timestamp;
    private final double bid;
    private final double ask;
    private final double bidVolume;
    private final double askVolume;

    public TickData(
        @JsonProperty("instrument") String instrument,
        @JsonProperty("timestamp") long timestamp,
        @JsonProperty("bid") double bid,
        @JsonProperty("ask") double ask,
        @JsonProperty("bidVolume") double bidVolume,
        @JsonProperty("askVolume") double askVolume
    ) {
        this.instrument = instrument;
        this.timestamp = timestamp;
        this.bid = bid;
        this.ask = ask;
        this.bidVolume = bidVolume;
        this.askVolume = askVolume;
    }

    public String getInstrument() { return instrument; }
    public long getTimestamp() { return timestamp; }
    public double getBid() { return bid; }
    public double getAsk() { return ask; }
    public double getBidVolume() { return bidVolume; }
    public double getAskVolume() { return askVolume; }

    public java.time.Instant getTimestampInstant() {
        return java.time.Instant.ofEpochMilli(timestamp);
    }
}
