// The Kits page (docs/design/ui.md, Kits): the installed kits, the kits the marketplaces
// offer and the updates, with the marketplaces beside them on every tab. What a kit is, what
// an install or update would do and who uses a kit all come from the core; the page decides
// nothing the core decides. Nothing goes to the network on its own: updates are checked and
// marketplaces fetched only with a button.
import { useEffect, useId, useRef, useState, type ChangeEvent, type ReactNode } from "react";
import { Link, useParams } from "react-router";

import {
  ApiError,
  addMarketplace,
  checkUpdates,
  getRemovePreview,
  installKit,
  planKit,
  planKitUpdate,
  removeKit,
  removeMarketplace,
  setMarketplaceEnabled,
  updateKit,
  updateMarketplaces,
  type InstalledKitInfo,
  type KitUsersInfo,
  type MarketplaceInfo,
  type OfferInfo,
  type OutdatedInfo,
  type PlanAsk,
  type PlanInfo,
} from "./api";
import { KitCard, type Source, type SourceKind } from "./KitCard";
import type { RowMenuItem } from "./RowMenu";
import { PlanContents } from "./KitPlan";
import { useLive, useLiveStore, type ListLoaded } from "./live";
import { NotFound } from "./pages";
import { storedKitsSource, storeKitsSource } from "./prefs";
import { useTitle } from "./Shell";

const TABS = ["installed", "available", "updates"] as const;
type KitsTab = (typeof TABS)[number];
const isKitsTab = (tab: string): tab is KitsTab => (TABS as readonly string[]).includes(tab);

const ALL = "all";
const marketSource = (name: string) => `marketplace:${name}`;

const messageOf = (error: unknown) => (error instanceof ApiError ? error.message : String(error));
const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? "" : "s"}`;
const itemsOf = <T,>(loaded: ListLoaded<T> | undefined): T[] =>
  loaded && "items" in loaded ? loaded.items : [];
const time = (at: Date) => at.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

// The dot of a kit from a marketplace: the official one's, or any other's (also one gone).
const marketKind = (name: string, markets: MarketplaceInfo[] | null): SourceKind =>
  markets?.find((m) => m.name === name)?.official ? "official" : "marketplace";

// Where an installed kit comes from: its marketplace ("<name> (removed)" when that one is
// gone, counted from the two lists), git, folder or built-in; its dot and its chip.
function sourceOf(kit: InstalledKitInfo, markets: MarketplaceInfo[] | null): Source & { chip: string } {
  if (kit.kind === "git" && kit.marketplace) {
    const gone = markets !== null && !markets.some((m) => m.name === kit.marketplace);
    return {
      label: gone ? `${kit.marketplace} (removed)` : kit.marketplace,
      kind: marketKind(kit.marketplace, markets),
      chip: marketSource(kit.marketplace),
    };
  }
  return { label: kit.kind, kind: kit.kind, chip: kit.kind };
}

type Dialog =
  | { kind: "add"; ask?: PlanAsk }
  | { kind: "update"; kit: InstalledKitInfo; tag: string | null }
  | { kind: "remove"; kit: InstalledKitInfo }
  | { kind: "add-marketplace" }
  | { kind: "remove-marketplace"; market: MarketplaceInfo };

type Checked = { at: Date; rows: OutdatedInfo[] };

// /kits, /kits/installed, /kits/available, /kits/updates; another tab is Not found.
export function Kits() {
  const { tab = "installed" } = useParams();
  return isKitsTab(tab) ? <KitsPage tab={tab} /> : <NotFound />;
}

function KitsPage({ tab }: { tab: KitsTab }) {
  useTitle("Kits");
  const live = useLiveStore();
  useEffect(() => live.watch("kits"), [live]);
  const loaded = useLive().kits;
  const [query, setQuery] = useState("");
  const [source, setSource] = useState(storedKitsSource);
  const [checked, setChecked] = useState<Checked | null>(null);
  const [checking, setChecking] = useState(false);
  const [checkProblem, setCheckProblem] = useState<string | null>(null);
  const [dialog, setDialog] = useState<Dialog | null>(null);
  const [updating, setUpdating] = useState(false);
  const [marketErrors, setMarketErrors] = useState<Record<string, string>>({});

  const installed = itemsOf(loaded?.installed);
  const marketList = loaded?.marketplaces;
  const markets = itemsOf(marketList);
  // The marketplaces when their list loaded: only then is a kit's one known to be gone.
  const knownMarkets = marketList && "items" in marketList ? markets : null;
  const offers = itemsOf(loaded?.available);
  // What Available lists and counts: an installed kit is in Installed, a new version of it
  // in Updates.
  const notInstalled = offers.filter((offer) => !offer.installed);
  // A check's newer version, while the kit is still at the tag it was checked at: an
  // update since (here or from the CLI, through the feed) ends it.
  const checks = new Map((checked?.rows ?? []).map((row) => [row.name, row]));
  const newerOf = (kit: InstalledKitInfo): string | null => {
    const row = checks.get(kit.name);
    return row?.newer && row.installed === (kit.tag ?? "") ? row.newer : null;
  };

  const chooseSource = (next: string) => {
    setSource(next);
    storeKitsSource(next);
  };
  const needle = query.trim().toLowerCase();
  const found = (name: string, description: string | null | undefined, chip: string) =>
    (source === ALL || source === chip) &&
    (!needle || name.toLowerCase().includes(needle) || (description ?? "").toLowerCase().includes(needle));

  const check = async () => {
    setChecking(true);
    setCheckProblem(null);
    try {
      setChecked({ at: new Date(), rows: await checkUpdates() });
    } catch (error) {
      setCheckProblem(messageOf(error));
    }
    setChecking(false);
  };

  const update = async (name?: string) => {
    setUpdating(true);
    try {
      const done = await updateMarketplaces(name);
      setMarketErrors((before) => {
        const after = { ...before };
        done.forEach((one) => {
          if (one.error) after[one.name] = one.error;
          else delete after[one.name];
        });
        return after;
      });
    } catch (error) {
      setMarketErrors((before) => ({ ...before, [name ?? ""]: messageOf(error) }));
    }
    setUpdating(false);
  };

  const shownInstalled = installed.filter((kit) => found(kit.name, kit.description, sourceOf(kit, knownMarkets).chip));
  const shownOffers = notInstalled.filter((offer) =>
    found(offer.name, offer.index?.description, marketSource(offer.marketplace)),
  );
  const updates = installed.filter((kit) => newerOf(kit) !== null);
  const shownUpdates = updates.filter((kit) => found(kit.name, kit.description, sourceOf(kit, knownMarkets).chip));

  const tabLabels: Record<KitsTab, [string, number | null]> = {
    installed: ["Installed", installed.length],
    available: ["Available", notInstalled.length],
    updates: ["Updates", checked ? updates.length : null],
  };

  const listProblem = [loaded?.installed, loaded?.available].find(
    (one): one is { error: string } => !!one && "error" in one,
  );

  return (
    <div className="kits-page">
      <div className="kits-head">
        {checked && <span className="muted kits-checked">Updates checked {time(checked.at)}</span>}
        <button type="button" className="quiet" disabled={checking} onClick={() => void check()}>
          {checking ? "Checking…" : "Check for updates"}
        </button>
        <button type="button" className="primary" onClick={() => setDialog({ kind: "add" })}>
          Add kit…
        </button>
      </div>
      {checkProblem && (
        <p className="problem" role="alert">
          {checkProblem}
        </p>
      )}
      <div className="kits-split">
        <div className="kits-main">
          <nav className="tab-bar" aria-label="Kits">
            {TABS.map((one) => {
              const [label, count] = tabLabels[one];
              return (
                <Link
                  key={one}
                  to={`/kits/${one}`}
                  className="tab-item"
                  aria-current={one === tab ? "page" : undefined}
                >
                  {label}
                  {count !== null && (
                    <>
                      {" "}
                      <span className="tab-count">{count}</span>
                    </>
                  )}
                </Link>
              );
            })}
          </nav>
          <div className="kits-bar">
            <input
              type="search"
              className="search"
              aria-label="Find a kit"
              placeholder="Find a kit"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            <div className="kits-chips" role="group" aria-label="Source">
              {[
                [ALL, "All"],
                ...markets.map((m) => [marketSource(m.name), m.name]),
                ["git", "git"],
                ["folder", "folder"],
                ["built-in", "built-in"],
              ].map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  className="chip"
                  aria-pressed={source === value}
                  onClick={() => chooseSource(value)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          {listProblem && (
            <p className="problem" role="alert">
              {listProblem.error}
            </p>
          )}
          {tab === "installed" && (
            <KitList loading={loaded?.installed == null} empty="No kit matches.">
              {shownInstalled.map((kit) => (
                <InstalledRow
                  key={`${kit.kind}:${kit.name}`}
                  kit={kit}
                  source={sourceOf(kit, knownMarkets)}
                  newer={newerOf(kit)}
                  onUpdate={(tag) => setDialog({ kind: "update", kit, tag })}
                  onRemove={() => setDialog({ kind: "remove", kit })}
                />
              ))}
            </KitList>
          )}
          {tab === "available" &&
            (loaded?.available != null && offers.length === 0 ? (
              <NoOffers markets={markets} busy={updating} onUpdate={(name) => void update(name)} />
            ) : offers.length > 0 && notInstalled.length === 0 ? (
              <AllInstalled offers={offers} />
            ) : (
              <KitList loading={loaded?.available == null} empty="No kit matches.">
                {shownOffers.map((offer) => (
                  <OfferRow
                    key={`${offer.marketplace}:${offer.name}`}
                    offer={offer}
                    official={marketKind(offer.marketplace, knownMarkets) === "official"}
                    onInstall={() =>
                      setDialog({
                        kind: "add",
                        ask: { spec: offer.name, marketplace: offer.marketplace, pre: false },
                      })
                    }
                  />
                ))}
              </KitList>
            ))}
          {tab === "updates" &&
            (checked === null ? (
              <div className="empty">
                <p>Check for updates to see them.</p>
                <button type="button" className="quiet" disabled={checking} onClick={() => void check()}>
                  {checking ? "Checking…" : "Check for updates"}
                </button>
              </div>
            ) : (
              <>
                <CheckNotes rows={checked.rows} />
                <KitList loading={false} empty="Every kit is up to date.">
                  {shownUpdates.map((kit) => (
                    <InstalledRow
                      key={kit.name}
                      kit={kit}
                      source={sourceOf(kit, knownMarkets)}
                      newer={newerOf(kit)}
                      onUpdate={(tag) => setDialog({ kind: "update", kit, tag })}
                      onRemove={() => setDialog({ kind: "remove", kit })}
                    />
                  ))}
                </KitList>
              </>
            ))}
        </div>
        <Marketplaces
          markets={markets}
          problem={marketList && "error" in marketList ? marketList.error : null}
          errors={marketErrors}
          busy={updating}
          onUpdateAll={() => void update()}
          onError={(name, error) => setMarketErrors((before) => ({ ...before, [name]: error }))}
          onAdd={() => setDialog({ kind: "add-marketplace" })}
          onRemove={(market) => setDialog({ kind: "remove-marketplace", market })}
        />
      </div>
      {dialog?.kind === "add" && (
        <AddKitDialog
          markets={markets.filter((m) => m.enabled)}
          offers={offers}
          ask={dialog.ask}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog?.kind === "update" && <UpdateDialog kit={dialog.kit} tag={dialog.tag} onClose={() => setDialog(null)} />}
      {dialog?.kind === "remove" && <RemoveKitDialog kit={dialog.kit} onClose={() => setDialog(null)} />}
      {dialog?.kind === "add-marketplace" && <AddMarketplaceDialog onClose={() => setDialog(null)} />}
      {dialog?.kind === "remove-marketplace" && (
        <RemoveMarketplaceDialog
          market={dialog.market}
          stay={installed.filter((kit) => kit.marketplace === dialog.market.name).map((kit) => kit.name)}
          onClose={() => setDialog(null)}
        />
      )}
    </div>
  );
}

function KitList({ loading, empty, children }: { loading: boolean; empty: string; children: ReactNode[] }) {
  if (loading) return <p className="muted">Loading…</p>;
  if (children.length === 0) return <p className="empty">{empty}</p>;
  return (
    <ul className="kit-grid" aria-label="Kits">
      {children}
    </ul>
  );
}

// The copy item of a card's ⋯: its address, or its folder.
function copyWhere(name: string, address: string | null, folder: string | null): RowMenuItem[] {
  if (address) {
    const field = { title: `Address of ${name}`, label: "Address" };
    return [{ label: "Copy address", copy: address, copied: "Address copied", field }];
  }
  if (folder) {
    const field = { title: `Folder of ${name}`, label: "Folder" };
    return [{ label: "Copy folder", copy: folder, copied: "Folder copied", field }];
  }
  return [];
}

// An installed kit: ↑ by its version when a check found a newer one; Update… (to that
// version), Remove… and its copy in ⋯; a built-in kit has none.
function InstalledRow(props: {
  kit: InstalledKitInfo;
  source: Source;
  newer: string | null;
  onUpdate: (tag: string | null) => void;
  onRemove: () => void;
}) {
  const { kit, newer } = props;
  const git = kit.kind === "git";
  const menu: RowMenuItem[] = [
    ...(git ? [{ label: newer ? `Update to ${newer}…` : "Update…", onSelect: () => props.onUpdate(newer) }] : []),
    { label: "Remove…", onSelect: props.onRemove },
    ...copyWhere(kit.name, kit.address, kit.folder),
  ];
  return (
    <KitCard
      name={kit.name}
      builtIn={kit.kind === "built-in"}
      version={kit.tag ?? kit.version}
      action={
        git && newer
          ? { symbol: "↑", label: `Update ${kit.name} to ${newer}…`, to: newer, onSelect: () => props.onUpdate(newer) }
          : undefined
      }
      badges={kit.missing && <span className="badge badge-warn">folder missing</span>}
      description={kit.description}
      problem={kit.problem}
      source={props.source}
      agents={kit.agents}
      skills={kit.skills}
      flows={kit.flows}
      where={kit.address ?? kit.folder}
      menu={kit.kind === "built-in" ? undefined : menu}
    />
  );
}

// A kit a marketplace offers: + by its version and Install… in ⋯, both to the plan.
function OfferRow({ offer, official, onInstall }: { offer: OfferInfo; official: boolean; onInstall: () => void }) {
  const entry = offer.index;
  const latest = entry?.latest ?? null;
  return (
    <KitCard
      name={offer.name}
      version={latest}
      action={{ symbol: "+", label: latest ? `Install ${offer.name} ${latest}…` : `Install ${offer.name}…`, onSelect: onInstall }}
      description={entry?.description ?? null}
      noDescription="No description in the index"
      source={{ label: offer.marketplace, kind: official ? "official" : "marketplace" }}
      agents={Object.keys(entry?.agents ?? {}).length}
      skills={entry?.skills?.length ?? 0}
      flows={entry?.flows?.length ?? 0}
      where={offer.address}
      menu={[{ label: "Install…", onSelect: onInstall }, ...copyWhere(offer.name, offer.address, null)]}
    />
  );
}

// Available with nothing in it: no marketplace fetched yet (a fresh LADO_HOME), or nothing
// listed in the enabled ones. Nothing is cloned until the human asks.
function NoOffers(props: { markets: MarketplaceInfo[]; busy: boolean; onUpdate: (name: string) => void }) {
  const unfetched = props.markets.filter((m) => m.enabled && m.kits === null);
  const fetched = props.markets.some((m) => m.enabled && m.kits !== null);
  if (fetched || unfetched.length === 0) return <p className="empty">No kit in the enabled marketplaces.</p>;
  return (
    <div className="empty">
      <p>No marketplace fetched yet.</p>
      {unfetched.map((m) => (
        <button
          key={m.name}
          type="button"
          className="quiet"
          disabled={props.busy}
          onClick={() => props.onUpdate(m.name)}
        >
          {`Update ${m.name}`}
        </button>
      ))}
    </div>
  );
}

// Available when the marketplaces list kits and each of them is installed.
function AllInstalled({ offers }: { offers: OfferInfo[] }) {
  const listed = new Map<string, number>();
  offers.forEach((offer) => listed.set(offer.marketplace, (listed.get(offer.marketplace) ?? 0) + 1));
  const lists = [...listed].map(([market, count]) => `${market} lists ${plural(count, "kit")}`);
  return (
    <div className="empty">
      <p>
        <b>All kits of your marketplaces are installed</b>
      </p>
      <p>{`${lists.join(", ")}.`}</p>
      <Link to="/kits/installed">Show installed kits</Link>
    </div>
  );
}

// What the check said besides the updates: kits it did not check and moved tags.
function CheckNotes({ rows }: { rows: OutdatedInfo[] }) {
  const notes = rows.filter((row) => row.note).map((row) => `${row.name}: ${row.note}`);
  const warnings = rows.flatMap((row) => row.warnings);
  if (notes.length === 0 && warnings.length === 0) return null;
  return (
    <div className="kit-notes">
      {warnings.map((warning) => (
        <p key={warning} className="kit-warning">
          {warning}
        </p>
      ))}
      {notes.map((note) => (
        <p key={note} className="muted">
          {note}
        </p>
      ))}
    </div>
  );
}

function Marketplaces(props: {
  markets: MarketplaceInfo[];
  problem: string | null;
  errors: Record<string, string>;
  busy: boolean;
  onUpdateAll: () => void;
  onError: (name: string, error: string) => void;
  onAdd: () => void;
  onRemove: (market: MarketplaceInfo) => void;
}) {
  const [switching, setSwitching] = useState<string | null>(null);
  const toggle = async (market: MarketplaceInfo) => {
    setSwitching(market.name);
    try {
      await setMarketplaceEnabled(market.name, !market.enabled);
    } catch (error) {
      props.onError(market.name, messageOf(error));
    }
    setSwitching(null);
  };
  return (
    <aside className="kits-markets" aria-label="Marketplaces">
      <div className="kits-markets-head">
        <h3>Marketplaces</h3>
        <button type="button" className="quiet" disabled={props.busy} onClick={props.onUpdateAll}>
          {props.busy ? "Updating…" : "Update all"}
        </button>
      </div>
      {props.problem && (
        <p className="problem" role="alert">
          {props.problem}
        </p>
      )}
      <ul>
        {props.markets.map((market) => (
          <li key={market.name} className="market-row" aria-label={market.name}>
            <input
              type="checkbox"
              aria-label={`${market.name} enabled`}
              checked={market.enabled}
              disabled={switching === market.name}
              onChange={() => void toggle(market)}
            />
            <span className={`market-name${market.enabled ? "" : " muted"}`}>{market.name}</span>
            {market.kits !== null && <span className="muted">{plural(market.kits, "kit")}</span>}
            {!market.official && (
              <button
                type="button"
                className="link-button"
                aria-label={`Remove ${market.name}…`}
                onClick={() => props.onRemove(market)}
              >
                Remove
              </button>
            )}
            <span className="market-where">
              {market.url}
              {" · "}
              {market.enabled
                ? market.updated_at
                  ? `updated ${new Date(market.updated_at).toLocaleString()}`
                  : "never updated"
                : "disabled"}
            </span>
            {market.problem && <span className="market-problem">{market.problem}</span>}
            {props.errors[market.name] && (
              <span className="market-error" role="alert">
                {props.errors[market.name]}
              </span>
            )}
          </li>
        ))}
      </ul>
      <button type="button" className="quiet" onClick={props.onAdd}>
        Add marketplace…
      </button>
    </aside>
  );
}

// A modal window of the page: Esc and Cancel close it unless a request runs. Its head and
// its footer with the buttons stay in place; only the middle scrolls. With `onSubmit` the
// window is a form, and Enter in a field submits it.
function Modal(props: {
  title: string;
  head?: ReactNode;
  busy: boolean;
  onClose: () => void;
  onSubmit?: () => void;
  footer: ReactNode;
  children: ReactNode;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  const frame = (
    <>
      <header className="kits-dialog-head">{props.head ?? <h3>{props.title}</h3>}</header>
      <div className="kits-dialog-body">{props.children}</div>
      <footer className="kits-dialog-foot">{props.footer}</footer>
    </>
  );
  const { onSubmit } = props;
  return (
    <dialog
      ref={dialog}
      className="question-dialog kits-dialog"
      aria-label={props.title}
      onCancel={(event) => {
        event.preventDefault();
        if (!props.busy) props.onClose();
      }}
      onKeyDown={(event) => {
        if (event.key !== "Escape") return;
        event.preventDefault();
        if (!props.busy) props.onClose();
      }}
    >
      {onSubmit ? (
        <form
          className="kits-dialog-frame"
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit();
          }}
        >
          {frame}
        </form>
      ) : (
        <div className="kits-dialog-frame">{frame}</div>
      )}
    </dialog>
  );
}

type Way = "marketplace" | "git" | "folder";

const WAYS: [Way, string][] = [
  ["marketplace", "From a marketplace"],
  ["git", "Git address"],
  ["folder", "Folder"],
];

type Step = { kind: "ask" } | { kind: "planning" } | { kind: "plan"; plan: PlanInfo } | { kind: "refused"; message: string };

// Add kit: what to add (a kit of a marketplace, a git address or a folder), then the plan
// the core makes, then Install. From an Available row it starts at the plan.
function AddKitDialog(props: { markets: MarketplaceInfo[]; offers: OfferInfo[]; ask?: PlanAsk; onClose: () => void }) {
  const ids = useId();
  const [way, setWay] = useState<Way>("marketplace");
  const [market, setMarket] = useState(props.ask?.marketplace ?? props.markets[0]?.name ?? "");
  const [name, setName] = useState(props.ask?.spec ?? "");
  const [address, setAddress] = useState("");
  const [folder, setFolder] = useState("");
  const [version, setVersion] = useState("");
  const [pre, setPre] = useState(false);
  const [step, setStep] = useState<Step>(props.ask ? { kind: "planning" } : { kind: "ask" });
  const [lastAsk, setLastAsk] = useState<PlanAsk | null>(props.ask ?? null);

  const askOf = (): PlanAsk | null => {
    const tag = version.trim();
    const pinned = (spec: string) => (tag ? `${spec}@${tag}` : spec);
    if (way === "marketplace") return name.trim() && market ? { spec: pinned(name.trim()), marketplace: market, pre } : null;
    if (way === "git") return address.trim() ? { spec: pinned(address.trim()), pre } : null;
    return folder.trim() ? { spec: folder.trim(), pre: false } : null;
  };

  const plan = async (ask: PlanAsk) => {
    setLastAsk(ask);
    setStep({ kind: "planning" });
    try {
      setStep({ kind: "plan", plan: await planKit(ask) });
    } catch (error) {
      setStep({ kind: "refused", message: messageOf(error) });
    }
  };

  useEffect(() => {
    if (props.ask) void plan(props.ask);
    // Once, for the Available row it was opened from.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const back = () => setStep({ kind: "ask" });

  if (step.kind === "plan" && lastAsk) {
    return <PlanStep plan={step.plan} onBack={back} onAgain={() => void plan(lastAsk)} onClose={props.onClose} />;
  }
  if (step.kind === "refused") {
    return (
      <Modal
        title="Refused"
        busy={false}
        onClose={props.onClose}
        footer={
          <button type="button" className="quiet" onClick={back}>
            Back
          </button>
        }
      >
        <p className="problem" role="alert">
          {step.message}
        </p>
      </Modal>
    );
  }
  const busy = step.kind === "planning";
  const ask = askOf();
  const names = [...new Set(props.offers.filter((o) => o.marketplace === market).map((o) => o.name))];
  return (
    <Modal
      title="Add kit"
      busy={busy}
      onClose={props.onClose}
      onSubmit={() => {
        if (ask && !busy) void plan(ask);
      }}
      footer={
        <>
          <button type="button" className="quiet" disabled={busy} onClick={props.onClose}>
            Cancel
          </button>
          <button type="submit" className="primary" disabled={busy || ask === null}>
            Next
          </button>
        </>
      }
    >
      <div className="kits-ways" role="radiogroup" aria-label="Where from">
        {WAYS.map(([value, label]) => (
          <label key={value} className={way === value ? "on" : undefined}>
            <input
              type="radio"
              name={`${ids}-way`}
              value={value}
              checked={way === value}
              disabled={busy}
              onChange={() => setWay(value)}
            />
            {label}
          </label>
        ))}
      </div>
      {way === "marketplace" && (
        <div className="kits-fields">
          <select aria-label="Marketplace" value={market} disabled={busy} onChange={(event) => setMarket(event.target.value)}>
            {props.markets.map((m) => (
              <option key={m.name} value={m.name}>
                {m.name}
              </option>
            ))}
          </select>
          <input
            aria-label="Kit"
            placeholder="kit name"
            list={`${ids}-names`}
            value={name}
            disabled={busy}
            onChange={(event) => setName(event.target.value)}
          />
          <datalist id={`${ids}-names`}>
            {names.map((one) => (
              <option key={one} value={one} />
            ))}
          </datalist>
        </div>
      )}
      {way === "git" && (
        <input
          className="kits-wide"
          aria-label="Git address"
          placeholder="https://github.com/you/kit.git"
          value={address}
          disabled={busy}
          onChange={(event) => setAddress(event.target.value)}
        />
      )}
      {way === "folder" && (
        <input
          className="kits-wide"
          aria-label="Folder"
          placeholder="/full/path/to/kit"
          value={folder}
          disabled={busy}
          onChange={(event) => setFolder(event.target.value)}
        />
      )}
      {way !== "folder" && (
        <div className="kits-fields">
          <input
            aria-label="Version"
            placeholder="latest"
            value={version}
            disabled={busy}
            onChange={(event) => setVersion(event.target.value)}
          />
          <label className="kits-check">
            <input type="checkbox" checked={pre} disabled={busy} onChange={(event) => setPre(event.target.checked)} />
            Include pre-releases
          </label>
        </div>
      )}
      {busy && <p className="muted">Making the plan: the kit is cloned into the cache, nothing is installed…</p>}
    </Modal>
  );
}

function Warnings({ lines }: { lines: string[] }) {
  return (
    <>
      {lines.map((line) => (
        <p key={line} className="kit-warning">
          {line}
        </p>
      ))}
    </>
  );
}

// A 409 or a refusal of the install: the server's words, and a new plan for a 409.
function Failure({ error, onAgain }: { error: ApiError; onAgain: () => void }) {
  return (
    <div className="kits-failure">
      <p className="problem" role="alert">
        {error.message}
      </p>
      {error.status === 409 && (
        <button type="button" className="quiet" onClick={onAgain}>
          Look at the plan again
        </button>
      )}
    </div>
  );
}

function PlanStep(props: { plan: PlanInfo; onBack: () => void; onAgain: () => void; onClose: () => void }) {
  const { plan } = props;
  const [checked, setChecked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<ApiError | null>(null);
  const title = plan.tag === null ? `Install ${plan.name} from a folder` : `Install ${plan.name} ${plan.tag}`;
  const install = async () => {
    setBusy(true);
    setFailed(null);
    try {
      await installKit({
        spec: plan.spec,
        ...(plan.marketplace ? { marketplace: plan.marketplace } : {}),
        ...(plan.tag === null ? { mcp: plan.mcp.map((m) => m.name) } : { commit: plan.commit }),
      });
      props.onClose();
    } catch (error) {
      setFailed(error instanceof ApiError ? error : new ApiError(0, String(error)));
      setBusy(false);
    }
  };
  return (
    <Modal
      title={title}
      head={
        <>
          <span className="kits-dialog-kicker">{plan.source}</span>
          <h3>{title}</h3>
        </>
      }
      busy={busy}
      onClose={props.onClose}
      footer={
        <>
          <button type="button" className="quiet" disabled={busy} onClick={props.onBack}>
            Back
          </button>
          <button
            type="button"
            className="primary"
            disabled={busy || (plan.needs_confirmation && !checked)}
            onClick={() => void install()}
          >
            {busy ? "Installing…" : "Install"}
          </button>
        </>
      }
    >
      {plan.needs_confirmation && (
        <p className="kit-alert">
          <b>Not from the official marketplace.</b> LADO has not checked this kit. Its MCP servers below will run in
          your sessions with your permissions.
        </p>
      )}
      {plan.tag === null && (
        <p className="muted">
          A local folder: the kit is read from it as it is each time a session starts, so changes in the folder reach
          new agents.
        </p>
      )}
      {plan.description && <p className="kit-plan-description">{plan.description}</p>}
      <Warnings lines={plan.warnings} />
      <PlanContents plan={plan} before={null} />
      {plan.needs_confirmation && (
        <label className="kits-check">
          <input type="checkbox" checked={checked} disabled={busy} onChange={(event) => setChecked(event.target.checked)} />
          I checked the address and the MCP servers
        </label>
      )}
      {failed && <Failure error={failed} onAgain={props.onAgain} />}
    </Modal>
  );
}

// Update: the core's plan for the latest version, the one a card's ↑ named (`tag`) or the one
// chosen, its new MCP servers and who gets it; an update never asks in the CLI, here the
// plan is shown all the same.
function UpdateDialog({ kit, tag: first, onClose }: { kit: InstalledKitInfo; tag: string | null; onClose: () => void }) {
  const [plan, setPlan] = useState<PlanInfo | null>(null);
  const [versions, setVersions] = useState<string[]>([]);
  const [busy, setBusy] = useState(true);
  const [failed, setFailed] = useState<ApiError | null>(null);

  const ask = async (tag: string | null) => {
    setBusy(true);
    setFailed(null);
    try {
      const got = await planKitUpdate(kit.name, tag);
      setPlan(got);
      // The repository's tags, the same for any tag planned: kept from the first plan.
      setVersions((before) => (before.length > 0 ? before : got.versions));
    } catch (error) {
      setFailed(error instanceof ApiError ? error : new ApiError(0, String(error)));
    }
    setBusy(false);
  };
  useEffect(() => {
    void ask(first);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const update = async () => {
    if (!plan || plan.tag === null || plan.commit === null) return;
    setBusy(true);
    setFailed(null);
    try {
      await updateKit(kit.name, plan.tag, plan.commit);
      onClose();
    } catch (error) {
      setFailed(error instanceof ApiError ? error : new ApiError(0, String(error)));
      setBusy(false);
    }
  };

  const title = `Update ${kit.name}`;
  const failure = failed && <Failure error={failed} onAgain={() => void ask(plan?.tag ?? null)} />;
  const options = versions.map((one, i) => {
    const marks = [i === 0 && "latest", one === kit.tag && "installed"].filter(Boolean);
    return (
      <option key={one} value={one}>
        {marks.length > 0 ? `${one} (${marks.join(", ")})` : one}
      </option>
    );
  });
  const choose = (event: ChangeEvent<HTMLSelectElement>) => void ask(event.target.value);

  // Nothing to update: a short answer, and another version to choose.
  if (plan === null || plan.current) {
    const latest = plan !== null && plan.tag === versions[0];
    return (
      <Modal
        title={title}
        busy={busy}
        onClose={onClose}
        footer={
          <button type="button" className="primary" disabled={busy} onClick={onClose}>
            {plan === null ? "Cancel" : "Close"}
          </button>
        }
      >
        {plan === null && busy && <p className="muted">Making the plan…</p>}
        {plan && (
          // The core's current_line, said here with the versions it knows: plan.notes holds
          // only that line for a current plan.
          <div className="kit-state">
            {latest && (
              <span className="kit-ok" aria-hidden="true">
                ✓
              </span>
            )}
            <div>
              <p className="kit-state-head">
                {latest ? `${kit.name} is up to date` : `${kit.name} is at ${plan.tag} already`}
              </p>
              <p className="muted">{`${versions[0] ?? plan.tag} is the latest version · ${plan.source}`}</p>
            </div>
          </div>
        )}
        {plan && <Warnings lines={plan.warnings} />}
        {plan && versions.length > 1 && (
          <label className="kits-check">
            Install another version
            <select aria-label="Install another version" value={plan.tag ?? ""} disabled={busy} onChange={choose}>
              {options}
            </select>
          </label>
        )}
        {failure}
      </Modal>
    );
  }

  return (
    <Modal
      title={title}
      head={
        <>
          <span className="kits-dialog-kicker">{`Update ${kit.name} · ${plan.source}`}</span>
          <div className="kit-jump">
            <span className="kit-jump-from">{plan.installed}</span>
            <span className="kit-jump-arrow" aria-hidden="true">
              →
            </span>
            <span className="kit-jump-to">{plan.tag}</span>
            {plan.tag === versions[0] && <span className="badge">latest</span>}
          </div>
        </>
      }
      busy={busy}
      onClose={onClose}
      footer={
        <>
          <label className="kits-dialog-version">
            Version
            <select aria-label="Version" value={plan.tag ?? ""} disabled={busy} onChange={choose}>
              {options}
            </select>
          </label>
          <button type="button" className="quiet" disabled={busy} onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="primary" disabled={busy} onClick={() => void update()}>
            {`Update to ${plan.tag}`}
          </button>
        </>
      }
    >
      {plan.new_mcp.length > 0 && (
        <p className="kit-alert">
          <b>{`New MCP server${plan.new_mcp.length === 1 ? "" : "s"}: ${plan.new_mcp.join(", ")}.`}</b> The new version
          starts what the installed one did not.
        </p>
      )}
      <Warnings lines={plan.warnings} />
      {plan.before === null && (
        <p className="muted">The installed version's files are not in the cache: changes are not shown.</p>
      )}
      <PlanContents key={plan.tag} plan={plan} before={plan.before} />
      {plan.notes.length > 0 && (
        <div className="kit-group">
          <h4>Who gets it</h4>
          {plan.notes.map((note) => (
            <p key={note} className="kit-who">
              {note}
            </p>
          ))}
        </div>
      )}
      {failure}
    </Modal>
  );
}

// Remove: never blocked; the core names the sessions that use the kit.
function RemoveKitDialog({ kit, onClose }: { kit: InstalledKitInfo; onClose: () => void }) {
  const [users, setUsers] = useState<KitUsersInfo | { error: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  useEffect(() => {
    let current = true;
    getRemovePreview(kit.name).then(
      (got) => current && setUsers(got),
      (error: unknown) => current && setUsers({ error: messageOf(error) }),
    );
    return () => {
      current = false;
    };
  }, [kit.name]);
  const remove = async () => {
    setBusy(true);
    setRefused(null);
    try {
      await removeKit(kit.name);
      onClose();
    } catch (error) {
      setRefused(messageOf(error));
      setBusy(false);
    }
  };
  const found = users !== null && "running" in users ? users : null;
  return (
    <Modal
      title={`Remove ${kit.name}?`}
      busy={busy}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="quiet" disabled={busy} onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="danger" disabled={busy || users === null} onClick={() => void remove()}>
            Remove
          </button>
        </>
      }
    >
      {users === null && <p className="muted">Loading…</p>}
      {users !== null && "error" in users && (
        <p className="problem" role="alert">
          {users.error}
        </p>
      )}
      {found?.running_line && <p className="kit-danger">{found.running_line}</p>}
      {found?.stopped_line && <p className="muted">{found.stopped_line}</p>}
      {found && !found.running_line && !found.stopped_line && <p>No session uses it.</p>}
      {kit.missing ? (
        <p className="muted">
          {kit.folder ? `Its folder ${kit.folder} is gone.` : "Its clone in the cache is gone."} LADO only forgets the kit.
        </p>
      ) : (
        <p className="muted">
          {kit.kind === "folder"
            ? "LADO forgets the kit; the folder stays."
            : "LADO forgets the kit; its clone stays in the cache, so Add kit brings the same version back without the network."}
        </p>
      )}
      {refused && (
        <p className="problem" role="alert">
          {refused}
        </p>
      )}
    </Modal>
  );
}

function AddMarketplaceDialog({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  const ready = name.trim() !== "" && url.trim() !== "";
  const add = async () => {
    setBusy(true);
    setRefused(null);
    try {
      await addMarketplace(name.trim(), url.trim());
      onClose();
    } catch (error) {
      setRefused(messageOf(error));
      setBusy(false);
    }
  };
  return (
    <Modal
      title="Add marketplace"
      busy={busy}
      onClose={onClose}
      onSubmit={() => {
        if (ready && !busy) void add();
      }}
      footer={
        <>
          <button type="button" className="quiet" disabled={busy} onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="primary" disabled={busy || !ready}>
            {busy ? "Adding…" : "Add"}
          </button>
        </>
      }
    >
      <div className="kits-fields">
        <input aria-label="Name" placeholder="name" value={name} disabled={busy} onChange={(e) => setName(e.target.value)} />
        <input
          className="kits-wide"
          aria-label="Git address"
          placeholder="https://github.com/you/marketplace.git"
          value={url}
          disabled={busy}
          onChange={(e) => setUrl(e.target.value)}
        />
      </div>
      <p className="muted">
        LADO clones it and reads its list. LADO does not check its kits: each install from it asks you to confirm.
      </p>
      {refused && (
        <p className="problem" role="alert">
          {refused}
        </p>
      )}
    </Modal>
  );
}

function RemoveMarketplaceDialog(props: { market: MarketplaceInfo; stay: string[]; onClose: () => void }) {
  const { market, stay } = props;
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  const remove = async () => {
    setBusy(true);
    setRefused(null);
    try {
      await removeMarketplace(market.name);
      props.onClose();
    } catch (error) {
      setRefused(messageOf(error));
      setBusy(false);
    }
  };
  const one = stay.length === 1;
  return (
    <Modal
      title={`Remove marketplace ${market.name}?`}
      busy={busy}
      onClose={props.onClose}
      footer={
        <>
          <button type="button" className="quiet" disabled={busy} onClick={props.onClose}>
            Cancel
          </button>
          <button type="button" className="danger" disabled={busy} onClick={() => void remove()}>
            Remove
          </button>
        </>
      }
    >
      {stay.length === 0 ? (
        <p>No installed kit comes from it.</p>
      ) : (
        <p>
          {`Its ${plural(stay.length, "installed kit")} ${one ? "stays and keeps" : "stay and keep"} working: ${stay.join(", ")}. `}
          {`They show “${market.name} (removed)” as their source and update from their own addresses.`}
        </p>
      )}
      <p className="muted">Its kits leave Available. Add it again to see them there.</p>
      {refused && (
        <p className="problem" role="alert">
          {refused}
        </p>
      )}
    </Modal>
  );
}
