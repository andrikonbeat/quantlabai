package com.quantlab.jforex_bridge.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;

/**
 * Swap data DTO.
 */
public class SwapData {
    private final String instrument;
    private final double longSwap;
    private final double shortSwap;
    private final double longSwapPips;
    private final double shortSwapPips;
    private final long rolloverTime;
    private final List<Integer> tripleSwapDays;

    public SwapData(
        @JsonProperty("instrument") String instrument,
        @JsonProperty("longSwap") double longSwap,
        @JsonProperty("shortSwap") double shortSwap,
        @JsonProperty("longSwapPips") double longSwapPips,
        @JsonProperty("shortSwapPips") double shortSwapPips,
        @JsonProperty("rolloverTime") long rolloverTime,
        @JsonProperty("tripleSwapDays") List<Integer> tripleSwapDays
    ) {
        this.instrument = instrument;
        this.longSwap = longSwap;
        this.shortSwap = shortSwap;
        this.longSwapPips = longSwapPips;
        this.shortSwapPips = shortSwapPips;
        this.rolloverTime = rolloverTime;
        this.tripleSwapDays = tripleSwapDays;
    }

    public String getInstrument() { return instrument; }
    public double getLongSwap() { return longSwap; }
    public double getShortSwap() { return shortSwap; }
    public double getLongSwapPips() { return longSwapPips; }
    public double getShortSwapPips() { return shortSwapPips; }
    public long getRolloverTime() { return rolloverTime; }
    public List<Integer> getTripleSwapDays() { return tripleSwapDays; }

    public java.time.Instant getRolloverTimeInstant() {
        return java.time.Instant.ofEpochMilli(rolloverTime);
    }
}
