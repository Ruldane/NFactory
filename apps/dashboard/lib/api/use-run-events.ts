"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { API_BASE } from "@/lib/api/client";
import { runKeys } from "@/lib/api/queries";
import type { RunEvent } from "@/lib/api/types";
import { EVENT_TYPES, isFinalEvent, mergeEvents } from "@/lib/run-events";

// Events that change what the run page shows beyond the journal itself.
const REFRESHING = new Set([
  "run.started",
  "run.state_changed",
  "run.completed",
  "run.failed",
  "run.cancelled",
  "step.started",
  "step.completed",
  "step.failed",
  "artifact.created",
]);

/**
 * Live event journal of a run, over SSE. The browser's EventSource reconnects on its
 * own and sends Last-Event-ID, so the server replays exactly what was missed.
 */
export function useRunEvents(runId: string): RunEvent[] {
  const client = useQueryClient();
  const [events, setEvents] = useState<RunEvent[]>([]);

  useEffect(() => {
    if (typeof EventSource === "undefined") return; // tests, very old browsers
    const source = new EventSource(`${API_BASE}/runs/${runId}/events`);
    const onEvent = (message: MessageEvent<string>) => {
      const event = JSON.parse(message.data) as RunEvent;
      setEvents((current) => mergeEvents(current, [event]));
      if (REFRESHING.has(event.type)) {
        void client.invalidateQueries({ queryKey: runKeys.all(runId) });
      }
      // The run is over: stop the browser from reconnecting to a finished stream.
      if (isFinalEvent(event)) source.close();
    };
    for (const type of EVENT_TYPES) source.addEventListener(type, onEvent);
    return () => source.close();
  }, [client, runId]);

  return events;
}
