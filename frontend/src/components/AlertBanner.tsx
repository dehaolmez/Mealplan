import { useEffect, useState } from "react";
import type { Alerts } from "../api/types";

const NOTIFIED_KEY = "meall:lastNotified";

/** SKT uyarıları: uygulama içi şerit + (izin verildiyse) günde bir tarayıcı bildirimi. */
export function AlertBanner({ alerts, onOpen }: { alerts: Alerts | null; onOpen: () => void }) {
  const [permission, setPermission] = useState<NotificationPermission | "unsupported">(
    typeof Notification === "undefined" ? "unsupported" : Notification.permission,
  );
  const urgent = alerts ? alerts.expired + alerts.critical : 0;

  useEffect(() => {
    if (!alerts || urgent === 0 || permission !== "granted") return;
    const today = new Date().toDateString();
    let last: string | null = null;
    try { last = localStorage.getItem(NOTIFIED_KEY); } catch { /* depolama kapalı */ }
    if (last === today) return;
    const top = alerts.alerts.slice(0, 3).map((a) => a.message).join("\n");
    new Notification("Meall: bozulmak üzere olan ürünler", { body: top });
    try { localStorage.setItem(NOTIFIED_KEY, today); } catch { /* yoksay */ }
  }, [alerts, urgent, permission]);

  if (!alerts || alerts.alerts.length === 0) return null;
  const top = alerts.alerts[0];
  return (
    <div className={`alert-banner ${urgent ? "alert-urgent" : ""}`}>
      <button className="alert-main" onClick={onOpen}>
        <span className="alert-emoji">{top.emoji}</span>
        <span>
          <b>{urgent ? `${urgent} ürün acil` : `${alerts.warning} ürün yakında bozulacak`}</b>
          <small>{top.message}</small>
        </span>
      </button>
      {permission === "default" && (
        <button className="btn btn-ghost btn-sm" onClick={async () => setPermission(await Notification.requestPermission())}>
          🔔 Bildirim
        </button>
      )}
    </div>
  );
}
