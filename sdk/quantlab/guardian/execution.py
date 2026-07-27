"""ExecutionGuardian: monitors broker health, latency, slippage, connection."""

from __future__ import annotations

import logging
import statistics
from typing import Dict, List, Optional

from .base import BaseGuardian
from .models import GuardianResult, GuardianType, GuardianStatus

logger = logging.getLogger(__name__)


class ExecutionGuardian(BaseGuardian):
    """Monitors execution quality and broker health."""

    def __init__(self, broker_interface, cost_collector=None):
        """Initialize the ExecutionGuardian.

        Args:
            broker_interface: Interface to the broker/trading platform
            cost_collector: Collector for cost data (from Auto-Costs, optional)
        """
        self.broker = broker_interface
        self.cost_collector = cost_collector

    def guardian_type(self) -> GuardianType:
        """Return the guardian type."""
        return GuardianType.EXECUTION

    def check(self) -> GuardianResult:
        """Check execution quality and return a health score.

        Returns:
            GuardianResult: Execution health assessment.
        """
        # Check broker connection
        try:
            connected = self._check_connection()
        except Exception as e:
            return GuardianResult(
                guardian_type=GuardianType.EXECUTION,
                status=GuardianStatus.RED,
                score=0.0,
                message=f"Broker connection check failed: {str(e)}",
            )

        if not connected:
            return GuardianResult(
                guardian_type=GuardianType.EXECUTION,
                status=GuardianStatus.RED,
                score=0.0,
                message="Broker disconnected",
            )

        # Check latency
        try:
            latency_score = self._check_latency()
        except Exception as e:
            logger.warning(f"Latency check failed: {e}")
            logger.debug(f"Exception details: {e}", exc_info=True)
            latency_score = 0.5  # Unknown latency
            latency_error = str(e)
        else:
            latency_error = None

        # Check slippage (if cost collector available)
        try:
            slippage_score = self._check_slippage()
        except Exception as e:
            logger.warning(f"Slippage check failed: {e}")
            logger.debug(f"Exception details: {e}", exc_info=True)
            slippage_score = 0.5  # Unknown slippage
            slippage_error = str(e)
        else:
            slippage_error = None

        # Check overall broker health
        try:
            health_score = self._check_broker_health()
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            logger.debug(f"Exception details: {e}", exc_info=True)
            health_score = 0.5  # Unknown health
            health_error = str(e)
        else:
            health_error = None

        # Weighted average
        weights = {
            "connection": 0.4,  # Critical - if disconnected, score 0
            "latency": 0.2,
            "slippage": 0.2,
            "health": 0.2,
        }
        
        # Connection is binary - if not connected, everything else is 0
        connection_score = 1.0 if connected else 0.0
        
        composite_score = (
            weights["connection"] * connection_score +
            weights["latency"] * latency_score +
            weights["slippage"] * slippage_score +
            weights["health"] * health_score
        )

        # Determine status
        if composite_score >= 0.8:
            status = GuardianStatus.GREEN
            message = "Execution quality good"
        elif composite_score >= 0.5:
            status = GuardianStatus.YELLOW
            message = "Execution quality degraded"
        else:
            status = GuardianStatus.RED
            message = "Execution quality poor - check broker"

        # Build detailed message
        details = []
        if latency_error:
            details.append(f"latency check failed: {latency_error}")
        if slippage_error:
            details.append(f"slippage check failed: {slippage_error}")
        if health_error:
            details.append(f"health check failed: {health_error}")
        
        if details:
            message += f" ({'; '.join(details)})"

        return GuardianResult(
            guardian_type=GuardianType.EXECUTION,
            status=status,
            score=round(composite_score, 3),
            message=message,
        )

    def _check_connection(self) -> bool:
        """Check if broker is connected and responsive.
        
        Returns:
            True if connected, False otherwise
            
        Raises:
            Exception: If a connection check method exists but fails
        """
        # Try multiple methods to check connection
        check_methods = [
            'is_connected',
            'check_connection',
            'get_connection_status',
            'is_connected_and_ready'
        ]
        
        for method_name in check_methods:
            if hasattr(self.broker, method_name):
                method = getattr(self.broker, method_name)
                if callable(method):
                    try:
                        result = method()
                        if isinstance(result, bool):
                            return result
                        elif isinstance(result, str):
                            return result.lower() in ('true', 'yes', '1', 'connected', 'ready')
                    except Exception as e:
                        # If a method exists and is callable but throws an exception,
                        # we treat this as a connection failure
                        raise e
        
        # Fallback: try a simple attribute
        if hasattr(self.broker, 'connected'):
            conn_attr = getattr(self.broker, 'connected')
            if isinstance(conn_attr, bool):
                return conn_attr
            elif isinstance(conn_attr, str):
                return conn_attr.lower() in ('true', 'yes', '1', 'connected', 'ready')
        
        # If we couldn't determine connection status through any method,
        # assume disconnected (fail safe)
        return False

    def _check_latency(self) -> float:
        """Check broker latency and return score (0-1).
        
        Returns:
            Score from 0.0 (high latency) to 1.0 (low latency)
        """
        # Try to get latency from various methods
        latency_ms = None
        latency_methods = [
            'get_latency',
            'latency',
            'ping',
            'get_ping_time',
            'get_response_time'
        ]
        
        for method_name in latency_methods:
            if hasattr(self.broker, method_name):
                method = getattr(self.broker, method_name)
                if callable(method):
                    try:
                        result = method()
                        if isinstance(result, (int, float)) and result >= 0:
                            latency_ms = float(result)
                            break
                    except Exception:
                        continue  # Try next method
        
        # Fallback to attribute
        if latency_ms is None and hasattr(self.broker, 'latency'):
            latency_attr = getattr(self.broker, 'latency')
            if isinstance(latency_attr, (int, float)) and latency_attr >= 0:
                latency_ms = float(latency_attr)
        
        # If still no latency, use a reasonable default
        if latency_ms is None:
            logger.debug("No latency information available, using default of 50ms")
            latency_ms = 50.0  # 50ms default - reasonable for good connection
        
        # Convert latency to score: 0ms = 1.0, 250ms+ = 0.0
        # 250ms is considered high latency for trading
        return max(0.0, min(1.0, 1.0 - (latency_ms / 250.0)))

    def _check_slippage(self) -> float:
        """Check slippage from recent trades and return score (0-1).
        
        Returns:
            Score from 0.0 (high slippage) to 1.0 (low slippage)
        """
        if not self.cost_collector:
            # Try to get slippage from broker directly
            try:
                if hasattr(self.broker, 'get_recent_slippage'):
                    slippage = self.broker.get_recent_slippage()
                    if isinstance(slippage, (int, float)) and slippage >= 0:
                        # Slippage in bps (basis points): 0-10 bps excellent, 50+ bps poor
                        return max(0.0, min(1.0, 1.0 - (slippage / 50.0)))
            except Exception:
                pass  # Fall back to default
            
            # No cost collector and no broker slippage data
            return 0.7  # Reasonable default
        
        # Try to get slippage data from cost collector
        try:
            if hasattr(self.cost_collector, 'get_recent_slippage'):
                slippage_data = self.cost_collector.get_recent_slippage()
                if isinstance(slippage_data, (int, float)) and slippage_data >= 0:
                    # Slippage in bps: 0-3 bps excellent, 10+ bps concerning
                    return max(0.0, min(1.0, 1.0 - (slippage_data / 15.0)))
            elif hasattr(self.cost_collector, 'slippage'):
                slippage_attr = getattr(self.cost_collector, 'slippage')
                if isinstance(slippage_attr, (int, float)) and slippage_attr >= 0:
                    return max(0.0, min(1.0, 1.0 - (slippage_attr / 15.0)))
        except Exception:
            pass  # Fall back to default
        
        # Default slippage assumption
        return 0.8  # Good execution quality

    def _check_broker_health(self) -> float:
        """Check overall broker health and return score (0-1).
        
        Returns:
            Score from 0.0 (unhealthy) to 1.0 (healthy)
        """
        # Try to get health score from various methods
        health_score = None
        health_methods = [
            'get_health_score',
            'health',
            'get_status',
            'is_healthy',
            'get_health'
        ]
        
        for method_name in health_methods:
            if hasattr(self.broker, method_name):
                method = getattr(self.broker, method_name)
                if callable(method):
                    try:
                        result = method()
                        if isinstance(result, (int, float)) and 0.0 <= result <= 1.0:
                            return float(result)
                        elif isinstance(result, str):
                            # Try to parse common health strings
                            result_lower = result.lower()
                            if result_lower in ('excellent', 'perfect', 'optimal'):
                                return 1.0
                            elif result_lower in ('good', 'healthy', 'ok'):
                                return 0.8
                            elif result_lower in ('fair', 'degraded', 'warning'):
                                return 0.5
                            elif result_lower in ('poor', 'unhealthy', 'critical'):
                                return 0.2
                            elif result_lower in ('down', 'offline', 'failed'):
                                return 0.0
                    except (ValueError, TypeError):
                        continue  # Try next method
        
        # Try to get health from attributes
        if health_score is None:
            for attr_name in ['health', 'health_status', 'status']:
                if hasattr(self.broker, attr_name):
                    attr_value = getattr(self.broker, attr_name)
                    if isinstance(attr_value, (int, float)) and 0.0 <= attr_value <= 1.0:
                        return float(attr_value)
                    elif isinstance(attr_value, str):
                        # Try string conversion as above
                        try:
                            val = float(attr_value)
                            if 0.0 <= val <= 1.0:
                                return val
                        except ValueError:
                            pass  # Not a simple float
        
        # Default assumption: reasonably healthy
        return 0.85