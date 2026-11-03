"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";

export function QueryProvider({ children }: { children: ReactNode }) {
  // Lazy init: one client per browser session, never shared across server requests.
  const [client] = useState(
    () => new QueryClient({ defaultOptions: { queries: { staleTime: 5_000 } } }),
  );
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
