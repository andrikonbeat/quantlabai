package com.quantlab.strategies;

import com.dukascopy.api.*;
import com.dukascopy.api.IEngine.OrderCommand;
import com.dukascopy.api.system.IClient;

import java.io.BufferedWriter;
import java.io.FileWriter;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;
import java.util.logging.Logger;

/**
 * QuantLab Portfolio 100 USD - JForex Strategy Template
 * 
 * Portfolio: 100 USD | Lote: 0.01 | Timeframe: M15
 * Instrumentos: EUR/USD, USD/CHF, AUD/USD (solo 1 operación simultánea)
 * Riesgo: 1.5-2.5% por trade ($1.50-$2.50) → SL 12-22 pips
 * Timeframe: M15 | Lote fijo: 0.01 | 1 trade a la vez
 * 
 * Configuration via system properties:
 * - quantlab.state_dir: Directory for output files (default: ~/JForex4/state)
 * - quantlab.instrument: Active instrument (EUR/USD, USD/CHF, AUD/USD)
 * - quantlab.lot_size: Position size (default: 0.01)
 * - quantlab.max_positions: Max concurrent positions (default: 1)
 * - quantlab.write_interval_ms: State write interval (default: 5000)
 * - quantlab.sl_pips: Stop Loss in pips (default: 20)
 * - quantlab.tp_pips: Take Profit in pips (default: 30)
 * - quantlab.atr_period: ATR period for dynamic SL/TP (default: 14)
 * - quantlab.atr_multiplier_sl: ATR multiplier for SL (default: 1.5)
 * - quantlab.atr_multiplier_tp: ATR multiplier for TP (default: 2.0)
 * - quantlab.session_filter: Filter by trading session (true/false, default: true)
 */
public class QuantLabPortfolio100USD implements IStrategy {

    private static final Logger LOG = Logger.getLogger(QuantLabPortfolio100USD.class.getName());

    // ── Portfolio Parameters ────────────────────────────────────────────────
    private static final double ACCOUNT_SIZE = 100.0;
    private static final double BASE_LOT_SIZE = 0.01;
    private static final int MAX_CONCURRENT_POSITIONS = 1;
    private static final double RISK_PER_TRADE_PCT = 2.0; // 2% per trade
    private static final int TIMEFRAME_MINUTES = 15; // M15

    // ── Default Parameters (overridable via system properties) ──────────────
    private String stateDirPath = System.getProperty("user.home") + "/JForex4/state";
    private Instrument[] instruments = {Instrument.EURUSD, Instrument.USDCHF, Instrument.AUDUSD};
    private int activeInstrumentIndex = 0; // 0=EURUSD, 1=USDCHF, 2=AUDUSD
    private double lotSize = 0.01;
    private int maxPositions = 1;
    private long writeIntervalMs = 5000;
    private int slPips = 20;
    private int tpPips = 30;
    private int atrPeriod = 14;
    private double atrMultiplierSL = 1.5;
    private double atrMultiplierTP = 2.0;
    private boolean sessionFilter = true;

    // ── Runtime ─────────────────────────────────────────────────────────────
    private IContext context;
    private IEngine engine;
    private IAccount account;
    private IHistory history;
    private Path stateDir;
    private AtomicLong lastWriteTime = new AtomicLong(0);
    
    // State tracking
    private final Map<String, OrderState> orderStates = new ConcurrentHashMap<>();
    private final List<EquityPoint> equityHistory = Collections.synchronizedList(new ArrayList<>());
    private double lastEquity = 0.0;
    private long strategyStartTime = System.currentTimeMillis();
    private Instrument currentInstrument;

    @Override
    public void onStart(IContext ctx) throws JFException {
        this.context = ctx;
        this.engine = ctx.getEngine();
        this.account = ctx.getAccount();
        this.history = ctx.getHistory();
        
        loadParameters();
        
        // Set current instrument
        this.currentInstrument = instruments[activeInstrumentIndex];
        
        this.stateDir = Paths.get(stateDirPath);
        try {
            Files.createDirectories(stateDir);
        } catch (IOException e) {
            LOG.severe("Failed to create state directory: " + e.getMessage());
        }
        
        // Subscribe to all instruments for monitoring
        Set<Instrument> subInstruments = new HashSet<>(Arrays.asList(instruments));
        context.setSubscribedInstruments(subInstruments, true);
        
        writeStateFiles();
        
        LOG.info("=== QuantLab Portfolio 100 USD Started ===");
        LOG.info("Account: 100.0 USD | Lot: " + lotSize + " | Max Pos: " + maxPositions);
        LOG.info("Active Instrument: " + currentInstrument + " | SL: " + slPips + " pips | TP: " + tpPips + " pips");
        LOG.info("State Dir: " + stateDir);
    }

    private void loadParameters() {
        String prop;
        
        prop = System.getProperty("quantlab.state_dir");
        if (prop != null) this.stateDirPath = prop;
        
        prop = System.getProperty("quantlab.instrument");
        if (prop != null) {
            Instrument inst = Instrument.fromString(prop);
            for (int i = 0; i < instruments.length; i++) {
                if (instruments[i].equals(inst)) {
                    activeInstrumentIndex = i;
                    break;
                }
            }
        }
        
        prop = System.getProperty("quantlab.lot_size");
        if (prop != null) this.lotSize = Double.parseDouble(prop);
        
        prop = System.getProperty("quantlab.max_positions");
        if (prop != null) this.maxPositions = Integer.parseInt(prop);
        
        prop = System.getProperty("quantlab.write_interval_ms");
        if (prop != null) this.writeIntervalMs = Long.parseLong(prop);
        
        prop = System.getProperty("quantlab.sl_pips");
        if (prop != null) this.slPips = Integer.parseInt(prop);
        
        prop = System.getProperty("quantlab.tp_pips");
        if (prop != null) this.tpPips = Integer.parseInt(prop);
        
        prop = System.getProperty("quantlab.atr_period");
        if (prop != null) this.atrPeriod = Integer.parseInt(prop);
        
        prop = System.getProperty("quantlab.atr_multiplier_sl");
        if (prop != null) this.atrMultiplierSL = Double.parseDouble(prop);
        
        prop = System.getProperty("quantlab.atr_multiplier_tp");
        if (prop != null) this.atrMultiplierTP = Double.parseDouble(prop);
        
        prop = System.getProperty("quantlab.session_filter");
        if (prop != null) this.sessionFilter = Boolean.parseBoolean(prop);
        
        this.currentInstrument = instruments[activeInstrumentIndex];
    }

    @Override
    public void onTick(Instrument instrument, ITick tick) throws JFException {
        if (!currentInstrument.equals(instrument)) return;
        
        double midPrice = (tick.getAsk() + tick.getBid()) / 2.0;
        updateEquity(midPrice);
        maybeWriteState();
    }

    @Override
    public void onBar(Instrument instrument, Period period, IBar askBar, IBar bidBar) throws JFException {
        if (!currentInstrument.equals(instrument)) return;
        if (period != Period.FIFTEEN_MINS) return;
        
        // ── SESSION FILTER ──────────────────────────────────────────────────
        if (sessionFilter && !isActiveSession()) return;
        
        // ── CHECK MAX POSITIONS ─────────────────────────────────────────────
        if (getOpenPositionsCount() >= maxPositions) return;
        
        // ── ATR-BASED SL/TP CALCULATION ─────────────────────────────────────
        double atr = calculateATR(atrPeriod);
        double dynamicSL = atr * atrMultiplierSL;
        double dynamicTP = atr * atrMultiplierTP;
        
        // Cap SL/TP to reasonable bounds (10-30 pips for M15 on 100 USD account)
        double minSL = 10, maxSL = 30;
        double minTP = 15, maxTP = 50;
        dynamicSL = Math.max(minSL, Math.min(maxSL, dynamicSL));
        dynamicTP = Math.max(minTP, Math.min(maxTP, dynamicTP));
        
        // ── ENTRY SIGNAL: Simple RSI Reversal ───────────────────────────────
        double rsi = calculateRSI(14);
        double midPrice = (askBar.getClose() + bidBar.getClose()) / 2.0;
        
        boolean longSignal = rsi < 30 && midPrice > bidBar.getLow();
        boolean shortSignal = rsi > 70 && midPrice < askBar.getHigh();
        
        if (longSignal) {
            enterLong(dynamicSL, dynamicTP);
        } else if (shortSignal) {
            enterShort(dynamicSL, dynamicTP);
        }
    }

    private boolean isActiveSession() {
        // London (08:00-16:00 UTC) + New York (13:00-21:00 UTC) overlap
        Calendar cal = Calendar.getInstance(TimeZone.getTimeZone("UTC"));
        int hour = cal.get(Calendar.HOUR_OF_DAY);
        int day = cal.get(Calendar.DAY_OF_WEEK);
        
        // Skip weekends
        if (day == Calendar.SATURDAY || day == Calendar.SUNDAY) return false;
        
        // London-NY overlap (13:00-16:00 UTC) is best, but allow full London+NY
        return hour >= 8 && hour <= 21;
    }

    private double calculateATR(int period) throws JFException {
        double sum = 0;
        int count = 0;
        
        for (int i = 1; i <= period; i++) {
            IBar askBar = history.getBar(currentInstrument, Period.FIFTEEN_MINS, OfferSide.ASK, i);
            IBar bidBar = history.getBar(currentInstrument, Period.FIFTEEN_MINS, OfferSide.BID, i);
            if (askBar == null || bidBar == null) continue;
            
            double high = Math.max(askBar.getHigh(), bidBar.getHigh());
            double low = Math.min(askBar.getLow(), bidBar.getLow());
            sum += high - low;
            count++;
        }
        
        return count > 0 ? sum / count : 0.0015; // fallback ~15 pips
    }

    private double calculateRSI(int period) throws JFException {
        double gains = 0, losses = 0;
        double prevClose = -1;
        int count = 0;
        
        for (int i = period; i >= 1; i--) {
            IBar askBar = history.getBar(currentInstrument, Period.FIFTEEN_MINS, OfferSide.ASK, i);
            IBar bidBar = history.getBar(currentInstrument, Period.FIFTEEN_MINS, OfferSide.BID, i);
            if (askBar == null || bidBar == null) continue;
            
            double close = (askBar.getClose() + bidBar.getClose()) / 2.0;
            if (prevClose > 0) {
                double change = close - prevClose;
                if (change > 0) gains += change;
                else losses -= change;
                count++;
            }
            prevClose = close;
        }
        
        if (count == 0 || losses == 0) return 50.0;
        double rs = gains / losses;
        return 100 - (100 / (1 + rs));
    }

    private int getOpenPositionsCount() throws JFException {
        int count = 0;
        for (IOrder order : engine.getOrders()) {
            if (order.getState() == IOrder.State.FILLED && order.getInstrument().equals(currentInstrument)) {
                count++;
            }
        }
        return count;
    }

    private void enterLong(double slPips, double tpPips) throws JFException {
        double price = history.getLastTick(currentInstrument).getBid();
        double sl = price - (slPips * currentInstrument.getPipValue());
        double tp = price + (tpPips * currentInstrument.getPipValue());
        
        IOrder order = engine.submitOrder(
            "LONG_" + System.currentTimeMillis(),
            currentInstrument, OrderCommand.BUY, lotSize,
            price, 1, sl, tp
        );
        order.waitForUpdate(2000);
        
        LOG.info(String.format("LONG %s @ %.5f | SL: %.5f (%.1f pips) | TP: %.5f (%.1f pips)",
            currentInstrument, price, sl, slPips, tp, tpPips));
    }

    private void enterShort(double slPips, double tpPips) throws JFException {
        double price = history.getLastTick(currentInstrument).getAsk();
        double sl = price + (slPips * currentInstrument.getPipValue());
        double tp = price - (tpPips * currentInstrument.getPipValue());
        
        IOrder order = engine.submitOrder(
            "SHORT_" + System.currentTimeMillis(),
            currentInstrument, OrderCommand.SELL, lotSize,
            price, 1, sl, tp
        );
        order.waitForUpdate(2000);
        
        LOG.info(String.format("SHORT %s @ %.5f | SL: %.5f (%.1f pips) | TP: %.5f (%.1f pips)",
            currentInstrument, price, sl, slPips, tp, tpPips));
    }

    @Override
    public void onMessage(IMessage message) throws JFException {
        IMessage.Type type = message.getType();
        
        if (type == IMessage.Type.ORDER_SUBMIT_OK) {
            IOrder order = message.getOrder();
            orderStates.put(order.getLabel(), new OrderState(order));
            LOG.info("Order submitted: " + order.getLabel() + " " + order.getInstrument());
        } else if (type == IMessage.Type.ORDER_FILL_OK) {
            IOrder order = message.getOrder();
            OrderState state = orderStates.get(order.getLabel());
            if (state != null) {
                state.filled = true;
                state.fillPrice = order.getOpenPrice();
                state.fillTime = message.getCreationTime();
            }
            LOG.info("Order filled: " + order.getLabel() + " @ " + order.getOpenPrice());
        } else if (type == IMessage.Type.ORDER_CLOSE_OK) {
            IOrder order = message.getOrder();
            OrderState state = orderStates.remove(order.getLabel());
            if (state != null) {
                state.closed = true;
                state.closePrice = order.getClosePrice();
                state.closeTime = message.getCreationTime();
                state.profitLoss = order.getProfitLossInUSD();
            }
            LOG.info("Order closed: " + order.getLabel() + " PL: $" + order.getProfitLossInUSD());
        } else if (type == IMessage.Type.ORDER_SUBMIT_REJECTED || type == IMessage.Type.ORDER_CLOSE_REJECTED) {
            LOG.warning("Order rejected: " + message.getContent());
        }
        maybeWriteState();
    }

    @Override
    public void onAccount(IAccount account) throws JFException {
        this.lastEquity = account.getEquity();
        equityHistory.add(new EquityPoint(System.currentTimeMillis(), lastEquity));
        if (equityHistory.size() > 10000) equityHistory.remove(0);
        maybeWriteState();
    }

    @Override
    public void onStop() throws JFException {
        LOG.info("=== QuantLab Portfolio 100 USD Stopping ===");
        writeStateFiles();
    }

    // ── State Export ────────────────────────────────────────────────────────

    private void updateEquity(double midPrice) {
        double unrealizedPl = 0.0;
        try {
            for (IOrder order : engine.getOrders()) {
                if (order.getState() == IOrder.State.FILLED && order.getInstrument().equals(currentInstrument)) {
                    double pipValue = currentInstrument.getPipValue();
                    double priceDiff = order.isLong() ? (midPrice - order.getOpenPrice()) : (order.getOpenPrice() - midPrice);
                    unrealizedPl += priceDiff * order.getAmount() / pipValue;
                }
            }
        } catch (JFException e) {
            LOG.warning("Error calculating unrealized PL: " + e.getMessage());
        }
        
        double equity = account.getBalance() + unrealizedPl;
        this.lastEquity = equity;
        equityHistory.add(new EquityPoint(System.currentTimeMillis(), equity));
        if (equityHistory.size() > 10000) equityHistory.remove(0);
    }

    private void maybeWriteState() {
        long now = System.currentTimeMillis();
        if (now - lastWriteTime.get() >= writeIntervalMs) {
            writeStateFiles();
            lastWriteTime.set(now);
        }
    }

    private void writeStateFiles() {
        writeEquityJson();
        writeOrdersJson();
        writeHealthTxt();
        writeLatencyTxt();
        writeSlippageTxt();
        writeConnectionJson();
    }

    private void writeEquityJson() {
        Path file = stateDir.resolve("equity.json");
        try (BufferedWriter writer = new BufferedWriter(new FileWriter(file.toFile()))) {
            writer.write("[");
            for (int i = 0; i < equityHistory.size(); i++) {
                EquityPoint p = equityHistory.get(i);
                writer.write(String.format("{\"timestamp\":%d,\"equity\":%.2f}", p.timestamp, p.equity));
                if (i < equityHistory.size() - 1) writer.write(",");
            }
            writer.write("]");
        } catch (IOException e) {
            LOG.warning("Failed to write equity.json: " + e.getMessage());
        }
    }

    private void writeOrdersJson() {
        Path file = stateDir.resolve("orders.json");
        try (BufferedWriter writer = new BufferedWriter(new FileWriter(file.toFile()))) {
            writer.write("[");
            List<IOrder> orders = new ArrayList<>();
            try {
                orders = new ArrayList<>(engine.getOrders());
            } catch (JFException e) {
                orders = new ArrayList<>();
            }
            
            for (int i = 0; i < orders.size(); i++) {
                IOrder o = orders.get(i);
                OrderState state = orderStates.get(o.getLabel());
                
                writer.write("{");
                writer.write(String.format("\"label\":\"%s\",", o.getLabel()));
                writer.write(String.format("\"instrument\":\"%s\",", o.getInstrument()));
                writer.write(String.format("\"side\":\"%s\",", o.isLong() ? "long" : "short"));
                writer.write(String.format("\"amount\":%.4f,", o.getAmount()));
                writer.write(String.format("\"open_price\":%.5f,", o.getOpenPrice()));
                writer.write(String.format("\"state\":\"%s\",", o.getState()));
                writer.write(String.format("\"creation_time\":%d,", o.getCreationTime()));
                
                if (state != null && state.filled) {
                    writer.write(String.format("\"fill_price\":%.5f,", state.fillPrice));
                    writer.write(String.format("\"fill_time\":%d,", state.fillTime));
                }
                if (state != null && state.closed) {
                    writer.write(String.format("\"close_price\":%.5f,", state.closePrice));
                    writer.write(String.format("\"close_time\":%d,", state.closeTime));
                    writer.write(String.format("\"profit_loss\":%.2f,", state.profitLoss));
                }
                
                writer.write("}");
                if (i < orders.size() - 1) writer.write(",");
            }
            writer.write("]");
        } catch (IOException e) {
            LOG.warning("Failed to write orders.json: " + e.getMessage());
        }
    }

    private void writeHealthTxt() {
        Path file = stateDir.resolve("health.txt");
        try {
            double health = calculateHealthScore();
            Files.writeString(file, String.format("%.4f", health));
        } catch (IOException e) {
            LOG.warning("Failed to write health.txt: " + e.getMessage());
        }
    }

    private void writeLatencyTxt() {
        Path file = stateDir.resolve("latency.txt");
        try {
            long latency = 0;
            long serverTime = context.getTime();
            long localTime = System.currentTimeMillis();
            latency = Math.abs(localTime - serverTime);
            Files.writeString(file, String.valueOf(latency));
        } catch (IOException e) {
            LOG.warning("Failed to write latency.txt: " + e.getMessage());
        }
    }

    private void writeSlippageTxt() {
        Path file = stateDir.resolve("slippage.txt");
        try {
            double totalSlippage = 0.0;
            int count = 0;
            for (OrderState state : orderStates.values()) {
                if (state.filled && state.expectedPrice > 0) {
                    totalSlippage += Math.abs(state.fillPrice - state.expectedPrice);
                    count++;
                }
            }
            double avgSlippage = count > 0 ? totalSlippage / count : 0.0;
            Files.writeString(file, String.format("%.2f", avgSlippage));
        } catch (IOException e) {
            LOG.warning("Failed to write slippage.txt: " + e.getMessage());
        }
    }

    private void writeConnectionJson() {
        Path file = stateDir.resolve("connection.json");
        try (BufferedWriter writer = new BufferedWriter(new FileWriter(file.toFile()))) {
            boolean connectedBool = account != null && account.isConnected();
            long serverTime = context.getTime();
            writer.write(String.format("{\"connected\":%b,\"server_time\":%d,\"uptime_ms\":%d}",
                connectedBool, serverTime, System.currentTimeMillis() - strategyStartTime));
        } catch (IOException e) {
            LOG.warning("Failed to write connection.json: " + e.getMessage());
        }
    }

    private double calculateHealthScore() {
        double score = 1.0;
        if (account == null || !account.isConnected()) score -= 0.5;
        
        long serverTime = context.getTime();
        long latency = Math.abs(System.currentTimeMillis() - serverTime);
        if (latency > 500) score -= 0.2;
        if (latency > 2000) score -= 0.3;
        
        if (account.getEquity() > 0 && account.getUsedMargin() > 0) {
            double marginLevel = (account.getEquity() / account.getUsedMargin()) * 100;
            if (marginLevel < 200) score -= 0.3;
            if (marginLevel < 100) score -= 0.5;
        }
        return Math.max(0.0, Math.min(1.0, score));
    }

    // ── Helper Classes ────────────────────────────────────────────────────────

    private static class EquityPoint {
        final long timestamp;
        final double equity;
        EquityPoint(long timestamp, double equity) {
            this.timestamp = timestamp;
            this.equity = equity;
        }
    }

    private static class OrderState {
        final String label;
        final Instrument instrument;
        final double amount;
        final double expectedPrice;
        boolean filled = false;
        double fillPrice = 0;
        long fillTime = 0;
        boolean closed = false;
        double closePrice = 0;
        long closeTime = 0;
        double profitLoss = 0;

        OrderState(IOrder order) {
            this.label = order.getLabel();
            this.instrument = order.getInstrument();
            this.amount = order.getAmount();
            this.expectedPrice = order.getOpenPrice();
        }
    }
}
