// IndicatorExporter.java — QuantLab strategy indicator export helper (REQ-05).
//
// Packaged into generated .jfx archives by the QuantLab pipeline so JForex4
// strategies can persist computed indicator values for LLM consumption.
//
// The Java strategy calls:
//     IndicatorExporter.export("BullEyes_M15", indicators);
// where indicators maps indicator name -> current value. The helper writes
// `~/JForex4/exports/quantlab-indicators-<strategy>.json` with a timestamped
// snapshot matching the schema parsed by quantlab.jforex.exporter.IndicatorExport.
package quantlab;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;

/** Writes quantified indicator values to a local JSON file for QuantLab LLM agents. */
public final class IndicatorExporter {

    private IndicatorExporter() {
    }

    /** Export a snapshot of indicator values for {@code strategy}. */
    public static Path export(String strategy, Map<String, Double> indicators)
            throws IOException {
        Path exportsDir = Paths.get(
                System.getProperty("user.home"), "JForex4", "exports");
        Files.createDirectories(exportsDir);
        Path target = exportsDir.resolve(
                "quantlab-indicators-" + strategy + ".json");

        StringBuilder json = new StringBuilder();
        json.append("{\n  \"strategy\": \"").append(escape(strategy)).append("\",\n");
        json.append("  \"exported_at\": \"").append(Instant.now()).append("\",\n");
        json.append("  \"indicators\": [\n");
        int i = 0;
        for (Map.Entry<String, Double> entry : indicators.entrySet()) {
            json.append("    {\"name\": \"").append(escape(entry.getKey()))
                .append("\", \"value\": ").append(entry.getValue())
                .append(", \"timestamp\": \"").append(Instant.now())
                .append("\"}");
            if (++i < indicators.size()) {
                json.append(",");
            }
            json.append("\n");
        }
        json.append("  ]\n}\n");
        Files.write(target, json.toString().getBytes(StandardCharsets.UTF_8));
        return target;
    }

    /** Convenience overload: strategy name is inferred as the singleton key. */
    public static Path export(Map<String, Double> indicators) throws IOException {
        return export(defaultStrategyName(indicators), indicators);
    }

    private static String defaultStrategyName(Map<String, Double> indicators) {
        return indicators.size() == 1
                ? entries(indicators).get(0).getKey()
                : "strategy";
    }

    private static java.util.List<Map.Entry<String, Double>> entries(
            Map<String, Double> map) {
        return new java.util.ArrayList<Map.Entry<String, Double>>(map.entrySet());
    }

    private static String escape(String value) {
        return value.replace("\\", "\\\\").replace("\"", "\\\"");
    }
}