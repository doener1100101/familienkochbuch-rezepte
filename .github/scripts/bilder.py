"""Bildpflege fürs Familienkochbuch.

- <Name>.zuschnitt.md neben <Name>.jpg: Inhalt "links oben breite höhe" in Prozent
  (z. B. "10 20 80 55"). Das Bild wird so zugeschnitten, danach wird die Datei gelöscht.
- Jedes Bild: Ausrichtung nach EXIF, längste Seite höchstens 1080 px, JPG so lange
  stärker komprimiert, bis es unter ~200 KB liegt (Qualität 82 → 60).
"""
import io, os, re, glob
from PIL import Image, ImageOps
try:
    import pillow_avif  # noqa: F401  (AVIF-Bilder lesen)
except Exception:
    pass

DIR = "Rezepte/Bilder"
MAX_SIDE, MAX_BYTES = 1080, 200_000

def find_image(stem):
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".JPG", ".JPEG", ".PNG"):
        p = os.path.join(DIR, stem + ext)
        if os.path.exists(p):
            return p
    return None

def save(img, path):
    fmt = "PNG" if path.lower().endswith(".png") else "WEBP" if path.lower().endswith(".webp") else "JPEG"
    if fmt == "JPEG" and img.mode != "RGB":
        img = img.convert("RGB")
    for q in (82, 76, 70, 65, 60):
        buf = io.BytesIO()
        if fmt == "PNG":
            img.save(buf, "PNG", optimize=True)
        else:
            img.save(buf, fmt, quality=q, optimize=True, progressive=(fmt == "JPEG"))
        if buf.tell() <= MAX_BYTES or fmt == "PNG":
            break
    with open(path, "wb") as f:
        f.write(buf.getvalue())

# 1) Zuschnitte
for spec in glob.glob(os.path.join(DIR, "*.zuschnitt.md")):
    stem = os.path.basename(spec)[: -len(".zuschnitt.md")]
    img_path = find_image(stem)
    nums = [float(x.replace(",", ".")) for x in re.findall(r"-?\d+(?:[.,]\d+)?", open(spec, encoding="utf-8").read())]
    if img_path and len(nums) >= 4:
        x, y, w, h = [max(0.0, min(100.0, n)) for n in nums[:4]]
        try:
            img = ImageOps.exif_transpose(Image.open(img_path))
        except Exception as e:
            print("Zuschnitt übersprungen:", img_path, e); os.remove(spec); continue
        W, H = img.size
        box = (int(W * x / 100), int(H * y / 100), int(W * min(100, x + w) / 100), int(H * min(100, y + h) / 100))
        if box[2] - box[0] > 50 and box[3] - box[1] > 50:
            save(img.crop(box), img_path)
            print("zugeschnitten:", img_path, box)
    os.remove(spec)

# 2) Verkleinern
for p in sorted(glob.glob(os.path.join(DIR, "*"))):
    if not re.search(r"\.(jpe?g|png|webp)$", p, re.I):
        continue
    try:
        img = Image.open(p); img.load()
    except Exception as e:
        print("übersprungen (kein lesbares Bild):", p, e)
        continue
    exif_rot = img.getexif().get(274, 1) not in (None, 1)
    want = "PNG" if p.lower().endswith(".png") else "WEBP" if p.lower().endswith(".webp") else "JPEG"
    wrong_format = img.format != want
    too_big = max(img.size) > MAX_SIDE or (os.path.getsize(p) > MAX_BYTES * 1.1 and not p.lower().endswith(".png"))
    if not (too_big or exif_rot or wrong_format):
        continue
    img = ImageOps.exif_transpose(img)
    if max(img.size) > MAX_SIDE:
        img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    before = os.path.getsize(p)
    save(img, p)
    print("verkleinert:", p, before, "->", os.path.getsize(p))
