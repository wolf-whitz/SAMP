import unicodedata
import re
import random
from itertools import product

LEET_MAP = {
    "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "6": "g", "7": "t", "8": "b", "9": "g",
    "$": "s", "@": "a", "!": "i", "€": "e", "£": "l", "¥": "y", "§": "s"
}

HOMOGLYPHS = {
    "a": ["а", "𝐚", "𝖆", "ᵃ", "ⓐ"], "b": ["𝐛", "𝖇", "ᵇ"], "c": ["с", "𝐜", "𝖈", "ᶜ"],
    "d": ["𝐝", "𝖉", "ᵈ"], "e": ["е", "𝐞", "𝖊", "ᵉ", "ⓔ"], "f": ["𝐟", "𝖋", "ⓕ"],
    "g": ["𝐠", "𝖌"], "h": ["𝐡", "𝖍"], "i": ["і", "𝐢", "𝖎", "ᶦ", "ⓘ"], "j": ["𝐣", "𝖏"],
    "k": ["𝐤", "𝖐"], "l": ["𝐥", "𝖑", "ⓛ"], "m": ["𝐦", "𝖒"], "n": ["𝐧", "𝖓", "ⓝ"],
    "o": ["о", "𝐨", "𝖔", "ᵒ", "ⓞ"], "p": ["р", "𝐩", "𝖕"], "q": ["𝐪", "𝖖"],
    "r": ["𝐫", "𝖗", "ⓡ"], "s": ["ѕ", "𝐬", "𝖘", "ᵗˢ", "ⓢ"], "t": ["𝐭", "𝖙", "ⓣ"],
    "u": ["υ", "𝐮", "𝖚", "ᵘ", "ⓤ"], "v": ["𝐯", "𝖛", "ⓥ"], "w": ["𝐰", "𝖜", "ⓦ"],
    "x": ["х", "𝐱", "𝖝", "ⓧ"], "y": ["у", "𝐲", "𝖞", "ⓨ"], "z": ["𝐳", "𝖟", "ⓩ"]
}

ZERO_WIDTH_CHARS = ["\u200b", "\u200c", "\u200d", "\ufeff"]
SPLITTER_CHARS = [".", "-", "_", "*", "/", "\\"]

def normalize_word(w: str) -> str:
    w = unicodedata.normalize("NFKD", w)
    w = "".join(LEET_MAP.get(c, c.lower()) for c in w)
    w = re.sub(r"[^\w]", "", w)
    w = re.sub(r"(.)\1{2,}", r"\1", w)
    return w

def apply_homoglyphs(w: str) -> str:
    return "".join(random.choice(HOMOGLYPHS.get(c, [c])) if random.random() < 0.5 else c for c in w)

def apply_zero_width(w: str) -> str:
    out = []
    for c in w:
        out.append(c)
        if random.random() < 0.4:
            out.append(random.choice(ZERO_WIDTH_CHARS))
    return "".join(out)

def apply_splitters(w: str) -> str:
    return random.choice(SPLITTER_CHARS).join(list(w))

def apply_fullwidth(w: str) -> str:
    return "".join(chr(ord(c)+0xFEE0) if '!' <= c <= '~' else c for c in w)

def generate_variants(word: str, max_variants: int = 10):
    word = normalize_word(word)
    variants = set()
    variants.add(word)
    transformations = [
        apply_homoglyphs,
        apply_zero_width,
        apply_splitters,
        apply_fullwidth,
        lambda x: x.translate(str.maketrans("aegiost", "4361057"))
    ]
    for t in transformations:
        v = t(word)
        variants.add(normalize_word(v))
        if len(variants) >= max_variants:
            break
    return variants

def split_text(text: str):
    raw_tokens = re.findall(r"\b[\w\.\!\$\@\#\%\&\*\-]+\b", text)
    normalized = set()
    for t in raw_tokens:
        n = normalize_word(t)
        if n:
            normalized.add(n)
    return list(normalized)

def expand_tokens(tokens: list):
    all_variants = set()
    for tok in tokens:
        all_variants.update(generate_variants(tok))
    return list(all_variants)
