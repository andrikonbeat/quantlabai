package com.quantlab.jforex_bridge;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableAsync
@EnableScheduling
public class JForexBridgeApplication {

    public static void main(String[] args) {
        SpringApplication.run(JForexBridgeApplication.class, args);
    }

    @Configuration
    @Profile("test")
    static class TestConfig {
        // Test-specific beans can go here
    }
}