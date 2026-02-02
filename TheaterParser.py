from collections import Counter
import sys
import tkinter as tk
from tkinter import filedialog
import fitz  # PyMuPDF
import re
import os
import matplotlib.pyplot as plt

number_words = {
    "ERSTER": 1, "ZWEITER": 2, "DRITTER": 3, "VIERTER": 4,
    "FÜNFTER": 5, "SECHSTER": 6, "SIEBTER": 7, "ACHTER": 8,
    "NEUNTER": 9, "ZEHNTER": 10,
    "EINS": 1, "ZWEI": 2, "DREI": 3, "VIER": 4,
    "FÜNF": 5, "SECHS": 6, "SIEBEN": 7, "ACHT": 8,
    "NEUN": 9, "ZEHN": 10
}

def roman_to_int(s):
    romans = {'I':1,'V':5,'X':10,'L':50,'C':100,'D':500,'M':1000}
    result, prev = 0, 0
    for c in reversed(s):
        if romans[c] < prev:
            result -= romans[c]
        else:
            result += romans[c]
        prev = romans[c]
    return result

def detect_act(line):
    line_text = " ".join(span["text"] for span in line).strip()
    line_clean = line_text.strip().upper().replace(" ", "").replace("-", "").replace("_", "").replace(".", "")

    # Wörter: "ERSTER AKT"
    for word, num in number_words.items():
        if re.fullmatch(rf"^[\W_]*(?:AKT)?[\W_]*(?:{word})[\W_]*(?:AKT)?[\W_]*$", line_clean):
            return num

    # Zahl + AKT (arabisch)
    match = re.fullmatch(r"^[\W_]*(?:AKT)[\W_]*(\d)[\W_]*$", line_clean)
    if match:
        return int(match.group(1))
    match = re.fullmatch(r"^[\W_]*(\d)[\W_]*(?:AKT)[\W_]*$", line_clean)
    if match:
        return int(match.group(1))


    # Römische Zahl + AKT
    match = re.fullmatch(r"^[\W_]*(?:AKT)?[\W_]*(I{1,3}|IV|V|VI{0,3}|IX|X)[\W_]*(?:AKT)?[\W_]*$", line_clean)
    if match:
        return roman_to_int(match.group(1))

    return None


def detect_scene(line):
    line_text = " ".join(span["text"] for span in line).strip()
    line_clean = line_text.strip().upper().replace(" ", "").replace("-", "").replace("_", "").replace(".", "")

    # Wörter: "ERSTER AKT"
    for word, num in number_words.items():
        if re.fullmatch(rf"^(?=.*SZENE)[\W_]*(?:SZENE)?[\W_]*(?:{word})[\W_]*(?:SZENE)?[\W_]*$", line_clean):
            return num

    # Zahl + AKT (arabisch)
    match = re.fullmatch(r"^(?=.*SZENE)[\W_]*(?:SZENE)?[\W_]*(\d)[\W_]*(?:SZENE)?[\W_]*$", line_clean)
    if match:
        return int(match.group(1))


    # Römische Zahl + AKT
    match = re.fullmatch(r"^(?=.*SZENE)[\W_]*(?:SZENE)?[\W_]*(I{1,3}|IV|V|VI{0,3}|IX|X)[\W_]*(?:SZENE)?[\W_]*$", line_clean)
    if match:
        return roman_to_int(match.group(1))

    return None


# -------------------------
# PDF auslesen mit Styles
# -------------------------
def extract_text_with_styles(pdf_path):
    doc = fitz.open(pdf_path)
    data = []

    for page_num, page in enumerate(doc, start=1):
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            for l in b.get("lines", []):
                line_spans = []  # alle Spans dieser Zeile sammeln
                for s in l.get("spans", []):
                    text = s["text"].strip()
                    if not text:
                        continue

                    font = s["font"]
                    style = "normal"
                    if "Bold" in font:
                        style = "bold"
                    elif "Italic" in font or "Oblique" in font:
                        style = "italic"

                    line_spans.append({
                        "page": page_num,
                        "text": text,
                        "style": style,
                        "font": font
                    })

                if line_spans:  # nur hinzufügen, wenn nicht leer
                    data.append(line_spans)

    return data



def count_first_spans(data, max_words=3, min_count=10):
    first_texts = []

    for line in data:
        if not line:
            continue
        first_span = line[0]
        text = first_span["text"]
        if len(text) < 2 and len(line) > 1:
            text = text + line[1]["text"]
        word_count = len(text.split())

        # Nur Spans mit max. max_words Wörtern
        if word_count > max_words:
            continue

        # Nur Spans ohne Zahlen
        if re.search(r'\d', text):
            continue

        first_texts.append(text)

    counter = Counter(first_texts)

    # Nur Spans, die mindestens min_count-mal vorkommen
    filtered = {text: count for text, count in counter.items() if count >= min_count}

    # Nach Häufigkeit sortieren
    return dict(sorted(filtered.items(), key=lambda x: x[1], reverse=True))



def get_cues(data, roles):
    cues = []
    acts = []
    scenes = []
    cueCounter = 0
    actCounter = 0
    sceneCounter = 0
    for line in data:
        if not line:
            continue
        act = detect_act(line)
        if act is not None:
            actCounter = act
            sceneCounter = 0
            acts.append((cueCounter, actCounter))
            continue
        
        if actCounter == 0:
            continue  # Noch kein Akt erkannt

        scene = detect_scene(line)
        if scene is not None:
            sceneCounter = scene
            scenes.append((cueCounter, actCounter, sceneCounter))
            continue

        first_span = line[0]
        text = first_span["text"]
        if len(text) < 2 and len(line) > 1:
            text = text + line[1]["text"]

        if text in roles.keys():
            cueCounter += 1
            cues.append((cueCounter, text))
    return cues, acts, scenes


def plot_roles_and_cues(roles, cues, acts, scenes, out_path):
    sorted_roles = sorted(roles.items(), key=lambda x: x[1], reverse=True)
    role_names = [r for r, _ in sorted_roles]
    role_names_with_counts = [f"{r} ({c})" for r, c in sorted_roles]
    role_counts = [c for _, c in sorted_roles]

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(14, 9),
        gridspec_kw={'height_ratios': [1, 2]},
        sharex=False
    )

    colors = ["#fbbc83" if i % 2 == 0 else "SkyBlue"
        for i in range(len(role_names_with_counts))]

    # --- 1. Diagramm ---
    ax1.barh(role_names_with_counts, role_counts, color=colors)
    ax1.set_xlabel("Einsätze")
    ax1.set_ylabel("Rollen")
    ax1.set_title("Rollenhäufigkeit")
    ax1.invert_yaxis()

    # --- 2. Diagramm ---
    role_index = {role: i for i, role in enumerate(role_names)}
    for i in range(len(role_names)):
        ax2.axhspan(i-0.5, i+0.5,
                    color="#fbbc83" if i % 2 == 0 else "SkyBlue",
                    alpha=0.3, zorder=0)

    for cue_num, role in cues:
        if role in role_index:
            y = role_index[role]
            ax2.scatter(cue_num, y, marker="o", color="black", s=12, zorder=2)

    max_cue = max([c for c, _ in cues], default=0)

    # --- Platzierung von Labels ---
    top_row = -1.3   # Höhe für Akt-Labels
    bottom_row = -2  # Höhe für Szenenlabels (falls vorhanden)

    # Titel ganz oben
    ax2.set_title("Einsatzverteilung über Akte und Scenen",
                  pad=50 if scenes else 25)

    # Akte einzeichnen
    for cue_num, act_num in acts:
        ax2.axvline(cue_num, color="red", linestyle="-", alpha=0.7, zorder=1)
        ax2.text(cue_num, top_row, f"Akt {act_num}",
                 rotation=0, color="red", va="bottom", ha="center")

    # Szenen darunter (falls vorhanden)
    if scenes:
        upper = False
        for cue_num, act_num, scene_num in scenes:

            ax2.axvline(cue_num, color="orange", linestyle="--", alpha=0.6, zorder=1)
            ax2.text(cue_num, bottom_row - (0.7 if upper else 0), f"S{scene_num}",
                     rotation=0, color="orange", va="bottom", ha="center")
            upper = not upper

    # --- Achsen ---
    ax2.set_xlabel("Einsätze")
    ax2.set_ylabel("Rollen")
    ax2.set_yticks(range(len(role_names)))
    ax2.set_yticklabels(role_names)
    ax2.invert_yaxis()
    ax2.set_xlim(0.5, max_cue + 0.5)

    plt.tight_layout()
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


# -------------------------
# Hauptprogramm mit File-Dialog
# -------------------------
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # Fenster verstecken

    pdf_path = filedialog.askopenfilename(
        title="Wähle ein Theaterstück-PDF",
        filetypes=[("PDF Dateien", "*.pdf")]
    )


    if pdf_path:
        print(f"Verarbeite: {pdf_path}")
        text_data = extract_text_with_styles(pdf_path)
        roles = count_first_spans(text_data)

        print("\nGefundene Rollen und Häufigkeiten:")
        for text, count in roles.items():
            print(f"{text}: {count}")

        cues, acts, scenes = get_cues(text_data, roles)
        print(f"\nAnzahl Akte: {len(acts)}")


    
        folder = os.path.dirname(pdf_path)
        basename = os.path.splitext(os.path.basename(pdf_path))[0]
        out_img = os.path.join(folder, f"Rollenverteilung_{basename}.png")

        plot_roles_and_cues(roles, cues, acts, scenes, out_img)
        print(f"\nDiagramm erstellt: {out_img}")
    else:
        print("Keine Datei ausgewählt.")
    
    input("\nDrücke Enter, um das Programm zu beenden...")