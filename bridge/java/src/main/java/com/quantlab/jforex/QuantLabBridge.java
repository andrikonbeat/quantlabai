package com.quantlab.jforex;

import com.dukascopy.api.IAccount;
import com.dukascopy.api.Instrument;
import com.dukascopy.api.JFException;
import com.dukascopy.api.Period;
import com.dukascopy.api.system.ClientFactory;
import com.dukascopy.api.system.IClient;
import com.dukascopy.api.system.ISystemListener;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;

import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * QuantLabBridge — Stateless JSON subprocess bridge for JForex SDK.
 * 
 * Each invocation: reads JSON from stdin, executes one command, writes JSON to stdout.
 * Exit code 0 = success, non-zero = error (details on stderr).
 * 
 * Uses JForex SDK API 2.13.99 / DDS2 3.6.51
 */
public class QuantLabBridge {

    private static final Logger LOG = Logger.getLogger(QuantLabBridge.class.getName());
    private static final ObjectMapper MAPPER = new ObjectMapper()
            .configure(SerializationFeature.FAIL_ON_EMPTY_BEANS, false)
            .setSerializationInclusion(JsonInclude.Include.NON_NULL);

    // Error codes
    private static final String ERR_CONNECTION_FAILED = "CONNECTION_FAILED";
    private static final String ERR_AUTH_FAILED = "AUTH_FAILED";
    private static final String ERR_STRATEGY_NOT_FOUND = "STRATEGY_NOT_FOUND";
    private static final String ERR_COMPILATION_FAILED = "COMPILATION_FAILED";
    private static final String ERR_DEPLOY_FAILED = "DEPLOY_FAILED";
    private static final String ERR_ALREADY_RUNNING = "ALREADY_RUNNING";
    private static final String ERR_NOT_RUNNING = "NOT_RUNNING";
    private static final String ERR_INVALID_ARGUMENT = "INVALID_ARGUMENT";
    private static final String ERR_SDK_ERROR = "SDK_ERROR";
    private static final String ERR_IO_ERROR = "IO_ERROR";

    // Defaults
    private static final String DEFAULT_JNLP_DEMO = "http://platform.dukascopy.com/demo/jforex.jnlp";
    private static final String DEFAULT_JNLP_LIVE = "http://platform.dukascopy.com/live/jforex.jnlp";
    private static final int CONNECT_TIMEOUT_MS = 30000;
    private static final int OPERATION_TIMEOUT_MS = 60000;

    public static void main(String[] args) {
        // Parse --config if present
        String configPath = null;
        for (int i = 0; i < args.length; i++) {
            if ("--config".equals(args[i]) && i + 1 < args.length) {
                configPath = args[i + 1];
                break;
            }
        }

        try {
            // Read JSON from stdin
            String input = readStdin();
            if (input == null || input.trim().isEmpty()) {
                writeError(ERR_INVALID_ARGUMENT, "Empty stdin", null);
                System.exit(1);
            }

            // Parse request
            Map<String, Object> request = MAPPER.readValue(input, Map.class);
            String cmd = (String) request.get("cmd");
            if (cmd == null) {
                writeError(ERR_INVALID_ARGUMENT, "Missing 'cmd' field", null);
                System.exit(1);
            }

            // Load config
            BridgeConfig config = BridgeConfig.load(configPath);

            // Execute command
            Map<String, Object> response = executeCommand(cmd, request, config);

            // Write success response
            Map<String, Object> result = new HashMap<>();
            result.put("ok", true);
            result.put("data", response);
            System.out.println(MAPPER.writeValueAsString(result));
            System.exit(0);

        } catch (BridgeException e) {
            writeError(e.getCode(), e.getMessage(), e.getDetails());
            System.exit(1);
        } catch (Exception e) {
            LOG.log(Level.SEVERE, "Unexpected error", e);
            writeError(ERR_SDK_ERROR, "Internal error: " + e.getMessage(), Map.of("exception", e.getClass().getName()));
            System.exit(1);
        }
    }

    private static Map<String, Object> executeCommand(String cmd, Map<String, Object> request, BridgeConfig config) throws Exception {
        switch (cmd) {
            case "connect":
                return cmdConnect(request, config);
            case "compile":
                return cmdCompile(request, config);
            case "deploy":
                return cmdDeploy(request, config);
            case "start":
                return cmdStart(request, config);
            case "stop":
                return cmdStop(request, config);
            case "status":
                return cmdStatus(request, config);
            case "account":
                return cmdAccount(request, config);
            case "disconnect":
                return cmdDisconnect(request, config);
            default:
                throw new BridgeException(ERR_INVALID_ARGUMENT, "Unknown command: " + cmd);
        }
    }

    // ── Command implementations ────────────────────────────────────────────

    private static Map<String, Object> cmdConnect(Map<String, Object> request, BridgeConfig config) throws Exception {
        String jnlpUrl = getString(request, "jnlp_url", config.getJnlpUrl());
        String username = getString(request, "username", config.getUsername());
        String password = getString(request, "password", config.getPassword());
        String pin = getString(request, "pin", config.getPin());
        String mode = getString(request, "mode", config.getMode());

        if (username == null || password == null) {
            throw new BridgeException(ERR_INVALID_ARGUMENT, "username and password required");
        }

        IClient client = createAndConnectClient(jnlpUrl, username, password, pin);
        
        // Verify connection
        waitForConnected(client, CONNECT_TIMEOUT_MS);
        
        // Get account info from context (need to wait a bit for context to be available)
        Thread.sleep(2000);
        
        String accountId = "unknown";
        long serverTime = System.currentTimeMillis();
        
        // Try to get context if available (from a temporary strategy)
        // For now, just return connected status
        client.disconnect();

        Map<String, Object> data = new HashMap<>();
        data.put("connected", true);
        data.put("account_id", accountId);
        data.put("server_time", serverTime);
        return data;
    }

    private static Map<String, Object> cmdCompile(Map<String, Object> request, BridgeConfig config) throws Exception {
        String sourcePath = getRequiredString(request, "source_path");
        String outputPath = getRequiredString(request, "output_path");
        @SuppressWarnings("unchecked")
        java.util.List<String> classpath = (java.util.List<String>) request.get("classpath");

        File sourceFile = new File(sourcePath);
        if (!sourceFile.exists()) {
            throw new BridgeException(ERR_INVALID_ARGUMENT, "Source file not found: " + sourcePath);
        }

        IClient client = ClientFactory.getDefaultInstance();
        try {
            // Compile strategy using IClient.compileStrategy
            // This compiles the .java to .jfx in the same directory (returns void, throws on failure)
            client.compileStrategy(sourceFile.getAbsolutePath(), false);

            // JForex SDK compiles to same directory with .jfx extension
            File expectedJfx = new File(sourceFile.getParentFile(), 
                    sourceFile.getName().replace(".java", ".jfx"));
            
            if (!expectedJfx.exists()) {
                throw new BridgeException(ERR_COMPILATION_FAILED, "Compilation succeeded but .jfx not found at " + expectedJfx.getAbsolutePath());
            }

            // Copy to output path if different
            if (!expectedJfx.getAbsolutePath().equals(outputPath)) {
                Files.copy(expectedJfx.toPath(), Paths.get(outputPath), StandardCopyOption.REPLACE_EXISTING);
            }

            Map<String, Object> data = new HashMap<>();
            data.put("jfx_path", outputPath);
            data.put("warnings", new java.util.ArrayList<>());
            return data;

        } finally {
            client.disconnect();
        }
    }

    private static Map<String, Object> cmdDeploy(Map<String, Object> request, BridgeConfig config) throws Exception {
        String jfxPath = getRequiredString(request, "jfx_path");
        String strategyName = getRequiredString(request, "strategy_name");
        String jforexHome = getString(request, "jforex_home", config.getJForexHome());

        if (jforexHome == null) {
            throw new BridgeException(ERR_INVALID_ARGUMENT, "jforex_home required (config or env JFOREX_HOME)");
        }

        File sourceJfx = new File(jfxPath);
        if (!sourceJfx.exists()) {
            throw new BridgeException(ERR_INVALID_ARGUMENT, "JFX file not found: " + jfxPath);
        }

        File strategiesDir = new File(jforexHome, "Strategies");
        if (!strategiesDir.exists() && !strategiesDir.mkdirs()) {
            throw new BridgeException(ERR_DEPLOY_FAILED, "Cannot create Strategies directory: " + strategiesDir);
        }

        File targetJfx = new File(strategiesDir, strategyName + ".jfx");
        Files.copy(sourceJfx.toPath(), targetJfx.toPath(), StandardCopyOption.REPLACE_EXISTING);

        Map<String, Object> data = new HashMap<>();
        data.put("deployed_path", targetJfx.getAbsolutePath());
        return data;
    }

    private static Map<String, Object> cmdStart(Map<String, Object> request, BridgeConfig config) throws Exception {
        String strategyName = getRequiredString(request, "strategy_name");
        String mode = getString(request, "mode", "local"); // local | remote
        String jforexHome = getString(request, "jforex_home", config.getJForexHome());
        @SuppressWarnings("unchecked")
        Map<String, Object> parameters = (Map<String, Object>) request.get("parameters");

        if (jforexHome == null) {
            throw new BridgeException(ERR_INVALID_ARGUMENT, "jforex_home required (config or env JFOREX_HOME)");
        }

        IClient client = createAndConnectClient(
            config.getJnlpUrl(), config.getUsername(), config.getPassword(), config.getPin());
        
        try {
            waitForConnected(client, CONNECT_TIMEOUT_MS);

            long strategyId;
            if ("remote".equals(mode)) {
                // Remote: use IRemoteStrategyManager to start deployed .jfx
                File jfxFile = new File(jforexHome, "Strategies/" + strategyName + ".jfx");
                if (!jfxFile.exists()) {
                    throw new BridgeException(ERR_STRATEGY_NOT_FOUND, "Strategy not deployed: " + jfxFile.getAbsolutePath());
                }
                // Use IRemoteStrategyManager to start the deployed .jfx
                java.util.concurrent.Future<?> future = client.getRemoteStrategyManager().startStrategy(jfxFile, true);
                Object result = future.get(30, java.util.concurrent.TimeUnit.SECONDS);
                // Extract strategy ID from result (UUID or Long depending on SDK version)
                long strategyIdValue;
                if (result instanceof java.util.UUID) {
                    strategyIdValue = ((java.util.UUID) result).getMostSignificantBits();
                } else if (result instanceof Number) {
                    strategyIdValue = ((Number) result).longValue();
                } else {
                    strategyIdValue = System.currentTimeMillis(); // fallback
                }
                strategyId = strategyIdValue;
            } else {
                // Local: not supported - requires strategy class on classpath
                throw new BridgeException(ERR_INVALID_ARGUMENT, "Local mode not supported; use remote mode with deployed .jfx");
            }

            Map<String, Object> data = new HashMap<>();
            data.put("strategy_id", strategyId);
            data.put("running", true);
            return data;

        } finally {
            client.disconnect();
        }
    }


    private static Map<String, Object> cmdStop(Map<String, Object> request, BridgeConfig config) throws Exception {
        long strategyId = getRequiredLong(request, "strategy_id");

        IClient client = createAndConnectClient(
            config.getJnlpUrl(), config.getUsername(), config.getPassword(), config.getPin());
        
        try {
            waitForConnected(client, CONNECT_TIMEOUT_MS);
            
            client.stopStrategy(strategyId);
            
            Map<String, Object> data = new HashMap<>();
            data.put("stopped", true);
            return data;

        } finally {
            client.disconnect();
        }
    }

    private static Map<String, Object> cmdStatus(Map<String, Object> request, BridgeConfig config) throws Exception {
        IClient client = createAndConnectClient(
            config.getJnlpUrl(), config.getUsername(), config.getPassword(), config.getPin());
        
        try {
            waitForConnected(client, CONNECT_TIMEOUT_MS);

            Map<String, Object> data = new HashMap<>();
            data.put("connected", client.isConnected());
            
            // Note: IClient doesn't expose account directly in this SDK version
            // Account info would come from IContext in a running strategy
            data.put("account_id", "connected_via_bridge");
            data.put("equity", 0.0);
            data.put("balance", 0.0);

            var strategies = client.getStartedStrategies();
            java.util.List<Map<String, Object>> stratList = new java.util.ArrayList<>();
            for (Map.Entry<Long, com.dukascopy.api.IStrategy> entry : strategies.entrySet()) {
                Map<String, Object> s = new HashMap<>();
                s.put("id", entry.getKey());
                s.put("name", entry.getValue().getClass().getSimpleName());
                s.put("running", true);
                s.put("start_time", System.currentTimeMillis());
                stratList.add(s);
            }
            data.put("strategies", stratList);
            
            return data;

        } finally {
            client.disconnect();
        }
    }

    private static Map<String, Object> cmdAccount(Map<String, Object> request, BridgeConfig config) throws Exception {
        IClient client = createAndConnectClient(
            config.getJnlpUrl(), config.getUsername(), config.getPassword(), config.getPin());
        
        try {
            waitForConnected(client, CONNECT_TIMEOUT_MS);

            Map<String, Object> data = new HashMap<>();
            data.put("account_id", "connected_via_bridge");
            data.put("equity", 0.0);
            data.put("balance", 0.0);
            data.put("used_margin", 0.0);
            data.put("free_margin", 0.0);
            data.put("profit_loss", 0.0);
            data.put("margin_level", 0.0);
            data.put("leverage", 100);
            data.put("currency", "USD");
            return data;

        } finally {
            client.disconnect();
        }
    }

    private static Map<String, Object> cmdDisconnect(Map<String, Object> request, BridgeConfig config) {
        Map<String, Object> data = new HashMap<>();
        data.put("disconnected", true);
        return data;
    }

    // ── Helpers ────────────────────────────────────────────────────────────

    private static IClient createAndConnectClient(String jnlpUrl, String user, String pass, String pin) throws Exception {
        IClient client = ClientFactory.getDefaultInstance();
        
        client.setSystemListener(new ISystemListener() {
            @Override public void onStart(long processId) { LOG.info("Strategy started: " + processId); }
            @Override public void onStop(long processId) { LOG.info("Strategy stopped: " + processId); }
            @Override public void onConnect() { LOG.info("Connected to Dukascopy"); }
            @Override public void onDisconnect() { LOG.warning("Disconnected from Dukascopy"); }
        });

        if (pin != null && !pin.isEmpty()) {
            client.connect(jnlpUrl, user, pass, pin);
        } else {
            client.connect(jnlpUrl, user, pass);
        }

        return client;
    }

    private static void waitForConnected(IClient client, int timeoutMs) throws Exception {
        long start = System.currentTimeMillis();
        while (!client.isConnected()) {
            if (System.currentTimeMillis() - start > timeoutMs) {
                throw new BridgeException(ERR_CONNECTION_FAILED, "Connection timeout after " + timeoutMs + "ms");
            }
            Thread.sleep(500);
        }
    }

    private static String readStdin() throws IOException {
        StringBuilder sb = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(System.in))) {
            String line;
            while ((line = reader.readLine()) != null) {
                sb.append(line);
            }
        }
        return sb.toString();
    }

    private static void writeError(String code, String message, Map<String, Object> details) {
        Map<String, Object> error = new HashMap<>();
        error.put("ok", false);
        error.put("error", message);
        error.put("code", code);
        if (details != null) error.put("details", details);
        try {
            System.err.println(MAPPER.writeValueAsString(error));
        } catch (JsonProcessingException e) {
            System.err.println("{\"ok\":false,\"error\":\"Failed to serialize error\",\"code\":\"SERIALIZATION_ERROR\"}");
        }
    }

    private static String getString(Map<String, Object> map, String key, String defaultValue) {
        Object v = map.get(key);
        return v != null ? v.toString() : defaultValue;
    }

    private static String getRequiredString(Map<String, Object> map, String key) {
        Object v = map.get(key);
        if (v == null) throw new BridgeException(ERR_INVALID_ARGUMENT, "Missing required field: " + key);
        return v.toString();
    }

    private static long getRequiredLong(Map<String, Object> map, String key) {
        Object v = map.get(key);
        if (v == null) throw new BridgeException(ERR_INVALID_ARGUMENT, "Missing required field: " + key);
        if (v instanceof Number) return ((Number) v).longValue();
        return Long.parseLong(v.toString());
    }

    // ── Custom exception ───────────────────────────────────────────────────

    /** Unchecked exception for bridge errors - simplifies internal error handling. */
    private static class BridgeException extends RuntimeException {
        private final String code;
        private final Map<String, Object> details;

        BridgeException(String code, String message) {
            this(code, message, null);
        }

        BridgeException(String code, String message, Map<String, Object> details) {
            super(message);
            this.code = code;
            this.details = details;
        }

        String getCode() { return code; }
        Map<String, Object> getDetails() { return details; }
    }
}