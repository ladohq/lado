// Open LADO on another device (docs/design/ui.md, Open on another device): the system
// panel's QR-code icon opens this dialog, which asks the server for the link each time it
// opens (GET /api/access) and shows it as a QR code to scan, its token cut, with Copy link;
// or, without a link, why there is none and what makes one. New link… asks first, then
// makes a new token (POST /api/access/new-token): every other browser is logged out, and
// the answer sets this one's cookie, so this page goes on.
import qrcode from "qrcode-generator";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { ApiError, getAccess, newAccessToken, type AccessInfo } from "./api";
import { useCopy } from "./Copy";

const TITLE = "Open LADO on another device";
const NAME = "<this computer's name>";
const OPEN_COMMAND = "lado server stop && lado ui --host 0.0.0.0";

const messageOf = (error: unknown) => (error instanceof ApiError ? error.message : String(error));

// The link with its token cut to its first and last four characters; a token too short
// to cut (tests) as it is.
export function cutToken(link: string): string {
  const at = link.indexOf("token=");
  if (at === -1) return link;
  const token = link.slice(at + "token=".length);
  if (token.length <= 8) return link;
  return `${link.slice(0, at)}token=${token.slice(0, 4)}…${token.slice(-4)}`;
}

// The text as a QR code: black modules on white with a 4-module quiet zone, in both themes,
// as a phone's camera needs.
export function QrCode({ text }: { text: string }) {
  const code = qrcode(0, "M");
  code.addData(text);
  code.make();
  const count = code.getModuleCount();
  const size = count + 8;
  const cells: ReactNode[] = [];
  for (let row = 0; row < count; row++) {
    for (let col = 0; col < count; col++) {
      if (code.isDark(row, col)) cells.push(<rect key={`${row}-${col}`} x={col + 4} y={row + 4} width={1} height={1} />);
    }
  }
  return (
    <svg className="share-qr" viewBox={`0 0 ${size} ${size}`} role="img" aria-label="QR code of the link" shapeRendering="crispEdges">
      <rect width={size} height={size} fill="#fff" />
      <g fill="#000">{cells}</g>
    </svg>
  );
}

export function ShareDialog({ onClose }: { onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [access, setAccess] = useState<AccessInfo | { error: string } | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  const { note, copy: copied } = useCopy();
  const [uncopied, setUncopied] = useState<string | null>(null); // to copy by hand
  const copy = async (text: string, said: string) => {
    const done = await copied(text, said);
    setUncopied(done ? null : text);
    return done;
  };
  useEffect(() => {
    dialog.current?.showModal();
    let current = true;
    getAccess().then(
      (found) => current && setAccess(found),
      (error: unknown) => current && setAccess({ error: messageOf(error) }),
    );
    return () => {
      current = false;
    };
  }, []);
  const renew = async () => {
    setBusy(true);
    setRefused(null);
    try {
      setAccess(await newAccessToken());
      setConfirming(false);
    } catch (error) {
      setRefused(messageOf(error));
    } finally {
      setBusy(false);
    }
  };
  const found = access !== null && "port" in access ? access : null;
  const title = confirming ? "Make a new link?" : TITLE;
  const status = (
    <span role="status" className="row-note">
      {note}
    </span>
  );
  return (
    <dialog
      ref={dialog}
      className="question-dialog share-dialog"
      aria-label={TITLE}
      onCancel={(event) => {
        event.preventDefault();
        if (busy) return;
        if (confirming) setConfirming(false);
        else onClose();
      }}
    >
      <h3>{title}</h3>
      {confirming ? (
        <>
          <p>
            Everyone who opened LADO with the current link — other browsers, phones, people you sent it to — is
            logged out at once. This browser stays in.
          </p>
          <p className="muted share-small">
            The same as <code>lado server --new-token</code>, without a restart.
          </p>
          {refused && (
            <p className="problem" role="alert">
              {refused}
            </p>
          )}
          <div className="question-buttons">
            <button type="button" className="quiet" disabled={busy} onClick={() => setConfirming(false)}>
              Cancel
            </button>
            <button type="button" className="danger" disabled={busy} onClick={() => void renew()}>
              {busy ? "Making…" : "Make a new link"}
            </button>
          </div>
        </>
      ) : (
        <>
          {access === null && <p className="muted">Loading…</p>}
          {access !== null && "error" in access && (
            <p className="problem" role="alert">
              {access.error}
            </p>
          )}
          {found?.link && (
            <>
              <p className="problem share-warning">
                This link gives <strong>full access</strong>: sessions, agents' terminals, commands as you. It travels
                unencrypted (plain HTTP): share it only on a network you trust.
              </p>
              <div className="share-body">
                <QrCode text={found.link} />
                <div className="share-link-column">
                  <p className="muted">Scan it with the phone's camera, or send the link.</p>
                  <code className="command share-link">{cutToken(found.link)}</code>
                  <span className="share-copy">
                    <button type="button" className="primary" onClick={() => void copy(found.link!, "Link copied")}>
                      Copy link
                    </button>
                    {status}
                  </span>
                </div>
              </div>
              <p className="muted share-small">Anyone who opened LADO with this link stays in until you make a new one.</p>
            </>
          )}
          {found && !found.link && <NoLink access={found} />}
          {uncopied && (
            <p className="share-uncopied">
              <span className="muted">The browser did not copy it: select it and press ⌘C / Ctrl+C.</span>
              <textarea readOnly aria-label="Text to copy" value={uncopied} rows={uncopied.split("\n").length} />
            </p>
          )}
          <div className="question-buttons">
            {found && !found.link && <CopyHow access={found} copy={copy} />}
            {found && !found.link && status}
            <button type="button" className="quiet" disabled={!found} onClick={() => setConfirming(true)}>
              New link…
            </button>
            <button type="button" className="quiet" onClick={onClose}>
              Close
            </button>
          </div>
        </>
      )}
    </dialog>
  );
}

// Why there is no link, and what makes one.
function NoLink({ access }: { access: AccessInfo }) {
  if (access.reason === "loopback" && !access.container) {
    return (
      <>
        <p>This LADO server listens on 127.0.0.1 only: other devices cannot reach it.</p>
        <p>To open it from a phone or another computer on your network, restart the server open to the network:</p>
        <code className="command">{OPEN_COMMAND}</code>
        <p className="muted share-small">The sessions keep running; open tabs reconnect.</p>
      </>
    );
  }
  if (access.reason === "loopback") {
    return (
      <>
        <p>LADO is reachable from this computer only (its port is published on 127.0.0.1).</p>
        <p>
          To open it from a phone or another computer on your network, set in <code>.env</code> next to compose.yaml,
          then run <code>docker compose up -d</code>:
        </p>
        <code className="command share-lines">{`LADO_LISTEN=0.0.0.0\nLADO_PUBLIC_HOST=${NAME}`}</code>
      </>
    );
  }
  if (access.reason === "no-address") {
    return (
      <>
        <p>
          LADO is open to your network (LADO_LISTEN={access.listen}), but inside its container it cannot learn this
          computer's address for the link.
        </p>
        <p>
          Set the name or address other devices reach this computer by in <code>.env</code>, then run{" "}
          <code>docker compose up -d</code>:
        </p>
        <code className="command">{`LADO_PUBLIC_HOST=${NAME}`}</code>
        <p className="muted share-small">
          Or publish on one address instead: <code>LADO_LISTEN=&lt;address&gt;</code>.
        </p>
      </>
    );
  }
  return <p>{access.note}</p>;
}

// The command or the .env lines of `NoLink`, to copy.
function CopyHow({ access, copy }: { access: AccessInfo; copy: (text: string, copied: string) => Promise<boolean> }) {
  if (access.reason !== "loopback") return null;
  if (!access.container) {
    return (
      <button type="button" className="quiet" onClick={() => void copy(OPEN_COMMAND, "Command copied")}>
        Copy command
      </button>
    );
  }
  return (
    <button
      type="button"
      className="quiet"
      onClick={() => void copy(`LADO_LISTEN=0.0.0.0\nLADO_PUBLIC_HOST=${NAME}`, "Lines copied")}
    >
      Copy lines
    </button>
  );
}
