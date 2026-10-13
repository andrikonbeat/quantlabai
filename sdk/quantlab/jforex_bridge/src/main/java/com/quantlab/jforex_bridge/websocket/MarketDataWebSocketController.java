package com.quantlab.jforex_bridge.websocket;

import com.quantlab.jforex_bridge.dto.TickData;
import com.quantlab.jforex_bridge.dto.BarData;
import com.quantlab.jforex_bridge.dto.AccountData;
import com.quantlab.jforex_bridge.service.MarketDataService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Lazy;
import org.springframework.messaging.handler.annotation.MessageMapping;
import org.springframework.messaging.handler.annotation.SendTo;
import org.springframework.messaging.simp.SimpMessageSendingOperations;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.CrossOrigin;

import java.util.Map;
import java.util.concurrent.CopyOnWriteArrayList;

@Controller
@CrossOrigin(origins = "*")
public class MarketDataWebSocketController {

    private static final Logger log = LoggerFactory.getLogger(MarketDataWebSocketController.class);

    private final MarketDataService marketDataService;
    private final SimpMessageSendingOperations messagingTemplate;
    private final java.util.concurrent.CopyOnWriteArrayList<String> tickSubscriptions = new CopyOnWriteArrayList<>();
    private final java.util.concurrent.CopyOnWriteArrayList<String> barSubscriptions = new CopyOnWriteArrayList<>();
    private final java.util.concurrent.CopyOnWriteArrayList<String> accountSubscriptions = new CopyOnWriteArrayList<>();

    @Autowired
    public MarketDataWebSocketController(
            @Lazy MarketDataService marketDataService,
            SimpMessageSendingOperations messagingTemplate) {
        this.marketDataService = marketDataService;
        this.messagingTemplate = messagingTemplate;
    }

    @MessageMapping("/subscribe/ticks")
    @SendTo("/topic/ticks")
    public void subscribeTicks(String instrument) {
        if (instrument != null && !instrument.isEmpty()) {
            tickSubscriptions.add(instrument.toUpperCase());
            log.info("Subscribed to ticks for: {}", instrument);
        }
    }

    @MessageMapping("/unsubscribe/ticks")
    @SendTo("/topic/ticks")
    public void unsubscribeTicks(String instrument) {
        if (instrument != null && !instrument.isEmpty()) {
            tickSubscriptions.remove(instrument.toUpperCase());
            log.info("Unsubscribed from ticks for: {}", instrument);
        }
    }

    @MessageMapping("/subscribe/bars")
    @SendTo("/topic/bars")
    public void subscribeBars(String payload) {
        if (payload != null && !payload.isEmpty()) {
            barSubscriptions.add(payload.toUpperCase());
            log.info("Subscribed to bars: {}", payload);
        }
    }

    @MessageMapping("/subscribe/account")
    @SendTo("/topic/account")
    public void subscribeAccount(String ignore) {
        accountSubscriptions.add("account");
        log.info("Subscribed to account updates");
    }

    /**
     * Called by MarketDataService to broadcast tick data.
     */
    public void broadcastTick(TickData tick) {
        if (tickSubscriptions.contains(tick.getInstrument()) || tickSubscriptions.isEmpty()) {
            messagingTemplate.convertAndSend("/topic/ticks", tick);
        }
    }

    /**
     * Called by MarketDataService to broadcast bar data.
     */
    public void broadcastBar(BarData bar) {
        String key = bar.getInstrument() + "_" + bar.getPeriod() + "_" + bar.getSide();
        if (barSubscriptions.contains(key) || barSubscriptions.isEmpty()) {
            messagingTemplate.convertAndSend("/topic/bars", bar);
        }
    }

    /**
     * Called by MarketDataService to broadcast account updates.
     */
    public void broadcastAccount(AccountData account) {
        if (!accountSubscriptions.isEmpty()) {
            messagingTemplate.convertAndSend("/topic/account", account);
        }
    }

    /**
     * Get subscription counts for monitoring.
     */
    public Map<String, Integer> getSubscriptionCounts() {
        return Map.of(
            "ticks", tickSubscriptions.size(),
            "bars", barSubscriptions.size(),
            "account", accountSubscriptions.size()
        );
    }
}