import { useState } from 'react';
import { API_BASE } from '../api';

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
      const ok = window.confirm(
        `Connect Chrollo to your LIVE real-money IBKR account on port ${livePort}?\n\n` +
        `This hands your single IBKR API session to Chrollo until you disconnect - ` +
        `make sure ${livePeer} is logged into the live account and TradingView isn't using it.`,
      );
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
        alert(`Reconnect failed: ${await res.text()}`);
      }
    } catch (error) {
      alert(`Reconnect error: ${error.message || error}`);
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
        alert(`Disconnect failed: ${await res.text()}`);
      }
    } catch (error) {
      alert(`Disconnect error: ${error.message || error}`);
    } finally {
      setReconnecting(false);
    }
  };

  const toggleIbkrMode = async () => {
    if (switchingMode) return;
    const next = isLive ? 'paper' : 'live';
    if (next === 'live' && !confirmLiveMode(isGateway)) {
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
        alert(`Mode switch failed: ${await res.text()}`);
      }
    } catch (error) {
      alert(`Mode switch error: ${error.message || error}`);
    } finally {
      setSwitchingMode(false);
    }
  };

  const toggleIbkrClient = async () => {
    if (switchingClient) return;
    setSwitchingClient(true);
    try {
      const next = isGateway ? 'tws' : 'gateway';
      const res = await fetch(`${API_BASE}/ibkr/client`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ client: next }),
      });
      if (!res.ok) {
        alert(`Client switch failed: ${await res.text()}`);
      }
    } catch (error) {
      alert(`Client switch error: ${error.message || error}`);
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
  return window.confirm(
    'Switch to LIVE trading mode?\n\n' +
    `This connects to your real-money IBKR account on port ${livePort}. ` +
    `Make sure ${livePeer} is logged into the live account.`,
  );
}

export default useIbkrActions;
