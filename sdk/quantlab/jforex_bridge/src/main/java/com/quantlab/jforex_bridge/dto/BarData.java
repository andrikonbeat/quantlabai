package com.quantlab.jforex_bridge.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;

/**
 * Bar data DTO.
 */
public class BarData {
    private final String instrument;
    private final String period;
    private final String side;
    private final long timestamp;
    private final double open;
    private final double high;
    private final double low;
    private final double close;
    private final double volume;

    public BarData(
        @JsonProperty("instrument") String instrument,
        @JsonProperty("period") String period,
        @JsonProperty("side") String side,
        @JsonProperty("timestamp") long timestamp,
        @JsonProperty("open") double open,
        @JsonProperty("high") double high,
        @JsonProperty("low") double low,
        @JsonProperty("close") double close,
        @JsonProperty("volume") double volume
    ) {
        this.instrument = instrument;
        this.period = period;
        this.side = side;
        this.timestamp = timestamp;
        this.open = open;
        this.high = high;
        this.low = low;
        this.close = close;
        this.volume = volume;
    }

    public String getInstrument() { return instrument; }
    public String getPeriod() { return period; }
    public String getSide() { return side; }
    public long getTimestamp() { return timestamp; }
    public double getOpen() { return open; }
    public double getHigh() { return high; }
    public double getLow() { return low; }
    public double getClose() { return close; }
    public double getVolume() { return volume; }

    public java.time.Instant getTimestampInstant() {
        return java.time.Instant.ofEpochMilli(timestamp);
    }
}
