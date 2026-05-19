import { useEffect, useState } from "react";

import { api, BedolagaOverviewResponse } from "../api/client";
import { useI18n } from "../localization";

export function BedolagaPage() {
  const { t } = useI18n();
  const [data, setData] = useState<BedolagaOverviewResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const payload = await api.getBedolagaOverview();
        if (cancelled) {
          return;
        }
        setData(payload);
        setError("");
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load Bedolaga");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="page-stack">
      <section className="panel">
        <h1>Bedolaga</h1>
        {loading ? <p className="muted">{t("common.loading")}</p> : null}
        {error ? <div className="error-box">{error}</div> : null}
        {!loading && !error ? (
          <div className="detail-grid">
            <div className="panel">
              <h2>Connection</h2>
              <p className="muted">{data?.enabled ? "enabled" : "disabled"}</p>
              <code>{data?.base_url || t("common.notAvailable")}</code>
            </div>
            <div className="panel">
              <h2>Metrics</h2>
              <pre className="code-block">{JSON.stringify(data?.metrics || {}, null, 2)}</pre>
            </div>
            <div className="panel">
              <h2>Clients</h2>
              <pre className="code-block">{JSON.stringify(data?.clients || [], null, 2)}</pre>
            </div>
            <div className="panel">
              <h2>Errors</h2>
              <pre className="code-block">{JSON.stringify(data?.errors || [], null, 2)}</pre>
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}
