package com.quantlab.jforex;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;

/**
 * Bridge configuration loader.
 * Priority: --config file > environment variables > defaults
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public class BridgeConfig {

    private String jnlpUrl;
    private String username;
    private String password;
    private String pin;
    private String mode; // demo | live
    private String jforexHome;

    // Defaults
    private static final String DEFAULT_JNLP_DEMO = "http://platform.dukascopy.com/demo/jforex.jnlp";
    private static final String DEFAULT_JNLP_LIVE = "http://platform.dukascopy.com/live/jforex.jnlp";
    private static final String DEFAULT_MODE = "demo";

    public static BridgeConfig load(String configPath) {
        BridgeConfig config = new BridgeConfig();

        // 1. Load from config file if provided
        if (configPath != null) {
            config.loadFromFile(configPath);
        }

        // 2. Override with environment variables
        config.applyEnvOverrides();

        // 3. Apply defaults
        config.applyDefaults();

        return config;
    }

    private void loadFromFile(String path) {
        try {
            String content = Files.readString(Paths.get(path));
            ObjectMapper mapper = new ObjectMapper();
            BridgeConfig fileConfig = mapper.readValue(content, BridgeConfig.class);
            merge(fileConfig);
        } catch (IOException e) {
            System.err.println("Warning: Failed to load config from " + path + ": " + e.getMessage());
        }
    }

    private void applyEnvOverrides() {
        String envJnlp = System.getenv("JFOREX_JNLP_URL");
        if (envJnlp != null) this.jnlpUrl = envJnlp;

        String envUser = System.getenv("JFOREX_USER");
        if (envUser != null) this.username = envUser;

        String envPass = System.getenv("JFOREX_PASS");
        if (envPass != null) this.password = envPass;

        String envPin = System.getenv("JFOREX_PIN");
        if (envPin != null) this.pin = envPin;

        String envMode = System.getenv("JFOREX_MODE");
        if (envMode != null) this.mode = envMode;

        String envHome = System.getenv("JFOREX_HOME");
        if (envHome != null) this.jforexHome = envHome;
    }

    private void applyDefaults() {
        if (this.jnlpUrl == null) {
            this.jnlpUrl = DEFAULT_MODE.equals("live") ? DEFAULT_JNLP_LIVE : DEFAULT_JNLP_DEMO;
        }
        if (this.mode == null) {
            this.mode = DEFAULT_MODE;
        }
    }

    private void merge(BridgeConfig other) {
        if (other.jnlpUrl != null) this.jnlpUrl = other.jnlpUrl;
        if (other.username != null) this.username = other.username;
        if (other.password != null) this.password = other.password;
        if (other.pin != null) this.pin = other.pin;
        if (other.mode != null) this.mode = other.mode;
        if (other.jforexHome != null) this.jforexHome = other.jforexHome;
    }

    // Getters
    public String getJnlpUrl() { return jnlpUrl; }
    public String getUsername() { return username; }
    public String getPassword() { return password; }
    public String getPin() { return pin; }
    public String getMode() { return mode; }
    public String getJForexHome() { return jforexHome; }

    // Setters (for JSON deserialization)
    public void setJnlpUrl(String jnlpUrl) { this.jnlpUrl = jnlpUrl; }
    public void setUsername(String username) { this.username = username; }
    public void setPassword(String password) { this.password = password; }
    public void setPin(String pin) { this.pin = pin; }
    public void setMode(String mode) { this.mode = mode; }
    public void setJforexHome(String jforexHome) { this.jforexHome = jforexHome; }
}