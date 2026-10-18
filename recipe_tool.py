#!/usr/bin/env python3
"""
recipe_tool.py — maintain the Recipe Book (index.html + recipes.md).

All recipes live as JSON inside index.html, in
    <script type="application/json" id="recipe-data"> ... </script>
recipes.md is always generated from that data, never edited by hand.

Commands (run from the folder that holds index.html):
    python3 recipe_tool.py list
    python3 recipe_tool.py check
    python3 recipe_tool.py add NEW.json            # one recipe object, or a list of them
    python3 recipe_tool.py add NEW.json --replace  # overwrite recipes with the same id
    python3 recipe_tool.py remove RECIPE_ID
    python3 recipe_tool.py md                      # rebuild recipes.md
Options: --html PATH (default index.html), --md PATH (default recipes.md)

add / remove automatically run check and rebuild recipes.md.
Only the Python standard library is used.
"""
import json, re, sys, argparse
from pathlib import Path

COURSES = [("breakfast", "Breakfast"), ("starters", "Starters"), ("mains", "Mains"), ("desserts", "Desserts")]
COURSE_IDS = [c for c, _ in COURSES]
TAGS = {"veg", "meat", "seafood", "quick"}
LANGS = {"en", "es", "de", "fr", "it", "pt", "zh", "ja"}
RECIPE_KEYS = {"id", "lang", "title", "sub", "course", "tags", "cuisine", "source", "facts", "ingredients", "method", "notes", "rating", "photos"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PHOTO_RE = re.compile(r"^photos/[a-z0-9]+(-[a-z0-9]+)*\.(jpg|jpeg|webp|png)$")
HTML_DIR = Path(".")
ITEM_KEYS = {"m", "o", "n", "x", "l"}
DATA_RE = re.compile(r'(<script type="application/json" id="recipe-data">\n)(.*?)(\n</script>)', re.S)
PAIR_RE = re.compile(r"\{([^|{}]+)\|([^{}]+)\}")
ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


# ---------------------------------------------------------------- I/O
def load(html_path):
    text = Path(html_path).read_text(encoding="utf-8")
    m = DATA_RE.search(text)
    if not m:
        sys.exit(f"ERROR: no recipe-data block found in {html_path}")
    return text, json.loads(m.group(2))


def save(html_path, text, recipes):
    payload = json.dumps(recipes, ensure_ascii=False, indent=1).replace("</", "<\\/")
    new = DATA_RE.sub(lambda m: m.group(1) + payload + m.group(3), text, count=1)
    Path(html_path).write_text(new, encoding="utf-8")


# ---------------------------------------------------------------- validation
def check_text(where, s, errors):
    if not isinstance(s, str) or not s.strip():
        errors.append(f"{where}: must be a non-empty string")
        return
    if s.count("{") != len(PAIR_RE.findall(s)) or s.count("}") != s.count("{"):
        errors.append(f"{where}: braces must only be used as {{metric|original}} pairs: {s!r}")


def validate(recipes):
    errors, warnings = [], []
    if not isinstance(recipes, list):
        return ["data must be a list of recipes"], []
    seen = set()
    for i, r in enumerate(recipes):
        rid = r.get("id", f"#{i}") if isinstance(r, dict) else f"#{i}"
        w = f"[{rid}]"
        if not isinstance(r, dict):
            errors.append(f"{w} recipe must be an object"); continue
        extra = set(r) - RECIPE_KEYS
        if extra: errors.append(f"{w} unknown keys: {sorted(extra)}")
        if not ID_RE.match(str(r.get("id", ""))): errors.append(f"{w} id must be a lowercase slug like 'beef-stew'")
        if rid in seen: errors.append(f"{w} duplicate id")
        seen.add(rid)
        if not str(r.get("title", "")).strip(): errors.append(f"{w} title is required")
        if r.get("course") not in COURSE_IDS: errors.append(f"{w} course must be one of {COURSE_IDS}")
        tags = r.get("tags", [])
        if not isinstance(tags, list) or set(tags) - TAGS: errors.append(f"{w} tags must be a list drawn from {sorted(TAGS)}")
        if "lang" in r and r["lang"] not in LANGS: errors.append(f"{w} lang must be one of {sorted(LANGS)}")
        src = r.get("source")
        if not isinstance(src, dict) or not src.get("name") or ("url" in src and not str(src["url"]).startswith("http")):
            errors.append(f"{w} source needs a name, and its url (optional) must be http(s)")
        facts = r.get("facts", [])
        if not isinstance(facts, list): errors.append(f"{w} facts must be a list")
        else:
            for j, f in enumerate(facts):
                if not (isinstance(f, list) and len(f) == 2 and all(isinstance(x, str) and x.strip() for x in f)):
                    errors.append(f"{w} facts[{j}] must be [label, value]")
                else:
                    check_text(f"{w} facts[{j}]", f[1], errors)
        ings = r.get("ingredients")
        if not isinstance(ings, list) or not ings: errors.append(f"{w} ingredients must be a non-empty list of groups")
        else:
            for gi, g in enumerate(ings):
                if not isinstance(g, dict) or not isinstance(g.get("items"), list) or not g["items"]:
                    errors.append(f"{w} ingredients[{gi}] needs a non-empty items list"); continue
                for ii, it in enumerate(g["items"]):
                    loc = f"{w} ingredients[{gi}].items[{ii}]"
                    if not isinstance(it, dict): errors.append(f"{loc} must be an object"); continue
                    if set(it) - ITEM_KEYS: errors.append(f"{loc} unknown keys {sorted(set(it) - ITEM_KEYS)}")
                    if not str(it.get("n", "")).strip(): errors.append(f"{loc} n (ingredient) is required")
                    if it.get("o") and not str(it.get("m", "")).strip():
                        errors.append(f"{loc} has an original measure (o) but no metric (m)")
                    if it.get("o") and it.get("o") == it.get("m"):
                        warnings.append(f"{loc} o equals m; leave o out when the original is already metric")
        meth = r.get("method")
        if not isinstance(meth, list) or not meth: errors.append(f"{w} method must be a non-empty list of groups")
        else:
            for gi, g in enumerate(meth):
                if not isinstance(g, dict) or not isinstance(g.get("steps"), list) or not g["steps"]:
                    errors.append(f"{w} method[{gi}] needs a non-empty steps list"); continue
                for si, st in enumerate(g["steps"]):
                    check_text(f"{w} method[{gi}].steps[{si}]", st, errors)
                if "alt" in g and not isinstance(g["alt"], bool):
                    errors.append(f"{w} method[{gi}].alt must be true or false")
        for ni, n in enumerate(r.get("notes", []) or []):
            check_text(f"{w} notes[{ni}]", n, errors)
        if "rating" in r:
            rt = r["rating"]
            if not isinstance(rt, dict) or set(rt) - {"score", "date", "note"}:
                errors.append(f"{w} rating must be an object with score, date and optional note")
            else:
                sc = rt.get("score")
                if not isinstance(sc, (int, float)) or isinstance(sc, bool) or not 1 <= sc <= 10 or (sc * 2) % 1:
                    errors.append(f"{w} rating.score must be 1 to 10 in steps of 0.5")
                if not DATE_RE.match(str(rt.get("date", ""))):
                    errors.append(f"{w} rating.date must be YYYY-MM-DD")
                if "note" in rt and not str(rt["note"]).strip():
                    errors.append(f"{w} rating.note must not be empty; leave it out instead")
        if "photos" in r:
            ph = r["photos"]
            if not isinstance(ph, list) or not ph:
                errors.append(f"{w} photos must be a non-empty list; leave it out instead")
            else:
                for pi, p in enumerate(ph):
                    loc = f"{w} photos[{pi}]"
                    if not isinstance(p, dict) or set(p) - {"src", "date", "caption", "alt"}:
                        errors.append(f"{loc} must be an object with src, date and optional caption/alt"); continue
                    if not PHOTO_RE.match(str(p.get("src", ""))):
                        errors.append(f"{loc}.src must look like photos/<recipe-id>-1.jpg")
                    elif not (HTML_DIR / p["src"]).is_file():
                        warnings.append(f"{loc}.src {p['src']} not found next to index.html")
                    if not DATE_RE.match(str(p.get("date", ""))):
                        errors.append(f"{loc}.date must be YYYY-MM-DD")
        if "quick" in tags:
            mins = 0
            for k, v in (facts if isinstance(facts, list) else []):
                if k in ("Prep", "Cook", "Bake", "Total") and isinstance(v, str):
                    h = re.search(r"(\d+)\s*hr", v); mm = re.search(r"(\d+)\s*min", v)
                    t = (int(h.group(1)) * 60 if h else 0) + (int(mm.group(1)) if mm else 0)
                    mins = t if k == "Total" else mins + t
            if not mins or mins > 30:
                warnings.append(f"{w} tagged 'quick' but the stated times don't show 30 min or less")
    return errors, warnings


def report(recipes, strict=True):
    errors, warnings = validate(recipes)
    for x in warnings: print("WARNING:", x)
    for x in errors: print("ERROR:", x)
    if errors and strict:
        sys.exit(f"{len(errors)} error(s); nothing was saved.")
    return not errors


# ---------------------------------------------------------------- markdown
def pairs(s):
    return PAIR_RE.sub(lambda m: f"{m.group(1)} / {m.group(2)}", s)


def to_markdown(recipes):
    out = ["# Recipe Collection", "",
           "Generated from the recipe data in `index.html` by `recipe_tool.py`. Don't edit this file by hand; it is rebuilt every time a recipe is added or changed.", "",
           "## How measurements are shown", "",
           "In ingredient lists the original measurement comes first, in **bold**. Where it isn't metric, the metric conversion follows in brackets, e.g. **2 tbsp** (30 ml) milk. In methods and notes, measurements read metric / original, e.g. 60 ml / ¼ cup.", "",
           "Conversions are approximate: 1 cup = 240 ml, 1 tbsp = 15 ml, 1 tsp = 5 ml, 1 lb = 450 g, 1 oz = 28 g, 1 inch = 2.5 cm. Weights marked ≈ depend on how the cup or spoon is filled.", ""]
    for cid, label in COURSES:
        group = [r for r in recipes if r["course"] == cid]
        if not group: continue
        out += ["---", "", f"# {label}", ""]
        for r in group:
            out.append(f"## {r['title']}" + (f" — {r['sub']}" if r.get("sub") else ""))
            src = r["source"]
            out.append(f"Source: {src['url']} ({src['name']})  " if src.get("url") else f"Source: {src['name']}  ")
            if src.get("note"): out.append(f"*{src['note']}*  ")
            if r.get("rating"):
                rt = r["rating"]
                out.append(f"My rating: ★ {rt['score']:g}/10 (rated {rt['date']})" + (f" — “{rt['note']}”" if rt.get("note") else "") + "  ")
            for p in r.get("photos", []):
                out.append(f"Photo: {p['src']} (made {p['date']})" + (f" — {p['caption']}" if p.get("caption") else "") + "  ")
            if r.get("facts"):
                out.append(" · ".join(f"{k}: {pairs(v)}" for k, v in r["facts"]))
            out.append("")
            for g in r["ingredients"]:
                out.append(f"**Ingredients — {g['group']}**" if g.get("group") else "**Ingredients**")
                for it in g["items"]:
                    if it.get("o"): q = f"**{it['o']}** ({it['m']}) "
                    elif it.get("m"): q = f"**{it['m']}** "
                    else: q = ""
                    line = f"- {q}{it['n']}"
                    if it.get("x"): line += f", {it['x']}"
                    if it.get("l"): line += f" — *{it['l']}*"
                    out.append(line)
                out.append("")
            n = 0
            for g in r["method"]:
                if g.get("alt"): n = 0
                out.append(f"**Method — {g['group']}**" if g.get("group") else "**Method**")
                for st in g["steps"]:
                    n += 1
                    out.append(f"{n}. {pairs(st)}")
                out.append("")
            if r.get("notes"):
                out.append("**Notes**")
                out += [f"- {pairs(x)}" for x in r["notes"]]
                out.append("")
    return "\n".join(out).rstrip() + "\n"


def write_md(recipes, md_path):
    Path(md_path).write_text(to_markdown(recipes), encoding="utf-8")
    print(f"Rebuilt {md_path}")


# ---------------------------------------------------------------- commands
def insert_sorted(recipes, new):
    """Place a recipe after the last existing recipe of the same course."""
    rank = COURSE_IDS.index(new["course"])
    pos = len(recipes)
    for i, r in enumerate(recipes):
        if COURSE_IDS.index(r["course"]) > rank:
            pos = i; break
    recipes.insert(pos, new)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["list", "check", "add", "remove", "md"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--replace", action="store_true")
    ap.add_argument("--html", default="index.html")
    ap.add_argument("--md", default="recipes.md")
    a = ap.parse_args()
    global HTML_DIR
    HTML_DIR = Path(a.html).resolve().parent

    text, recipes = load(a.html)

    if a.cmd == "list":
        for r in recipes: print(f"{r['course']:<10} {r['id']:<36} {r['title']}")
        print(f"{len(recipes)} recipes")
    elif a.cmd == "check":
        ok = report(recipes, strict=False)
        print("OK" if ok else "FAILED"); sys.exit(0 if ok else 1)
    elif a.cmd == "md":
        report(recipes); write_md(recipes, a.md)
    elif a.cmd == "add":
        if not a.arg: sys.exit("usage: add NEW.json [--replace]")
        new = json.loads(Path(a.arg).read_text(encoding="utf-8"))
        new = new if isinstance(new, list) else [new]
        errs, _ = validate(new)
        if errs:
            for e in errs: print("ERROR:", e)
            sys.exit("The new recipe is invalid; nothing was saved.")
        for r in new:
            existing = next((i for i, x in enumerate(recipes) if x["id"] == r["id"]), None)
            if existing is not None:
                if not a.replace:
                    sys.exit(f"ERROR: a recipe with id '{r['id']}' already exists. Use --replace to overwrite it, or choose a new id.")
                if recipes[existing]["course"] == r["course"]:
                    recipes[existing] = r; print(f"Replaced {r['id']}"); continue
                recipes.pop(existing)
            insert_sorted(recipes, r); print(f"Added {r['id']} ({r['course']})")
        report(recipes); save(a.html, text, recipes); write_md(recipes, a.md)
        print(f"Saved {a.html}: {len(recipes)} recipes")
    elif a.cmd == "remove":
        before = len(recipes)
        recipes = [r for r in recipes if r["id"] != a.arg]
        if len(recipes) == before: sys.exit(f"ERROR: no recipe with id '{a.arg}'")
        report(recipes); save(a.html, text, recipes); write_md(recipes, a.md)
        print(f"Removed {a.arg}. {len(recipes)} recipes left.")


if __name__ == "__main__":
    main()
