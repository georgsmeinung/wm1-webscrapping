# ------------------------------------------------------------
# Toma el 20% más "nuevo" por categoría, donde "nuevo" = ID numérico
# más alto extraído del nombre del archivo (p.ej. 826016-*.html).
# Mueve los archivos a Validacion/<categoria>/, con dry-run y restore.
# ------------------------------------------------------------

import argparse
import csv
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

def is_html(p: Path, exts):
    return p.is_file() and p.suffix.lower() in exts

def extract_leading_id(path: Path):
    """
    Extrae el primer bloque de dígitos AL INICIO del nombre (sin extensión).
    Ejemplos válidos:
      826016-lo-que-sea.html  -> 826016
      000123-foo.htm          -> 123
    Si no hay dígitos iniciales, devuelve None.
    """
    m = re.match(r"^0*(\d+)", path.stem)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None

def safe_move(src: Path, dst_dir: Path) -> Path:
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    if not dst.exists():
        shutil.move(str(src), str(dst))
        return dst
    # Evitar colisiones
    stem, suf = src.stem, src.suffix
    k = 1
    while True:
        candidate = dst_dir / f"{stem}_{k}{suf}"
        if not candidate.exists():
            shutil.move(str(src), str(candidate))
            return candidate
        k += 1

def sample_count(n_total: int, pct: float) -> int:
    # Redondeo clásico; si hay >=5 archivos y da 0, movemos 1.
    n = int(round(n_total * pct))
    if n == 0 and n_total >= 5:
        n = 1
    return min(max(n, 0), n_total)

def collect_categories(base: Path, val_name: str):
    return [d for d in base.iterdir() if d.is_dir() and d.name != val_name]

def rglob_htmls(folder: Path, exts):
    return [p for p in folder.rglob("*") if is_html(p, exts)]

def write_manifest(manifest_path: Path, rows):
    header = ["moved_at", "category", "src", "dst", "id_rank"]
    write_header = not manifest_path.exists()
    with manifest_path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(header)
        for r in rows:
            w.writerow([r["moved_at"], r["category"], r["src"], r["dst"], r["id_rank"]])

def restore_from_manifest(manifest_csv: Path):
    if not manifest_csv.exists():
        print(f"[ERROR] No existe el manifest: {manifest_csv}")
        sys.exit(1)
    restored, missing = 0, 0
    with manifest_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            src = Path(row["src"])
            dst = Path(row["dst"])
            if dst.exists():
                src.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dst), str(src))
                restored += 1
            else:
                missing += 1
    print(f"[RESTORE] Restaurados: {restored} | No encontrados: {missing}")

def main():
    parser = argparse.ArgumentParser(description="Mover el 20% más nuevo (ID alto) por categoría a Validacion/<cat>/")
    parser.add_argument("--base", required=True, help="Ruta base con carpetas de categorías (economia, sociedad, ...)")
    parser.add_argument("--val-folder", default="Validacion", help="Nombre carpeta de validación (default: Validacion)")
    parser.add_argument("--pct", type=float, default=0.2, help="Proporción a mover por categoría (default: 0.2)")
    parser.add_argument("--ext", nargs="*", default=[".html", ".htm"], help="Extensiones a incluir (default: .html .htm)")
    parser.add_argument("--dry-run", action="store_true", help="No mueve nada; sólo muestra el plan")
    parser.add_argument("--manifest", default="manifest_validacion.csv", help="Archivo manifest (default: manifest_validacion.csv)")
    parser.add_argument("--restore", help="Ruta a manifest CSV para revertir")
    args = parser.parse_args()

    base = Path(args.base).resolve()
    val_root = base / args.val_folder
    exts = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in args.ext}

    if args.restore:
        restore_from_manifest(Path(args.restore))
        return

    if not base.exists():
        print(f"[ERROR] Base no existe: {base}")
        sys.exit(1)

    categories = collect_categories(base, args.val_folder)
    if not categories:
        print("[WARN] No se encontraron carpetas de categorías.")
        sys.exit(0)

    total_to_move = 0
    plan = []  # (category, src_path, dst_path, id_rank_for_info)

    print(f"[INFO] Base: {base}")
    print(f"[INFO] Carpeta Validación: {val_root}")
    print(f"[INFO] Extensiones: {sorted(exts)} | Pct: {args.pct}")
    print("-----------------------------------------------------")

    for cat_dir in categories:
        # Evitar tocar la carpeta de validación si estuviera al mismo nivel
        if val_root in cat_dir.parents or cat_dir == val_root:
            continue

        htmls = rglob_htmls(cat_dir, exts)
        n_total = len(htmls)
        n_move = sample_count(n_total, args.pct)

        if n_total == 0 or n_move == 0:
            print(f"[CAT] {cat_dir.name}: {n_total} archivos | a mover: 0")
            continue

        # Rank: primero con ID (mayor a menor), luego sin ID por fecha de modif. (recientes primero)
        ranked = []
        for p in htmls:
            fid = extract_leading_id(p)  # None si no hay
            if fid is not None:
                ranked.append((0, -fid, p))  # 0 => tiene ID; -fid para ordenar desc
            else:
                try:
                    mtime = p.stat().st_mtime
                except Exception:
                    mtime = 0.0
                ranked.append((1, -mtime, p))  # 1 => sin ID; recientes primero

        ranked.sort()  # orden asc: (0, -id) van antes que (1, -mtime)

        picks = [t[2] for t in ranked[:n_move]]
        # Armar plan
        dst_dir = val_root / cat_dir.name
        for idx, src in enumerate(picks, start=1):
            plan.append((cat_dir.name, src, dst_dir / src.name, idx))
        total_to_move += len(picks)

        # Métrica informativa
        con_id = sum(1 for t in ranked if t[0] == 0)
        print(f"[CAT] {cat_dir.name}: {n_total} archivos (con ID: {con_id}) | a mover: {len(picks)}")

    if not plan:
        print("[INFO] Nada para mover.")
        return

    if args.dry_run:
        print("\n[DRY-RUN] Archivos que se moverían (top por ID/reciente):")
        for cat, src, dst, k in plan:
            fid = extract_leading_id(src)
            tag = f"ID={fid}" if fid is not None else "SIN_ID"
            print(f"  [{cat}] {src.name:<80} -> {dst.parent}/   ({tag})")
        print(f"\n[DRY-RUN] Total: {total_to_move} archivos.")
        return

    # Ejecutar movimientos y registrar manifest
    manifest_rows = []
    moved = 0
    for cat, src, dst, k in plan:
        moved_path = safe_move(src, dst.parent)
        moved += 1
        manifest_rows.append({
            "moved_at": datetime.now().isoformat(timespec="seconds"),
            "category": cat,
            "src": str(src),
            "dst": str(moved_path),
            "id_rank": str(extract_leading_id(src) or "")
        })

    write_manifest(base / args.manifest, manifest_rows)
    print(f"\n[OK] Movidos {moved} archivos. Manifest: {base / args.manifest}")

if __name__ == "__main__":
    main()
