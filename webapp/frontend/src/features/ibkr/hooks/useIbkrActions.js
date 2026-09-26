import { useState } from 'react';
import { API_BASE } from '../../../api/base';
import { confirmDialog, toast } from '../../../shared/components/feedback';

function useIbkrActions(ibkrStatus) {
  const isLive = ibkrStatus?.mode === 'live';
  const isGateway = ibkrStatus?.client === 'gateway';
  const isConnected = !!ibkrStatus?.connected;
  const [switchingMode, setSwitchingMode] = useState(false);
  const [switchingClient, setSwitchingClient] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);

  const reconnectIbkr = async () => {
    if (reconnecting) return;
    let confirmed = false;
    if (isLive) {
      const { port: livePort, peer: livePeer } = liveTarget(isGateway);
      const ok = await confirmDialog({
        title: 'Connect to LIVE IBKR?',
        message:
          `Connect Chrollo to your LIVE real-money IBKR account on port ${livePort}?\n\n` +
          `This hands your single IBKR API session to Chrollo until you disconnect - ` +
          `make sure ${livePeer} is logged into the live account and TradingView isn't using it.`,
        confirmLabel: 'Connect live',
        danger: true,
      });
      if (!ok) return;
      confirmed = true;
    }

    setReconnecting(true);
    try {
      const res = await fetch(`${API_BASE}/ibkr/reconnect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirm: confirmed }),
      });
      if (!res.ok) {
        toast(`Reconnect failed: ${await res.text()}`, { tone: 'danger' });
      }
    } catch (error) {
      toast(`Reconnect error: ${error.message || error}`, { tone: 'danger' });
    } finally {
      setReconnecting(false);
    }
  };

  const disconnectIbkr = async () => {
    if (reconnecting) return;
    setReconnecting(true);
    try {
      const res = await fetch(`${API_BASE}/ibkr/disconnect`, { method: 'POST' });
      if (!res.ok) {
        toast(`Disconnect failed: ${await res.text()}`, { tone: 'danger' });
      }
    } catch (error) {
      toast(`Disconnect error: ${error.message || error}`, { tone: 'danger' });
    } finally {
      setReconnecting(false);
    }
  };

  const toggleIbkrMode = async () => {
    if (switchingMode) return;
    const next = isLive ? 'paper' : 'live';
    if (next === 'live' && !(await confirmLiveMode(isGateway))) {
      return;
    }

    setSwitchingMode(true);
    try {
      const res = await fetch(`${API_BASE}/ibkr/mode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: next, confirm: true }),
      });
      if (!res.ok) {
        toast(`Mode switch failed: ${await res.text()}`, { tone: 'danger' });
      }
    } catch (error) {
      toast(`Mode switch error: ${error.message || error}`, { tone: 'danger' });
    } finally {
      setSwitchingMode(false);
    }
  };

  const toggleIbkrClient = async () => {
    if (switchingClient) return;
    const next = isGateway ? 'tws' : 'gateway';
    let confirmed = false;
    if (isLive) {
      const nextIsGateway = next === 'gateway';
      if (!(await confirmLiveClientSwitch(nextIsGateway))) {
        return;
      }
      confirmed = true;
    }

    setSwitchingClient(true);
    try {
      const res = await fetch(`${API_BASE}/ibkr/client`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ client: next, confirm: confirmed }),
      });
      if (!res.ok) {
        toast(`Client switch failed: ${await res.text()}`, { tone: 'danger' });
      }
    } catch (error) {
      toast(`Client switch error: ${error.message || error}`, { tone: 'danger' });
    } finally {
      setSwitchingClient(false);
    }
  };

  return {
    isLive,
    isGateway,
    isConnected,
    switchingMode,
    switchingClient,
    reconnecting,
    reconnectIbkr,
    disconnectIbkr,
    toggleIbkrMode,
    toggleIbkrClient,
  };
}

// Single source of truth for the IBKR live-account endpoint (port + peer app).
function liveTarget(isGateway) {
  return {
    port: isGateway ? 4001 : 7496,
    peer: isGateway ? 'IB Gateway' : 'TWS',
  };
}

function confirmLiveMode(isGateway) {
  const { port: livePort, peer: livePeer } = liveTarget(isGateway);
  return confirmDialog({
    title: 'Switch to LIVE trading mode?',
    message:
      `This connects to your real-money IBKR account on port ${livePort}. ` +
      `Make sure ${livePeer} is logged into the live account.`,
    confirmLabel: 'Switch to live',
    danger: true,
  });
}

function confirmLiveClientSwitch(isGateway) {
  const { port: livePort, peer: livePeer } = liveTarget(isGateway);
  return confirmDialog({
    title: `Switch LIVE connection to ${livePeer}?`,
    message:
      `Switch Chrollo's LIVE IBKR connection to ${livePeer} on port ${livePort}?\n\n` +
      `This hands your single IBKR API session to Chrollo until you disconnect.`,
    confirmLabel: 'Switch client',
    danger: true,
  });
}

export default useIbkrActions;
