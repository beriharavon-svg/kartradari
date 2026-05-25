"use client";

import React, { useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Search,
  Radar,
  TrendingUp,
  ShieldCheck,
  Bell,
  ScanLine,
  WalletCards,
  ArrowRight,
  Sparkles,
  BarChart3,
  Package,
  Gem,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const cards = [
  {
    name: "Umbreon VMAX Alt Art",
    set: "Evolving Skies",
    type: "PSA 10",
    price: "₺58.400",
    change: "+12.8%",
    score: 94,
    tag: "Yüksek Talep",
  },
  {
    name: "Giratina V Alt Art",
    set: "Lost Origin",
    type: "Raw",
    price: "₺14.900",
    change: "+7.4%",
    score: 88,
    tag: "Chase Card",
  },
  {
    name: "Charizard ex SIR",
    set: "151",
    type: "PSA 10",
    price: "₺22.750",
    change: "+5.1%",
    score: 82,
    tag: "Likidite Yüksek",
  },
];

const sealed = [
  { name: "Terastal Festival Booster Box", roi: "+31%", risk: "Orta", density: "Yüksek" },
  { name: "151 Booster Bundle", roi: "+18%", risk: "Düşük", density: "Çok Yüksek" },
  { name: "Prismatic Evolutions ETB", roi: "+24%", risk: "Orta", density: "Yüksek" },
];

function ScoreRing({ score }: { score: number }) {
  const color =
    score >= 90 ? "text-emerald-400" : score >= 80 ? "text-cyan-400" : "text-yellow-400";

  return (
    <div className="relative flex h-16 w-16 items-center justify-center rounded-full bg-white/5 ring-1 ring-white/10">
      <Radar className={`absolute h-12 w-12 ${color} opacity-20`} />
      <span className={`text-lg font-bold ${color}`}>{score}</span>
    </div>
  );
}

export default function HomePage() {
  const [query, setQuery] = useState("");

  const filteredCards = useMemo(() => {
    if (!query.trim()) return cards;
    return cards.filter((card) =>
      `${card.name} ${card.set} ${card.type}`.toLowerCase().includes(query.toLowerCase())
    );
  }, [query]);

  return (
    <main className="min-h-screen bg-[#070A12] text-white">
      <section className="relative overflow-hidden border-b border-white/10">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(34,211,238,0.23),transparent_35%),radial-gradient(circle_at_top_left,rgba(16,185,129,0.16),transparent_35%)]" />
        <div className="absolute left-1/2 top-24 h-96 w-96 -translate-x-1/2 rounded-full border border-cyan-400/20 opacity-40" />
        <div className="absolute left-1/2 top-24 h-72 w-72 -translate-x-1/2 rounded-full border border-emerald-400/20 opacity-30" />

        <nav className="relative mx-auto flex max-w-7xl items-center justify-between px-6 py-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-cyan-400/10 ring-1 ring-cyan-300/30">
              <Radar className="h-6 w-6 text-cyan-300" />
            </div>
            <div>
              <p className="text-xl font-black tracking-tight">KartRadarı</p>
              <p className="text-xs text-white/50">TCG Market Intelligence</p>
            </div>
          </div>

          <div className="hidden items-center gap-8 text-sm text-white/70 md:flex">
            <a href="#radar" className="hover:text-white">Radar</a>
            <a href="#sealed" className="hover:text-white">Sealed Analiz</a>
            <a href="#portfolio" className="hover:text-white">Portföy</a>
            <a href="#features" className="hover:text-white">Özellikler</a>
          </div>

          <Button className="rounded-2xl bg-white text-black hover:bg-white/90">
            Beta’ya Katıl
          </Button>
        </nav>

        <div className="relative mx-auto grid max-w-7xl gap-10 px-6 pb-20 pt-12 md:grid-cols-[1.1fr_0.9fr] md:items-center md:pt-20">
          <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-300/10 px-4 py-2 text-sm text-cyan-100">
              <Sparkles className="h-4 w-4" /> Türkiye’nin collectible fiyat ve hype radarı
            </div>

            <h1 className="max-w-4xl text-5xl font-black leading-tight tracking-tight md:text-7xl">
              Kart piyasasını sezgiyle değil,{" "}
              <span className="bg-gradient-to-r from-cyan-300 to-emerald-300 bg-clip-text text-transparent">
                veriyle
              </span>{" "}
              takip et.
            </h1>

            <p className="mt-6 max-w-2xl text-lg leading-8 text-white/65">
              Pokémon, One Piece, Yu-Gi-Oh ve slab kartlar için fiyat geçmişi, hype skoru,
              portföy takibi, alarm sistemi ve sealed yatırım analizi.
            </p>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Button size="lg" className="rounded-2xl bg-cyan-300 px-6 text-black hover:bg-cyan-200">
                Kart Ara <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
              <Button size="lg" variant="outline" className="rounded-2xl border-white/15 bg-white/5 px-6 text-white hover:bg-white/10">
                Demo İncele
              </Button>
            </div>

            <div className="mt-10 grid max-w-xl grid-cols-3 gap-4">
              {[
                ["50K+", "Kart Datası"],
                ["24/7", "Fiyat Takibi"],
                ["AI", "Grade Tahmini"],
              ].map(([a, b]) => (
                <div key={b} className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                  <p className="text-2xl font-black">{a}</p>
                  <p className="mt-1 text-xs text-white/50">{b}</p>
                </div>
              ))}
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.7, delay: 0.1 }}>
            <Card id="radar" className="rounded-[2rem] border-white/10 bg-white/[0.06] shadow-2xl shadow-cyan-950/40 backdrop-blur">
              <CardContent className="p-5">
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <p className="text-sm text-white/50">Canlı Radar</p>
                    <h2 className="text-2xl font-black text-white">Yükselen Kartlar</h2>
                  </div>
                  <div className="rounded-2xl bg-emerald-400/10 px-3 py-2 text-sm font-bold text-emerald-300">
                    LIVE
                  </div>
                </div>

                <div className="relative mb-5">
                  <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-white/40" />
                  <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Kart, set veya slab ara..."
                    className="w-full rounded-2xl border border-white/10 bg-black/30 py-4 pl-12 pr-4 text-sm outline-none placeholder:text-white/35 focus:border-cyan-300/50"
                  />
                </div>

                <div className="space-y-3">
                  {filteredCards.map((card) => (
                    <div key={card.name} className="rounded-3xl border border-white/10 bg-black/25 p-4 transition hover:bg-white/[0.06]">
                      <div className="flex items-center justify-between gap-4">
                        <div>
                          <p className="font-bold text-white">{card.name}</p>
                          <p className="mt-1 text-sm text-white/45">{card.set} • {card.type}</p>
                          <div className="mt-3 inline-flex rounded-full bg-cyan-300/10 px-3 py-1 text-xs font-semibold text-cyan-200">
                            {card.tag}
                          </div>
                        </div>
                        <ScoreRing score={card.score} />
                      </div>
                      <div className="mt-4 flex items-center justify-between border-t border-white/10 pt-4">
                        <p className="text-xl font-black">{card.price}</p>
                        <p className="flex items-center gap-1 font-bold text-emerald-300">
                          <TrendingUp className="h-4 w-4" /> {card.change}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </section>

      <section id="features" className="mx-auto max-w-7xl px-6 py-20">
        <div className="mb-10 max-w-2xl">
          <p className="font-bold text-cyan-300">Neden KartRadarı?</p>
          <h2 className="mt-3 text-4xl font-black tracking-tight md:text-5xl">
            KartFiyat’ın üstüne çıkacak sistem
          </h2>
          <p className="mt-4 text-white/60">
            Sadece fiyat göstermek yetmez. Koleksiyoncu gerçek satış, risk, hype ve likidite görmek ister.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          {[
            [BarChart3, "Fiyat Geçmişi", "Raw ve slab kartlar için geçmiş fiyat grafikleri, son satışlar ve trend yönü."],
            [ScanLine, "AI Kart Tarama", "Fotoğrafla kart tanıma, kondisyon kontrolü ve yaklaşık grade tahmini."],
            [Bell, "Fiyat Alarmı", "Belirlediğin hedef fiyata gelince anında bildirim al."],
            [WalletCards, "Koleksiyon Portföyü", "Alış maliyeti, güncel değer, ROI ve toplam kâr/zarar takibi."],
            [ShieldCheck, "Fake Risk Kontrolü", "Şüpheli ilanlar, aşırı ucuz fiyatlar ve sahte riskleri için uyarı sistemi."],
            [Gem, "Hype Score", "YouTube, eBay, sosyal medya ve satış hacmine göre popülerlik skoru."],
          ].map(([Icon, title, desc]) => {
            const FeatureIcon = Icon as typeof BarChart3;
            return (
              <Card key={title as string} className="rounded-3xl border-white/10 bg-white/[0.04]">
                <CardContent className="p-6">
                  <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-2xl bg-cyan-300/10 ring-1 ring-cyan-300/20">
                    <FeatureIcon className="h-6 w-6 text-cyan-300" />
                  </div>
                  <h3 className="text-xl font-black text-white">{title as string}</h3>
                  <p className="mt-3 leading-7 text-white/55">{desc as string}</p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </section>

      <section id="sealed" className="border-y border-white/10 bg-white/[0.03]">
        <div className="mx-auto max-w-7xl px-6 py-20">
          <div className="mb-10 flex flex-col justify-between gap-4 md:flex-row md:items-end">
            <div>
              <p className="font-bold text-emerald-300">Sealed Radar</p>
              <h2 className="mt-3 text-4xl font-black tracking-tight md:text-5xl">
                Booster box ve ETB yatırım paneli
              </h2>
            </div>
            <p className="max-w-xl text-white/55">
              Print risk, chase yoğunluğu, satış hızı ve fiyat trendine göre sealed ürünleri karşılaştır.
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            {sealed.map((item) => (
              <Card key={item.name} className="rounded-3xl border-white/10 bg-black/25">
                <CardContent className="p-6">
                  <Package className="mb-5 h-9 w-9 text-emerald-300" />
                  <h3 className="text-xl font-black text-white">{item.name}</h3>
                  <div className="mt-6 grid grid-cols-3 gap-3 text-center">
                    <div className="rounded-2xl bg-white/[0.05] p-3">
                      <p className="text-xs text-white/45">ROI</p>
                      <p className="mt-1 font-black text-emerald-300">{item.roi}</p>
                    </div>
                    <div className="rounded-2xl bg-white/[0.05] p-3">
                      <p className="text-xs text-white/45">Risk</p>
                      <p className="mt-1 font-black">{item.risk}</p>
                    </div>
                    <div className="rounded-2xl bg-white/[0.05] p-3">
                      <p className="text-xs text-white/45">Chase</p>
                      <p className="mt-1 font-black">{item.density}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section id="portfolio" className="mx-auto max-w-7xl px-6 py-20">
        <div className="grid gap-8 md:grid-cols-[0.9fr_1.1fr] md:items-center">
          <div>
            <p className="font-bold text-cyan-300">Portföy Takibi</p>
            <h2 className="mt-3 text-4xl font-black tracking-tight md:text-5xl">
              Koleksiyonun kaç TL ediyor?
            </h2>
            <p className="mt-5 leading-8 text-white/60">
              Kartlarını ve sealed ürünlerini ekle. Alış fiyatını yaz. KartRadarı sana toplam değer,
              kâr/zarar, risk dağılımı ve en iyi satış zamanını göstersin.
            </p>
            <Button className="mt-8 rounded-2xl bg-white text-black hover:bg-white/90">
              Portföy Oluştur
            </Button>
          </div>

          <Card className="rounded-[2rem] border-white/10 bg-white/[0.05]">
            <CardContent className="p-6">
              <div className="mb-6 flex items-center justify-between">
                <div>
                  <p className="text-sm text-white/45">Toplam Portföy</p>
                  <p className="text-4xl font-black">₺184.250</p>
                </div>
                <div className="rounded-2xl bg-emerald-400/10 px-4 py-2 font-bold text-emerald-300">
                  +26.4%
                </div>
              </div>

              <div className="flex h-52 items-end gap-3 rounded-3xl border border-white/10 bg-black/25 p-5">
                {[36, 58, 42, 74, 66, 91, 82, 100, 88, 112, 124, 140].map((h, i) => (
                  <div
                    key={i}
                    className="flex-1 rounded-t-xl bg-gradient-to-t from-cyan-500/40 to-emerald-300/80"
                    style={{ height: `${h}px` }}
                  />
                ))}
              </div>

              <div className="mt-5 grid grid-cols-3 gap-3">
                <div className="rounded-2xl bg-black/25 p-4">
                  <p className="text-xs text-white/45">Kart</p>
                  <p className="mt-1 font-black">38</p>
                </div>
                <div className="rounded-2xl bg-black/25 p-4">
                  <p className="text-xs text-white/45">Slab</p>
                  <p className="mt-1 font-black">12</p>
                </div>
                <div className="rounded-2xl bg-black/25 p-4">
                  <p className="text-xs text-white/45">Sealed</p>
                  <p className="mt-1 font-black">9</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      <footer className="border-t border-white/10 px-6 py-10">
        <div className="mx-auto flex max-w-7xl flex-col justify-between gap-5 text-sm text-white/45 md:flex-row md:items-center">
          <div className="flex items-center gap-3">
            <Radar className="h-5 w-5 text-cyan-300" />
            <span>KartRadarı.com</span>
          </div>
          <p>Fiyatlar demo amaçlıdır. Gerçek veri entegrasyonu sonraki aşamada yapılır.</p>
        </div>
      </footer>
    </main>
  );
}
