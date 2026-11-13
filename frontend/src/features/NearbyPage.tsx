import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { api } from "../api/client";
import type { Household, Nearby, Place } from "../api/types";
import { KIND_LABELS } from "../lib";
import { ErrorBox, Empty, Section } from "../components/ui";
import { useToast } from "../components/Toast";


const RADII = [500, 1000, 2000, 5000];
const TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";

const fmtDistance = (m: number) => (m < 1000 ? `${m} m` : `${(m / 1000).toFixed(1).replace(".", ",")} km`);

function pin(color: string, label: string) {
  return L.divIcon({
    className: "map-pin",
    html: `<span style="--pin:${color}">${label}</span>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
  });
}

/** Konum tabanlı yakın marketler: OpenStreetMap verisi + Leaflet harita. */
export function NearbyPage() {
  const toast = useToast();
  const [household, setHousehold] = useState<Household | null>(null);
  const [pos, setPos] = useState<{ lat: number; lon: number } | null>(null);
  const [radius, setRadius] = useState(2000);
  const [onlyChains, setOnlyChains] = useState(true);
  const [data, setData] = useState<Nearby | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);

  const mapEl = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);
  const markers = useRef(new Map<number, L.Marker>());

  useEffect(() => {
    api.household().then((h) => {
      setHousehold(h);
      setRadius(h.search_radius_m);
      if (h.home_lat != null && h.home_lon != null) setPos({ lat: h.home_lat, lon: h.home_lon });
    }).catch((e) => setError((e as Error).message));
  }, []);

  // Haritayı bir kez kur
  useEffect(() => {
    if (!mapEl.current || map.current) return;
    map.current = L.map(mapEl.current, { zoomControl: true }).setView([39.0, 35.2], 5);
    L.tileLayer(TILE_URL, {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> katkıcıları',
    }).addTo(map.current);
    layer.current = L.layerGroup().addTo(map.current);
    map.current.on("click", (e: L.LeafletMouseEvent) => setPos({ lat: e.latlng.lat, lon: e.latlng.lng }));
    return () => { map.current?.remove(); map.current = null; };
  }, []);

  // Konum / yarıçap / filtre değişince ara
  useEffect(() => {
    if (!pos) return;
    let cancelled = false;
    setLoading(true);
    api.nearby({ lat: pos.lat, lon: pos.lon, radius_m: radius, only_chains: onlyChains })
      .then((d) => { if (!cancelled) { setData(d); setError(null); } })
      .catch((e) => { if (!cancelled) { setError((e as Error).message); setData(null); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [pos, radius, onlyChains]);

  // Haritayı sonuçlarla çiz
  useEffect(() => {
    const m = map.current, g = layer.current;
    if (!m || !g || !pos) return;
    g.clearLayers();
    markers.current.clear();
    L.circle([pos.lat, pos.lon], { radius, color: "#15803d", weight: 1, fillOpacity: 0.05 }).addTo(g);
    L.marker([pos.lat, pos.lon], { icon: pin("#111827", "🏠") }).addTo(g).bindTooltip("Konum");
    for (const p of data?.places ?? []) {
      const color = p.chain?.color ?? "#64748b";
      const label = p.chain ? p.chain.name.slice(0, 2).toUpperCase() : "•";
      const marker = L.marker([p.lat, p.lon], { icon: pin(color, label) })
        .addTo(g)
        .bindPopup(`<b>${escapeHtml(p.name)}</b><br>${fmtDistance(p.distance_m)}${p.address ? "<br>" + escapeHtml(p.address) : ""}`);
      marker.on("click", () => setSelected(p.id));
      markers.current.set(p.id, marker);
    }
    m.fitBounds(L.latLng(pos.lat, pos.lon).toBounds(radius * 2.2), { animate: false });
  }, [data, pos, radius]);

  const locate = () => {
    if (!("geolocation" in navigator)) { toast("Tarayıcı konum desteklemiyor", "err"); return; }
    navigator.geolocation.getCurrentPosition(
      (g) => setPos({ lat: g.coords.latitude, lon: g.coords.longitude }),
      (e) => toast(e.code === e.PERMISSION_DENIED ? "Konum izni verilmedi — haritaya dokunarak konum seçebilirsin" : "Konum alınamadı", "err"),
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 300_000 },
    );
  };

  const saveHome = async () => {
    if (!pos) return;
    try {
      const h = await api.updateHousehold({ home_lat: pos.lat, home_lon: pos.lon, search_radius_m: radius });
      setHousehold(h);
      toast("Ev konumu kaydedildi (~100 m hassasiyetle)");
    } catch (e) { toast((e as Error).message, "err"); }
  };

  const focus = (p: Place) => {
    setSelected(p.id);
    const mk = markers.current.get(p.id);
    if (mk && map.current) { map.current.setView(mk.getLatLng(), 17); mk.openPopup(); }
  };

  const homeSaved = household?.home_lat != null && pos &&
    Math.abs(household.home_lat - pos.lat) < 0.001 && Math.abs((household.home_lon ?? 0) - pos.lon) < 0.001;

  return (
    <div className="page">
      <div className="page-intro">
        <h1>Yakındaki marketler</h1>
        <p className="muted">Konumunu paylaş ya da haritaya dokun. Veriler OpenStreetMap'ten gelir.</p>
      </div>

      <div className="toolbar">
        <button className="btn btn-primary" onClick={locate}>📍 Konumumu bul</button>
        <div className="seg">
          {RADII.map((r) => (
            <button key={r} className={radius === r ? "on" : ""} onClick={() => setRadius(r)}>{fmtDistance(r)}</button>
          ))}
        </div>
        <label className="switch">
          <input type="checkbox" checked={!onlyChains} onChange={(e) => setOnlyChains(!e.target.checked)} />
          <span>Bakkalları da göster</span>
        </label>
      </div>

      <div className="map-wrap">
        <div ref={mapEl} className="map" aria-label="Harita" />
        {loading && <div className="map-loading">Aranıyor…</div>}
      </div>

      {pos && !homeSaved && (
        <button className="btn btn-ghost" onClick={saveHome}>🏠 Bu konumu ev konumu olarak kaydet</button>
      )}
      {error && <ErrorBox message={error} />}
      {!pos && <Empty icon="🗺️">Konum seçilmedi.</Empty>}

      {data && (
        <>
          <Section title={`Zincirler (${data.chains.length})`}>
            {data.chains.length === 0 && <p className="muted">Bu yarıçapta zincir market bulunamadı.</p>}
            <div className="chain-summary">
              {data.chains.map((c) => (
                <button key={c.chain.id} className="chain-chip" style={{ ["--chain" as string]: c.chain.color }}
                  onClick={() => { const p = data.places.find((x) => x.id === c.nearest_place_id); if (p) focus(p); }}>
                  <b>{c.chain.name}</b>
                  <span>{c.count} şube · en yakın {fmtDistance(c.nearest_m)}</span>
                  <small>{c.chain.has_prices ? "💰 fiyat verisi var" : "fiyat verisi yok"}</small>
                </button>
              ))}
            </div>
          </Section>

          <Section title={`Şubeler (${data.places.length})`}>
            <ul className="place-list">
              {data.places.map((p) => (
                <li key={p.id} className={selected === p.id ? "on" : ""}>
                  <button className="place-main" onClick={() => focus(p)}>
                    <span className="place-dot" style={{ background: p.chain?.color ?? "#64748b" }} />
                    <span>
                      <b>{p.name}</b>
                      <small className="muted">
                        {p.chain ? KIND_LABELS[p.chain.kind] : "Bağımsız"}{p.address && ` · ${p.address}`}
                        {p.opening_hours && ` · 🕘 ${p.opening_hours}`}
                      </small>
                    </span>
                    <span className="place-dist">{fmtDistance(p.distance_m)}</span>
                  </button>
                  <a className="btn btn-ghost btn-sm" target="_blank" rel="noreferrer"
                    href={`https://www.openstreetmap.org/directions?engine=fossgis_osrm_foot&route=${data.lat}%2C${data.lon}%3B${p.lat}%2C${p.lon}`}>
                    Yol tarifi
                  </a>
                </li>
              ))}
            </ul>
            <p className="muted small">
              {data.from_cache ? "Önbellekten (24 saat)." : "Az önce güncellendi."} Eksik/yanlış şube mi var?
              OpenStreetMap'te düzeltebilirsin.
            </p>
          </Section>
        </>
      )}
    </div>
  );
}

function escapeHtml(s: string) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}
