import styles from "./cases.module.css";
import CaseManager from "./CaseManager";

export const dynamic = "force-dynamic";

export default function CasesPage() {
  const serviceConfigured = Boolean(
    process.env.AIML01_CASES_SERVICE_URL &&
    process.env.AIML01_CASES_API_KEY?.length >= 32 &&
    process.env.AIML01_DASHBOARD_ACCESS_CODE?.length >= 16
  );

  if (serviceConfigured) {
    return <CaseManager />;
  }

  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <a href="/" className={styles.back}>
          ← Dashboard overview
        </a>

        <p className={styles.eyebrow}>
          AIML-01 / Analyst workspace
        </p>

        <h1>Fraud Investigation Cases</h1>

        <section className={styles.panel}>
          <h2>Case management is not enabled in this hosted demo</h2>

          <p className={styles.muted}>
            The hosted application supports authenticated XGBoost
            fraud scoring using a frozen historical Feast feature snapshot.
          </p>

          <p className={styles.muted}>
            Persistent investigation cases require a separate authenticated
            case-management service. That service is not configured here,
            so fraud alerts are not saved as case records.
          </p>

          <p className={styles.muted}>
            The original case-management interface and API remain
            preserved in the project repository.
          </p>

          <a href="/scoring">
            Open transaction fraud scoring
          </a>
        </section>
      </div>
    </main>
  );
}
