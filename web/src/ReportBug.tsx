// Report a bug (docs/design/ui.md, Report a bug): the report the server builds
// (lado.bug_report, the same as `lado bug-report` prints) with this page's browser line,
// loaded anew on each visit, and GitHub's new issue form with it. Nothing is sent from here:
// the link opens the form, and only the human's submit there makes the issue.
import { useEffect, useState } from "react";

import { ApiError, getBugReport, type BugReport } from "./api";
import { useCopy } from "./Copy";
import { useTitle } from "./Shell";
import { browserLine, GITHUB } from "./SystemPanel";

const PRIVATE_REPORT = `${GITHUB}/security/advisories/new`;

const messageOf = (error: unknown) => (error instanceof ApiError ? error.message : String(error));

export function ReportBug() {
  useTitle("Report a bug");
  const [report, setReport] = useState<BugReport | { error: string } | null>(null);
  const { note, copy } = useCopy();
  useEffect(() => {
    let current = true;
    getBugReport(browserLine(navigator.userAgent)).then(
      (found) => current && setReport(found),
      (error: unknown) => current && setReport({ error: messageOf(error) }),
    );
    return () => {
      current = false;
    };
  }, []);
  return (
    <div className="report-bug">
      <p>
        This opens a new <strong>public</strong> issue on github.com/ladohq/lado with the text below. Nothing is
        sent until you submit it there, and you can edit or delete any of it on GitHub first. It holds no paths,
        session or repository names, nor message texts. For a vulnerability, use{" "}
        <a href={PRIVATE_REPORT} target="_blank" rel="noreferrer">
          private reporting
        </a>{" "}
        instead.
      </p>
      {report === null ? (
        <p className="muted">Loading…</p>
      ) : "error" in report ? (
        <p className="problem" role="alert">
          {report.error}
        </p>
      ) : (
        <>
          <pre className="log">{report.text}</pre>
          <p className="report-bug-actions">
            <a className="primary" href={report.url} target="_blank" rel="noreferrer">
              Open a new issue on GitHub ↗
            </a>
            <button type="button" className="quiet" onClick={() => void copy(report.text, "Report copied")}>
              Copy text
            </button>
            <span role="status" className="row-note">
              {note}
            </span>
          </p>
        </>
      )}
    </div>
  );
}
