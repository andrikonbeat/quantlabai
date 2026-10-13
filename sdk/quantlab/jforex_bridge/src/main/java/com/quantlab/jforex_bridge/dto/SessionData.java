package com.quantlab.jforex_bridge.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;
import java.util.Map;

/**
 * Trading session data DTO.
 */
public class SessionData {
    private final String name;
    private final String instrument;
    private final String timezone;
    private final Map<String, List<TradingHour>> tradingHours;
    private final List<Holiday> holidays;

    public SessionData(
        @JsonProperty("name") String name,
        @JsonProperty("instrument") String instrument,
        @JsonProperty("timezone") String timezone,
        @JsonProperty("tradingHours") Map<String, List<TradingHour>> tradingHours,
        @JsonProperty("holidays") List<Holiday> holidays
    ) {
        this.name = name;
        this.instrument = instrument;
        this.timezone = timezone;
        this.tradingHours = tradingHours;
        this.holidays = holidays;
    }

    public String getName() { return name; }
    public String getInstrument() { return instrument; }
    public String getTimezone() { return timezone; }
    public Map<String, List<TradingHour>> getTradingHours() { return tradingHours; }
    public List<Holiday> getHolidays() { return holidays; }

    public static class TradingHour {
        private final String open;
        private final String close;

        public TradingHour(
            @JsonProperty("open") String open,
            @JsonProperty("close") String close
        ) {
            this.open = open;
            this.close = close;
        }

        public String getOpen() { return open; }
        public String getClose() { return close; }
    }

    public static class Holiday {
        private final String date;
        private final String description;

        public Holiday(
            @JsonProperty("date") String date,
            @JsonProperty("description") String description
        ) {
            this.date = date;
            this.description = description;
        }

        public String getDate() { return date; }
        public String getDescription() { return description; }
    }
}
