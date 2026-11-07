// A link as a QR code, to open it on a phone: LADO's own link (Share.tsx) and a CLI's
// sign-in page (LoginWindow.tsx).
import qrcode from "qrcode-generator";
import type { ReactNode } from "react";

// The text as a QR code: black modules on white with a 4-module quiet zone, in both themes,
// as a phone's camera needs.
export function QrCode({ text, label = "QR code of the link", className = "share-qr" }: { text: string; label?: string; className?: string }) {
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
    <svg className={className} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={label} shapeRendering="crispEdges">
      <rect width={size} height={size} fill="#fff" />
      <g fill="#000">{cells}</g>
    </svg>
  );
}
