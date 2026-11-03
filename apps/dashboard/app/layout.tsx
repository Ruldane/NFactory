import type { Metadata } from "next";
import { Fraunces, Instrument_Sans, JetBrains_Mono } from "next/font/google";

import { QueryProvider } from "@/components/shell/query-provider";
import { Sidebar } from "@/components/shell/sidebar";

import "./globals.css";

const fraunces = Fraunces({ variable: "--font-fraunces", subsets: ["latin"], axes: ["SOFT", "opsz"] });
const instrument = Instrument_Sans({ variable: "--font-instrument", subsets: ["latin"] });
const jetbrains = JetBrains_Mono({ variable: "--font-jetbrains", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "NFactory",
  description: "Usine logicielle IA local-first : de l'idée au projet testé.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="fr"
      className={`${fraunces.variable} ${instrument.variable} ${jetbrains.variable} antialiased`}
    >
      <body className="min-h-dvh md:flex">
        <Sidebar />
        <QueryProvider>
          <main className="min-w-0 flex-1 px-6 py-10 md:px-12 lg:px-16">
            <div className="mx-auto max-w-6xl">{children}</div>
          </main>
        </QueryProvider>
      </body>
    </html>
  );
}
