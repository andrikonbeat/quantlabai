package com.quantlab.jforex_bridge.service;

import com.dukascopy.api.*;
import com.dukascopy.api.instrument.IFinancialInstrument;
import com.dukascopy.api.instrument.IFinancialInstrumentProvider;
import com.quantlab.jforex_bridge.client.JForexClientManager;
import com.quantlab.jforex_bridge.dto.*;
import com.quantlab.jforex_bridge.websocket.MarketDataWebSocketController;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Collectors;

/**
 * Service for collecting and serving market data from JForex.
 * This service is initialized with an IContext from the JForexStrategy.
 */
@Service
public class MarketDataService {

    private static final Logger log = LoggerFactory.getLogger(MarketDataService.class);

    private final MarketDataWebSocketController wsController;
    private final Map<String, TickData> latestTicks = new ConcurrentHashMap<>();
    private final Map<String, BarData> latestBars = new ConcurrentHashMap<>();
    private final Map<String, SpreadData> latestSpreads = new ConcurrentHashMap<>();
    private final Map<String, InstrumentData> instruments = new ConcurrentHashMap<>();
    private final Map<String, SwapData> swaps = new ConcurrentHashMap<>();
    private final Map<String, SessionData> sessions = new ConcurrentHashMap<>();
    private volatile AccountData accountData;
    private volatile AccountData latestAccountData;

    private IContext context;

    @Autowired
    public MarketDataService(MarketDataWebSocketController wsController) {
        this.wsController = wsController;
    }

    /**
     * Initialize with IContext from JForexStrategy.onStart().
     * This must be called after the strategy's onStart() is called.
     */
    public void initialize(IContext context) {
        this.context = context;
        log.info("MarketDataService initialized with IContext");
        try {
            loadInstruments();
            loadSwaps();
            loadSessions();
        } catch (Exception e) {
            log.error("Failed to load initial market data: {}", e.getMessage(), e);
        }
    }

    // Tick handling
    public void onTick(TickData tick) {
        latestTicks.put(tick.getInstrument(), tick);
        // Calculate spread
        double spreadPips = (tick.getAsk() - tick.getBid()) * Math.pow(10, getPipScale(tick.getInstrument()));
        SpreadData spread = new SpreadData(
            tick.getInstrument(),
            tick.getBid(),
            tick.getAsk(),
            spreadPips,
            tick.getTimestamp()
        );
        latestSpreads.put(tick.getInstrument(), spread);

        // Broadcast via WebSocket
        wsController.broadcastTick(tick);
    }

    public void onBar(BarData bar) {
        String key = bar.getInstrument() + "_" + bar.getPeriod() + "_" + bar.getSide();
        latestBars.put(key, bar);

        // Broadcast via WebSocket
        wsController.broadcastBar(bar);
    }

    public void onAccount(AccountData account) {
        this.latestAccountData = account;

        // Broadcast via WebSocket
        wsController.broadcastAccount(account);
    }

    // Data loading
    private void loadInstruments() {
        if (context == null) return;

        try {
            IFinancialInstrumentProvider provider = context.getFinancialInstrumentProvider();
            if (provider == null) {
                log.warn("Financial instrument provider not available");
                return;
            }

            Set<IFinancialInstrument> allInstruments = provider.getFinancialInstruments();
            if (allInstruments == null || allInstruments.isEmpty()) {
                log.warn("No financial instruments available");
                return;
            }

            for (IFinancialInstrument finInst : allInstruments) {
                InstrumentData data = new InstrumentData(
                    finInst.getName(),
                    finInst.getDescription(),
                    finInst.getType().name(),
                    finInst.getPrimaryCurrency().getCurrencyCode(),
                    finInst.getSecondaryCurrency().getCurrencyCode(),
                    finInst.getPipValue(),
                    finInst.getPipScale(),
                    finInst.getTickScale(),
                    finInst.getMinTradeAmount(),
                    finInst.getTradeAmountIncrement(),
                    finInst.getAmountPerContract(),
                    finInst.getLeverageUse(),
                    finInst.getCountry(),
                    finInst.isExotic(),
                    finInst.getPrimaryJFCurrency().getCurrencyCode(),
                    finInst.getSecondaryJFCurrency().getCurrencyCode()
                );
                instruments.put(finInst.getName(), data);
            }
            log.info("Loaded {} instruments", instruments.size());
        } catch (Exception e) {
            log.warn("Failed to load instruments: {}", e.getMessage());
        }
    }

    private void loadSwaps() {
        // Note: JForex API doesn't expose swap rates directly through IDataService.
        // Swap rates are typically available through the instrument or account.
        // For now, we'll use placeholder values. Real implementation would need
        // to access swap data from the JForex platform's instrument properties.
        try {
            if (context == null) return;
            for (Instrument instrument : context.getSubscribedInstruments()) {
                // Placeholder values - real implementation would access JForex instrument properties
                SwapData swap = new SwapData(
                    instrument.name(),
                    0.0, // longSwap
                    0.0, // shortSwap
                    0.0, // longSwapPips
                    0.0, // shortSwapPips
                    System.currentTimeMillis(),
                    List.of(3) // Wednesday = triple swap
                );
                swaps.put(instrument.name(), swap);
            }
            log.info("Loaded swaps for {} instruments (placeholder values)", swaps.size());
        } catch (Exception e) {
            log.warn("Failed to load swaps: {}", e.getMessage());
        }
    }

    private void loadSessions() {
        if (context == null) return;

        try {
            IDataService dataService = context.getDataService();
            for (Instrument instrument : context.getSubscribedInstruments()) {
                // Get trading sessions for instrument
                ITimeDomain timeDomain = dataService.getOfflineTimeDomain(instrument);
                if (timeDomain != null) {
                    SessionData session = new SessionData(
                        instrument.name(),
                        instrument.name(),
                        "UTC", // ITimeDomain doesn't expose timezone directly
                        Map.of(), // Trading hours would need parsing
                        List.of()
                    );
                    sessions.put(instrument.name(), session);
                }
            }
            log.info("Loaded sessions for {} instruments", sessions.size());
        } catch (Exception e) {
            log.warn("Failed to load sessions: {}", e.getMessage());
        }
    }

    // Getters for REST endpoints
    public List<InstrumentData> getAllInstruments() {
        return new ArrayList<>(instruments.values());
    }

    public Optional<InstrumentData> getInstrument(String name) {
        return Optional.ofNullable(instruments.get(name));
    }

    public List<SwapData> getAllSwaps() {
        return new ArrayList<>(swaps.values());
    }

    public Optional<SwapData> getSwap(String instrument) {
        return Optional.ofNullable(swaps.get(instrument));
    }

    public List<SpreadData> getAllSpreads() {
        return new ArrayList<>(latestSpreads.values());
    }

    public Optional<SpreadData> getSpread(String instrument) {
        return Optional.ofNullable(latestSpreads.get(instrument));
    }

    public List<BarData> getBars(String instrument, String period, String side) {
        String prefix = instrument + "_" + period + "_" + side;
        return latestBars.entrySet().stream()
            .filter(e -> e.getKey().startsWith(prefix))
            .map(Map.Entry::getValue)
            .collect(Collectors.toList());
    }

    public Optional<TickData> getLatestTick(String instrument) {
        return Optional.ofNullable(latestTicks.get(instrument));
    }

    public List<SessionData> getAllSessions() {
        return new ArrayList<>(sessions.values());
    }

    public Optional<SessionData> getSession(String instrument) {
        return Optional.ofNullable(sessions.get(instrument));
    }

    public AccountData getAccountData() {
        return latestAccountData;
    }

    public List<TickData> getAllTicks() {
        return new ArrayList<>(latestTicks.values());
    }

    public List<BarData> getAllBars() {
        return new ArrayList<>(latestBars.values());
    }

    public List<SpreadData> getAllSpreadsAll() {
        return new ArrayList<>(latestSpreads.values());
    }

    private int getPipScale(String instrumentName) {
        InstrumentData inst = instruments.get(instrumentName);
        return inst != null ? inst.getPipScale() : 4;
    }
}
