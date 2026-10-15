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
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;
import java.util.logging.Logger;

/**
 * QuantLab JForex Strategy Template - Compatible with Java 11 / JForex SDK 2.13.99
 * 
 * This strategy exports equity, orders, and health metrics to JSON files
 * in the JForex state directory for QuantLab's LiveFeed and BrokerAdapter.
 * 
 * Configuration via system properties:
 * - quantlab.state_dir: Directory for output files (default: ~/JForex4/state)
 * - quantlab.instrument: Trading instrument (default: EUR/USD)
 * - quantlab.lot_size: Position size in lots (default: 0.1)
 * - quantlab.max_positions: Maximum concurrent positions (default: 1)
 * - quantlab.write_interval_ms: How often to write state files (default: 5000)
 */
public class QuantLabTemplateStrategy implements IStrategy {

    private static final Logger LOG = Logger.getLogger(QuantLabTemplateStrategy.class.getName());

    // Strategy parameters (injected via system properties)
    private String stateDirPath = System.getProperty("user.home") + "/JForex4/state";
    private Instrument instrument = Instrument.EURUSD;
    private double lotSize = 0.1;
    private int maxPositions = 1;
    private long writeIntervalMs = 5000;

    // Runtime
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

    @Override
    public void onStart(IContext ctx) throws JFException {
        this.context = ctx;
        this.engine = ctx.getEngine();
        this.account = ctx.getAccount();
        this.history = ctx.getHistory();
        
        loadParameters();
        
        this.stateDir = Paths.get(stateDirPath);
        try {
            Files.createDirectories(stateDir);
        } catch (IOException e) {
            LOG.severe("Failed to create state directory: " + e.getMessage());
        }
        
        Set<Instrument> instruments = new HashSet<>();
        instruments.add(instrument);
        context.setSubscribedInstruments(instruments, true);
        
        writeStateFiles();
        
        LOG.info("QuantLabTemplateStrategy started for " + instrument + " | state_dir: " + stateDir);
    }

    private void loadParameters() {
        String prop;
        
        prop = System.getProperty("quantlab.state_dir");
        if (prop != null) this.stateDirPath = prop;
        
        prop = System.getProperty("quantlab.instrument");
        if (prop != null) this.instrument = Instrument.fromString(prop);
        
        prop = System.getProperty("quantlab.lot_size");
        if (prop != null) this.lotSize = Double.parseDouble(prop);
        
        prop = System.getProperty("quantlab.max_positions");
        if (prop != null) this.maxPositions = Integer.parseInt(prop);
        
        prop = System.getProperty("quantlab.write_interval_ms");
        if (prop != null) this.writeIntervalMs = Long.parseLong(prop);
    }

    @Override
    public void onTick(Instrument instrument, ITick tick) throws JFException {
        if (!this.instrument.equals(instrument)) return;
        
        double midPrice = (tick.getAsk() + tick.getBid()) / 2.0;
        updateEquity(midPrice);
        maybeWriteState();
    }

    @Override
    public void onBar(Instrument instrument, Period period, IBar askBar, IBar bidBar) throws JFException {
        if (!this.instrument.equals(instrument)) return;
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
            LOG.info("Order closed: " + order.getLabel() + " PL: " + order.getProfitLossInUSD());
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
        LOG.info("QuantLabTemplateStrategy stopping...");
        writeStateFiles();
    }

    private void updateEquity(double midPrice) {
        double unrealizedPl = 0.0;
        try {
            for (IOrder order : engine.getOrders()) {
                if (order.getState() == IOrder.State.FILLED && order.getInstrument().equals(instrument)) {
                    double pipValue = instrument.getPipValue();
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
            boolean connectedBool = false;
            long serverTime = context.getTime();
            boolean connectedBool2 = account != null && account.isConnected();
            writer.write(String.format("{\"connected\":%b,\"server_time\":%d,\"uptime_ms\":%d}",
                connectedBool2, serverTime, System.currentTimeMillis() - strategyStartTime));
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

    // ── Helper classes ────────────────────────────────────────────────────────

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
