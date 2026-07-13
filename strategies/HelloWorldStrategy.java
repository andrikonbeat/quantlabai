// HelloWorldStrategy.java
// A minimal JForex 4 compatible strategy template.
//
// This strategy opens a single LONG position when the strategy starts
// and closes it after one bar. It serves as a skeleton for developing
// more complex trading logic.
//
// Dependencies:
//   - JForex 4 API (com.dukascopy.api.*)
//   - Built with Java 11+
//
// Usage:
//   1. Place this file in your JForeX strategies directory.
//   2. Compile with JForex 4 libraries on the classpath.
//   3. Deploy via JForex Live or JCloud.

package strategies;

import com.dukascopy.api.IAccount;
import com.dukascopy.api.IBar;
import com.dukascopy.api.IConsole;
import com.dukascopy.api.IContext;
import com.dukascopy.api.IEngine;
import com.dukascopy.api.IEngine.OrderCommand;
import com.dukascopy.api.IHistory;
import com.dukascopy.api.IMessage;
import com.dukascopy.api.IOrder;
import com.dukascopy.api.IStrategy;
import com.dukascopy.api.ITick;
import com.dukascopy.api.Instrument;
import com.dukascopy.api.JFException;
import com.dukascopy.api.Period;

public class HelloWorldStrategy implements IStrategy {

    private IEngine engine;
    private IConsole console;
    private boolean positionOpened = false;

    @Override
    public void onStart(IContext context) throws JFException {
        this.engine = context.getEngine();
        this.console = context.getConsole();

        console.getOut().println("HelloWorldStrategy started — instrument: "
                + context.getInstrument());

        // Open a single LONG position on the default instrument
        Instrument instrument = context.getInstrument();
        if (instrument != null) {
            engine.submitOrder(
                "HelloWorldOrder",            // label
                instrument,                    // instrument
                OrderCommand.BUY,              // command
                0.01,                          // lots
                0,                             // slippage
                0,                             // stop loss (points)
                0,                             // take profit (points)
                0,                             // good until time (0 = GTC)
                "",                            // comment
                0,                             // trailing step
                0                              // trailing offset
            );
            positionOpened = true;
            console.getOut().println("Order submitted: BUY 0.01 lots");
        }
    }

    @Override
    public void onBar(Instrument instrument, Period period, IBar bidBar, IBar askBar)
            throws JFException {
        // Close the position after one bar if it is still open
        if (positionOpened) {
            for (IOrder order : engine.getOrders()) {
                if ("HelloWorldOrder".equals(order.getLabel())
                        && order.getState() == IOrder.State.FILLED) {
                    engine.closeOrder(order.getLabel());
                    console.getOut().println("Order closed after first bar");
                    break;
                }
            }
            positionOpened = false;
        }
    }

    @Override
    public void onMessage(IMessage message) throws JFException {
        // Log order fill and close messages
        if (message.getOrder() != null) {
            console.getOut().println(
                "Message: " + message.getType()
                + " — Order: " + message.getOrder().getLabel()
                + " — State: " + message.getOrder().getState()
            );
        }
    }

    @Override
    public void onTick(Instrument instrument, ITick tick) throws JFException {
        // Not used in this example
    }

    @Override
    public void onAccount(IAccount account) throws JFException {
        // Not used in this example
    }

    @Override
    public void onStop() throws JFException {
        if (console != null) {
            console.getOut().println("HelloWorldStrategy stopped");
        }
    }
}
