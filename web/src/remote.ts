// A git remote as the session's head shows it (docs/design/ui.md, Session head): its host
// and path without the scheme, the user and the ending `.git`. The server gives the URL
// with no secret in it already (runtime.public_remote).
export function shortRemote(url: string): string {
  const scp = /^[^/:@]+@([^/:]+):(.*)$/.exec(url); // git@host:path
  const short = scp ? `${scp[1]}/${scp[2]}` : url.replace(/^[a-z][a-z0-9+.-]*:\/\//i, "").replace(/^[^/@]*@/, "");
  return short.replace(/\.git$/, "").replace(/\/$/, "");
}
