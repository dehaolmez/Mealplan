import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { Me, RegisterIn } from "../api/types";
import { LegalLink, LegalModal } from "../components/LegalModal";

type Mode = "login" | "register" | "forgot" | "reset";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (o: { client_id: string; callback: (r: { credential: string }) => void; ux_mode?: string }) => void;
          renderButton: (el: HTMLElement, o: Record<string, unknown>) => void;
        };
      };
    };
  }
}

const EMPTY: RegisterIn = {
  email: "", password: "", display_name: "", accept_terms: false, acknowledge_privacy_notice: false,
  health_data_consent: false, location_consent: false, ai_transfer_consent: false, marketing_consent: false,
  with_sample_data: true,
};

export function AuthPage({ onAuthed, resetToken }: { onAuthed: (me: Me) => void; resetToken: string | null }) {
  const [mode, setMode] = useState<Mode>(resetToken ? "reset" : "login");
  const [form, setForm] = useState<RegisterIn>(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [legal, setLegal] = useState<string | null>(null);
  const [googleId, setGoogleId] = useState<string | null>(null);
  const googleEl = useRef<HTMLDivElement>(null);
  const formRef = useRef(form);
  formRef.current = form;

  const set = <K extends keyof RegisterIn>(k: K, v: RegisterIn[K]) => setForm((f) => ({ ...f, [k]: v }));

  useEffect(() => { api.authConfig().then((c) => setGoogleId(c.google_client_id)).catch(() => {}); }, []);

  // Google Identity Services düğmesi (yalnız istemci kimliği yapılandırılmışsa yüklenir)
  useEffect(() => {
    if (!googleId || !googleEl.current || (mode !== "login" && mode !== "register")) return;
    const render = () => {
      if (!window.google || !googleEl.current) return;
      window.google.accounts.id.initialize({
        client_id: googleId,
        callback: async ({ credential }) => {
          const f = formRef.current;
          await run(() => api.google({
            credential, accept_terms: f.accept_terms, acknowledge_privacy_notice: f.acknowledge_privacy_notice,
            health_data_consent: f.health_data_consent, location_consent: f.location_consent,
            ai_transfer_consent: f.ai_transfer_consent, with_sample_data: f.with_sample_data,
          }), () => { setMode("register"); });
        },
      });
      googleEl.current.innerHTML = "";
      window.google.accounts.id.renderButton(googleEl.current, { theme: "outline", size: "large", text: "continue_with", locale: "tr", width: 300 });
    };
    if (window.google) { render(); return; }
    const s = document.createElement("script");
    s.src = "https://accounts.google.com/gsi/client";
    s.async = true;
    s.onload = render;
    document.head.appendChild(s);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [googleId, mode]);

  const run = async (fn: () => Promise<Me>, onLegalMissing?: () => void) => {
    setBusy(true); setError(null);
    try {
      onAuthed(await fn());
    } catch (e) {
      const msg = (e as Error).message;
      if (onLegalMissing && msg.includes("kullanım koşullarını")) {
        onLegalMissing();
        setError("İlk girişte koşulları kabul edip aydınlatma metnini onaylayın, sonra Google düğmesine tekrar basın.");
      } else setError(msg);
    } finally { setBusy(false); }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (mode === "login") await run(() => api.login(form.email, form.password));
    else if (mode === "register") await run(() => api.register({ ...form, invite_code: form.invite_code || undefined }));
    else if (mode === "reset" && resetToken) {
      await run(() => api.reset(resetToken, form.password));
      history.replaceState(null, "", "#suggest");
    } else if (mode === "forgot") {
      setBusy(true);
      try { await api.forgot(form.email); setInfo("Bu e-postaya kayıtlı bir hesap varsa sıfırlama bağlantısı gönderildi."); }
      catch (e2) { setError((e2 as Error).message); } finally { setBusy(false); }
    }
  };

  return (
    <div className="auth">
      <div className="auth-card card">
        <div className="auth-brand">🐦 Mealbird</div>
        <p className="muted auth-tag">Buzdolabındakini israf etme, alışverişi akıllı yap.</p>

        {(mode === "login" || mode === "register") && (
          <div className="seg seg-wide">
            <button className={mode === "login" ? "on" : ""} onClick={() => { setMode("login"); setError(null); }}>Giriş</button>
            <button className={mode === "register" ? "on" : ""} onClick={() => { setMode("register"); setError(null); }}>Kayıt ol</button>
          </div>
        )}
        {mode === "forgot" && <h2>Şifremi unuttum</h2>}
        {mode === "reset" && <h2>Yeni şifre belirle</h2>}

        <form className="auth-form" onSubmit={submit}>
          {mode !== "reset" && (
            <label className="field"><span>E-posta</span>
              <input type="email" autoComplete="email" required value={form.email} onChange={(e) => set("email", e.target.value)} />
            </label>
          )}
          {mode === "register" && (
            <label className="field"><span>Adın (isteğe bağlı)</span>
              <input autoComplete="given-name" value={form.display_name} onChange={(e) => set("display_name", e.target.value)} />
            </label>
          )}
          {mode !== "forgot" && (
            <label className="field"><span>{mode === "reset" ? "Yeni şifre" : "Şifre"}</span>
              <input type="password" required minLength={mode === "login" ? 1 : 8}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                value={form.password} onChange={(e) => set("password", e.target.value)} />
              {mode !== "login" && <small className="muted">En az 8 karakter</small>}
            </label>
          )}

          {mode === "register" && (
            <>
              <label className="field"><span>Davet kodu (bir haneye katılacaksan)</span>
                <input value={form.invite_code ?? ""} onChange={(e) => set("invite_code", e.target.value.toUpperCase())} placeholder="ör. K7M2QX9P" />
              </label>
              <fieldset className="consents">
                <legend>Zorunlu</legend>
                <label className="check"><input type="checkbox" checked={form.accept_terms} onChange={(e) => set("accept_terms", e.target.checked)} />
                  <span><LegalLink slug="kullanim-kosullari" onOpen={setLegal} />'nı kabul ediyorum.</span></label>
                <label className="check"><input type="checkbox" checked={form.acknowledge_privacy_notice} onChange={(e) => set("acknowledge_privacy_notice", e.target.checked)} />
                  <span><LegalLink slug="aydinlatma" onOpen={setLegal} />'ni okudum.</span></label>
              </fieldset>
              <fieldset className="consents">
                <legend>İsteğe bağlı — <LegalLink slug="acik-riza" onOpen={setLegal}>Açık Rıza Metni</LegalLink></legend>
                <label className="check"><input type="checkbox" checked={form.health_data_consent} onChange={(e) => set("health_data_consent", e.target.checked)} />
                  <span><b>Sağlık verisi:</b> boy, kilo ve hedeflerle kalori ihtiyacının hesaplanması</span></label>
                <label className="check"><input type="checkbox" checked={form.location_consent} onChange={(e) => set("location_consent", e.target.checked)} />
                  <span><b>Konum:</b> ev konumumun (~11 m hassasiyetle) saklanması</span></label>
                <label className="check"><input type="checkbox" checked={form.ai_transfer_consent} onChange={(e) => set("ai_transfer_consent", e.target.checked)} />
                  <span><b>Yapay zekâ:</b> envanter ürün adlarının öneri için yurt dışındaki sağlayıcıya gönderilmesi</span></label>
                <label className="check"><input type="checkbox" checked={form.marketing_consent} onChange={(e) => set("marketing_consent", e.target.checked)} />
                  <span><b>Ticari ileti:</b> kampanya ve yenilik e-postaları</span></label>
              </fieldset>
              <label className="check"><input type="checkbox" checked={form.with_sample_data} onChange={(e) => set("with_sample_data", e.target.checked)} />
                <span>Örnek envanterle başla (denemek için)</span></label>
            </>
          )}

          {error && <p className="form-error" role="alert">{error}</p>}
          {info && <p className="note note-ok">{info}</p>}

          <button className="btn btn-primary" disabled={busy} type="submit">
            {mode === "login" ? "Giriş yap" : mode === "register" ? "Hesap oluştur" : mode === "forgot" ? "Bağlantı gönder" : "Şifreyi kaydet"}
          </button>
        </form>

        {googleId && (mode === "login" || mode === "register") && (
          <div className="google-wrap">
            <span className="muted small">veya</span>
            <div ref={googleEl} />
          </div>
        )}

        <div className="auth-links">
          {mode === "login" && <button className="link" onClick={() => { setMode("forgot"); setError(null); }}>Şifremi unuttum</button>}
          {(mode === "forgot" || mode === "reset") && <button className="link" onClick={() => { setMode("login"); setInfo(null); setError(null); }}>← Girişe dön</button>}
          <LegalLink slug="cerez" onOpen={setLegal}>Çerez politikası</LegalLink>
        </div>
      </div>
      {legal && <LegalModal slug={legal} onClose={() => setLegal(null)} />}
    </div>
  );
}
