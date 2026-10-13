package com.quantlab.jforex_bridge.strategy;

import com.dukascopy.api.*;
import com.quantlab.jforex_bridge.dto.*;
import com.quantlab.jforex_bridge.service.MarketDataService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;

/**
 * JForex Strategy implementation that receives market data and forwards to services.
 */
@Component
public class JForexStrategy implements IStrategy {

    private static final Logger log = LoggerFactory.getLogger(JForexStrategy.class);

    private final MarketDataService marketDataService;
    private final Set<Instrument> subscribedInstruments = ConcurrentHashMap.newKeySet();

    @Autowired
    public JForexStrategy(MarketDataService marketDataService) {
        this.marketDataService = marketDataService;
    }

    @Override
    public void onStart(IContext context) {
        log.info("JForexStrategy started - subscribing to instruments");

        // Initialize market data service with context
        marketDataService.initialize(context);

        // Subscribe to all available instruments by default
        Set<Instrument> allInstruments = context.getSubscribedInstruments();
        if (allInstruments.isEmpty()) {
            // Subscribe to major pairs by default
            Set<Instrument> defaultInstruments = new HashSet<>(Arrays.asList(
                Instrument.EURUSD, Instrument.GBPUSD, Instrument.USDJPY,
                Instrument.AUDUSD, Instrument.USDCAD, Instrument.USDCHF,
                Instrument.NZDUSD, Instrument.EURGBP, Instrument.EURJPY,
                Instrument.GBPJPY, Instrument.XAUUSD, Instrument.XAGUSD
            ));
            context.setSubscribedInstruments(defaultInstruments);
            subscribedInstruments.addAll(defaultInstruments);
        } else {
            subscribedInstruments.addAll(allInstruments);
        }

        log.info("Subscribed to {} instruments", subscribedInstruments.size());
    }

    @Override
    public void onStop() {
        log.info("JForexStrategy stopped");
    }

    @Override
    public void onTick(Instrument instrument, ITick tick) {
        // Forward tick to market data service
        TickData tickData = new TickData(
            instrument.name(),
            tick.getTime(),
            tick.getBid(),
            tick.getAsk(),
            tick.getBidVolume(),
            tick.getAskVolume()
        );
        marketDataService.onTick(tickData);
    }

    @Override
    public void onBar(Instrument instrument, Period period, IBar askBar, IBar bidBar) {
        // Forward bar to market data service
        BarData askBarData = new BarData(
            instrument.name(),
            period.name(),
            OfferSide.ASK.name(),
            askBar.getTime(),
            askBar.getOpen(),
            askBar.getHigh(),
            askBar.getLow(),
            askBar.getClose(),
            askBar.getVolume()
        );
        BarData bidBarData = new BarData(
            instrument.name(),
            period.name(),
            OfferSide.BID.name(),
            bidBar.getTime(),
            bidBar.getOpen(),
            bidBar.getHigh(),
            bidBar.getLow(),
            bidBar.getClose(),
            bidBar.getVolume()
        );
        marketDataService.onBar(askBarData);
        marketDataService.onBar(bidBarData);
    }

    @Override
    public void onMessage(IMessage message) {
        // Handle system messages
        log.debug("Received message: {}", message.getContent());
    }

    @Override
    public void onAccount(IAccount account) {
        // Forward account updates
        AccountData accountData = new AccountData(
            account.getAccountId(),
            account.getCurrency().getCurrencyCode(),
            account.getEquity(),
            account.getBalance(),
            account.getLeverage(),
            account.getUsedMargin(),
            account.getEquity() - account.getUsedMargin(), // freeMargin = equity - usedMargin
            account.getMarginCutLevel(),
            account.getAccountState().name(),
            account.isConnected()
        );
        marketDataService.onAccount(accountData);
    }

    /**
     * Subscribe to an instrument for tick/bar updates.
     */
    public void subscribe(Instrument instrument) {
        subscribedInstruments.add(instrument);
    }

    /**
     * Unsubscribe from an instrument.
     */
    public void unsubscribe(Instrument instrument) {
        subscribedInstruments.remove(instrument);
    }

    public Set<Instrument> getSubscribedInstruments() {
        return new HashSet<>(subscribedInstruments);
    }
}