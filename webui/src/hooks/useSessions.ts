import { useCallback, useEffect, useRef, useState } from "react";

import { useClient } from "@/providers/ClientProvider";
import i18n from "@/i18n";
import {
  ApiError,
  deleteSession as apiDeleteSession,
  fetchWebuiThread,
  listSessions,
} from "@/lib/api";
import { deriveTitle } from "@/lib/format";
import type { ChatSummary, UIMessage } from "@/lib/types";

const EMPTY_MESSAGES: UIMessage[] = [];

/** Sidebar state: fetches the full session list and exposes create / delete actions. */
export function useSessions(): {
  sessions: ChatSummary[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  createChat: () => Promise<string>;
  deleteChat: (key: string) => Promise<void>;
} {
  const { client, token } = useClient();
  const [sessions, setSessions] = useState<ChatSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const tokenRef = useRef(token);
  const optimisticSessionsRef = useRef<Map<string, ChatSummary>>(new Map());
  const locallyDeletedKeysRef = useRef<Set<string>>(new Set());
  tokenRef.current = token;

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      const rows = await listSessions(tokenRef.current);
      const merged = [...rows];
      const seen = new Set(merged.map((row) => row.key));
      for (const [key, optimistic] of optimisticSessionsRef.current) {
        if (seen.has(key)) {
          optimisticSessionsRef.current.delete(key);
          continue;
        }
        merged.push(optimistic);
        seen.add(key);
      }
      const defaultChatId = client.defaultChatId;
      if (defaultChatId) {
        const defaultKey = `websocket:${defaultChatId}`;
        if (!seen.has(defaultKey) && !locallyDeletedKeysRef.current.has(defaultKey)) {
          const now = new Date().toISOString();
          merged.unshift({
            key: defaultKey,
            channel: "websocket",
            chatId: defaultChatId,
            createdAt: now,
            updatedAt: now,
            title: "",
            preview: "",
          });
        }
      }
      setSessions(merged);
      setError(null);
    } catch (e) {
      const msg =
        e instanceof ApiError ? `HTTP ${e.status}` : (e as Error).message;
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    return client.onSessionUpdate(() => {
      void refresh();
    });
  }, [client, refresh]);

  const createChat = useCallback(async (): Promise<string> => {
    const chatId = await client.newChat();
    const key = `websocket:${chatId}`;
    const optimistic: ChatSummary = {
      key,
      channel: "websocket",
      chatId,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      title: "",
      preview: "",
    };
    locallyDeletedKeysRef.current.delete(key);
    optimisticSessionsRef.current.set(key, optimistic);
    // Optimistic insert; a subsequent refresh will replace it with the
    // authoritative row once the server persists the session.
    setSessions((prev) => [
      optimistic,
      ...prev.filter((s) => s.key !== key),
    ]);
    return chatId;
  }, [client]);

  const deleteChat = useCallback(
    async (key: string) => {
      await apiDeleteSession(tokenRef.current, key);
      optimisticSessionsRef.current.delete(key);
      locallyDeletedKeysRef.current.add(key);
      setSessions((prev) => prev.filter((s) => s.key !== key));
    },
    [],
  );

  return { sessions, loading, error, refresh, createChat, deleteChat };
}

/** Lazy-load a session's on-disk messages the first time the UI displays it. */
export function useSessionHistory(key: string | null): {
  messages: UIMessage[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
  version: number;
  /** ``true`` when the replayed transcript ends with a trace row (turn still in flight). */
  hasPendingToolCalls: boolean;
} {
  const { token } = useClient();
  const [refreshSeq, setRefreshSeq] = useState(0);
  const refresh = useCallback(() => {
    setRefreshSeq((value) => value + 1);
  }, []);
  const [state, setState] = useState<{
    key: string | null;
    messages: UIMessage[];
    loading: boolean;
    error: string | null;
    hasPendingToolCalls: boolean;
    version: number;
  }>({
    key: null,
    messages: [],
    loading: false,
    error: null,
    hasPendingToolCalls: false,
    version: 0,
  });

  useEffect(() => {
    if (!key) {
      setState({
        key: null,
        messages: [],
        loading: false,
        error: null,
        hasPendingToolCalls: false,
        version: 0,
      });
      return;
    }
    let cancelled = false;
    // Mark the new key as loading immediately so callers never see stale
    // messages from the previous session during the render right after a switch.
    setState((prev) => prev.key === key
      ? { ...prev, loading: true, error: null }
      : {
          key,
          messages: [],
          loading: true,
          error: null,
          hasPendingToolCalls: false,
          version: 0,
        });
    (async () => {
      try {
        const body = await fetchWebuiThread(token, key);
        if (cancelled) return;
        if (!body?.messages?.length) {
          setState((prev) => ({
            key,
            messages: [],
            loading: false,
            error: null,
            hasPendingToolCalls: false,
            version: prev.key === key ? prev.version + 1 : 1,
          }));
          return;
        }
        const ui: UIMessage[] = body.messages.map((m, idx) => ({
          ...m,
          id: m.id ?? `hist-${idx}`,
          createdAt: typeof m.createdAt === "number" ? m.createdAt : Date.now(),
        }));
        const last = ui[ui.length - 1];
        const hasPending = last?.kind === "trace";
        setState((prev) => ({
          key,
          messages: ui,
          loading: false,
          error: null,
          hasPendingToolCalls: hasPending,
          version: prev.key === key ? prev.version + 1 : 1,
        }));
      } catch (e) {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 404) {
          setState((prev) => ({
            key,
            messages: [],
            loading: false,
            error: null,
            hasPendingToolCalls: false,
            version: prev.key === key ? prev.version + 1 : 1,
          }));
        } else {
          setState((prev) => ({
            key,
            messages: [],
            loading: false,
            error: (e as Error).message,
            hasPendingToolCalls: false,
            version: prev.key === key ? prev.version : 0,
          }));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [key, token, refreshSeq]);

  if (!key) {
    return {
      messages: EMPTY_MESSAGES,
      loading: false,
      error: null,
      refresh,
      version: 0,
      hasPendingToolCalls: false,
    };
  }

  // Even before the effect above commits its loading state, never surface the
  // previous session's payload for a brand-new key.
  if (state.key !== key) {
    return {
      messages: EMPTY_MESSAGES,
      loading: true,
      error: null,
      refresh,
      version: 0,
      hasPendingToolCalls: false,
    };
  }

  return {
    messages: state.messages,
    loading: state.loading,
    error: state.error,
    refresh,
    version: state.version,
    hasPendingToolCalls: state.hasPendingToolCalls,
  };
}

/** Produce a compact display title for a session. */
export function sessionTitle(
  session: ChatSummary,
  firstUserMessage?: string,
): string {
  return deriveTitle(
    session.title || firstUserMessage || session.preview,
    i18n.t("chat.newChat"),
  );
}
