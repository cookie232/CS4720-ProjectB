// BUG TM Double Decision:
//   commit() sends Commit to all RMs, then immediately sends Abort as well.
//   TLA+ violations:
//     -   TMAbort requires tmState = "init", but tmState = "done" after TMCommit,
//         so TLC rejects the TMAbort trace step as having no matching enabled action.
//     -   Once Commit is in msgs, any RM that receives Abort and aborts violates
//         TCConsistent (some RMs commit, some abort).
package org.lbee.protocol;

import java.io.IOException;
import java.util.Collection;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.lbee.helpers.Helper;
import org.lbee.instrumentation.trace.TLATracer;
import org.lbee.instrumentation.trace.VirtualField;
import org.lbee.network.NetworkManager;
import org.lbee.network.TimeOutException;

public class TransactionManager extends Manager {

    private final static int RECEIVE_TIMEOUT = 100;
    private final static int ABORT_TIMEOUT = 100;
    private static final int MAX_INIT_DURATION = 100;

    private final Set<String> resourceManagers;
    private final Collection<String> preparedRMs;
    private final int initDuration;

    private final VirtualField traceMessages;
    private final VirtualField traceTmPrepared;
    private final VirtualField traceState;

    public TransactionManager(NetworkManager networkManager, String name, List<String> resourceManagerNames,
            int initDuration, TLATracer tracer) {
        super(name, networkManager, tracer);
        this.resourceManagers = new HashSet<>(resourceManagerNames);
        this.preparedRMs = new HashSet<>();
        if (initDuration == -1) {
            this.initDuration = Helper.next(MAX_INIT_DURATION);
        } else {
            this.initDuration = initDuration;
        }
        this.traceMessages = tracer.getVariableTracer("msgs");
        this.traceTmPrepared = tracer.getVariableTracer("tmPrepared");
        this.traceState = tracer.getVariableTracer("tmState");
    }

    private void initialising() {
        try {
            Thread.sleep(this.initDuration);
        } catch (InterruptedException ex) {
        }
    }

    @Override
    public void run() throws IOException {
        long startTime = System.currentTimeMillis();
        this.initialising();
        while (true) {
            boolean messageReceived = false;
            do {
                if (System.currentTimeMillis() - startTime > ABORT_TIMEOUT) {
                    this.abort();
                    System.out.println("-- TM  aborted (timeout)");
                    return;
                }
                try {
                    Message message = networkManager.receive(this.name, RECEIVE_TIMEOUT);
                    this.handleMessage(message);
                    messageReceived = true;
                } catch (TimeOutException e) {
                    System.out.println("TM received TIMEOUT");
                }
            } while (!messageReceived);

            if (checkAllPrepared()) {
                this.commit();
                System.out.println("-- TM  shutdown");
                return;
            }
        }
    }

    private void handleMessage(Message message) throws IOException {
        if (message.getContent().equals(TwoPhaseMessage.Prepared.toString())) {
            String preparedRM = message.getFrom();
            if (resourceManagers.contains(preparedRM)) {
                this.preparedRMs.add(preparedRM);
                traceTmPrepared.add(preparedRM);
                traceState.unchanged();
                tracer.log("TMRcvPrepared", preparedRM);
            }
        }
        System.out.println(
                "TM received " + message.getContent() + " from " + message.getFrom() + " => " + this.preparedRMs);
    }

    private void abort() throws IOException {
        traceMessages.add(Map.of("type", TwoPhaseMessage.Abort.toString()));
        traceState.update("done");
        tracer.log("TMAbort");
        for (String rmName : resourceManagers) {
            this.networkManager.send(new Message(this.name, rmName, TwoPhaseMessage.Abort.toString(), 0));
        }
        System.out.println("TM sends Abort");
    }

    protected boolean checkAllPrepared() {
        return this.preparedRMs.size() >= this.resourceManagers.size();
    }

    // Buggy implementation of commit() that sends both Commit and Abort messages to RMs.
    private void commit() throws IOException {
        traceMessages.add(Map.of("type", TwoPhaseMessage.Commit.toString()));
        traceState.update("done");
        tracer.log("TMCommit");
        for (String rmName : resourceManagers) {
            this.networkManager.send(new Message(this.name, rmName, TwoPhaseMessage.Commit.toString(), 0));
        }
        System.out.println("TM sent Commits");

        traceMessages.add(Map.of("type", TwoPhaseMessage.Abort.toString()));
        traceState.update("done");
        tracer.log("TMAbort");
        for (String rmName : resourceManagers) {
            this.networkManager.send(new Message(this.name, rmName, TwoPhaseMessage.Abort.toString(), 0));
        }
        System.out.println("TM sent Aborts (after already committing)");
    }
}
