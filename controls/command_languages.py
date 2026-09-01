"""Slowniki komend glosowych per jezyk.

Klucze slownikow to frazy tak, jak moze je zwrocic Whisper w danym jezyku,
wartosci to sloty: FLASH i SUMM2 sa podmieniane na skonfigurowane klawisze,
reszta to doslowne klawisze ("s", "b", "p", "escape", "random") albo litery
umiejetnosci ("q", "w", "e", "r").

Jezyk wybiera prefiks locale (pl_PL -> pl). Domyslnie aktywny jest tylko
slownik biezacego jezyka; ustawienie merge_command_languages laczy wszystkie.

Przetestowany zostal polski. Pozostale jezyki zawieraja rozsadne warianty
mowione (oficjalne nazwy czarow przywolywacza i potoczne anglicyzmy), ale sa
nietestowane z zywym graczem.
"""

from __future__ import annotations

FLASH = "FLASH"
SUMM2 = "SUMM2"

# --- litery Q W E R ---------------------------------------------------

# Doslowne litery dzialaja w kazdym jezyku (Whisper czesto zwraca lacinskie
# litery nawet w tekscie azjatyckim).
LETTERS_UNIVERSAL: dict[str, str] = {
    "q": "q",
    "w": "w",
    "e": "e",
    "r": "r",
}

LETTERS_BY_LANG: dict[str, dict[str, str]] = {
    "pl": {
        "kju": "q", "ku": "q", "kiu": "q", "ok": "q",
        "wu": "w", "vu": "w", "bo": "w",
        "je": "e", "a": "e", "tak": "e", "ale": "e",
        "er": "r", "ar": "r", "ult": "r", "ulti": "r",
    },
    "en": {
        "cue": "q", "queue": "q",
        "double u": "w",
        "ee": "e",
        "are": "r", "ar": "r", "ult": "r", "ulti": "r", "ultimate": "r",
    },
    "de": {
        "ku": "q", "kuh": "q", "cool": "q",
        "we": "w", "weh": "w", "doppel u": "w",
        "er": "r", "err": "r", "ult": "r", "ulti": "r",
    },
    "fr": {"cu": "q", "double ve": "w", "eu": "e", "erre": "r", "ult": "r"},
    "es": {"cu": "q", "doble u": "w", "erre": "r", "ulti": "r"},
    "it": {"cu": "q", "doppia vu": "w", "erre": "r", "ulti": "r"},
    "pt": {"que": "q", "dablio": "w", "erre": "r", "ulti": "r"},
    "ru": {"кью": "q", "ку": "q", "дабл ю": "w", "и": "e", "эр": "r", "ульта": "r", "ульт": "r"},
    "tr": {"kü": "q", "çift ve": "w", "re": "r", "ulti": "r"},
    "ko": {"큐": "q", "더블유": "w", "이": "e", "알": "r", "궁": "r", "궁극기": "r"},
    "ja": {"キュー": "q", "ダブリュー": "w", "イー": "e", "アール": "r", "ウルト": "r"},
    "zh": {"大招": "r", "大抽": "r", "大超": "r"},
    "th": {"คิว": "q", "ดับเบิลยู": "w", "อี": "e", "อาร์": "r"},
    "vi": {"quy": "q", "vê kép": "w", "e": "e", "rờ": "r", "chiêu cuối": "r"},
    "id": {"ki": "q", "we": "w", "er": "r", "ulti": "r"},
    "ar": {"كيو": "q", "دبليو": "w", "اي": "e", "ار": "r"},
    "cs": {"kve": "q", "dvojite ve": "w", "er": "r", "ulta": "r"},
    "el": {"κιου": "q", "νταμπλγιου": "w", "ρο": "r"},
    "hu": {"kú": "q", "dupla vé": "w", "er": "r", "ulti": "r"},
    "ro": {"chiu": "q", "dublu ve": "w", "re": "r", "ulti": "r"},
}

# Rozmyte warianty liter: pomylki, ktore Whisper realnie robi.
LETTER_FUZZY_BY_LANG: dict[str, dict[str, str]] = {
    "pl": {
        "ciu": "q", "tiu": "q", "czu": "q", "chcial": "q", "dlaczego": "q",
        "dzien dobry": "q", "ka": "q",
        "buch": "w", "wluch": "w", "wy": "w", "ty": "w",
        "wlo": "w", "wlu": "w", "wol": "w",
        "low": "w", "wol": "w", "wuf": "w", "luf": "w",
        "wiem": "w", "zim": "w", "wiesz": "w", "zbyt": "w",
        "eh": "e", "eee": "e", "ej": "e", "we": "e", "wee": "e", "wen": "e",
        "klo": "q", "kwu": "q", "kol": "q", "kul": "q", "kwil": "q", "kul": "q",
        "altaj": "r", "ulty": "r",
        "uld": "r", "olt": "r", "olde": "r", "wojt": "r",
        "ultymat": "r", "ul": "r", "ur": "r", "rka": "r",
    },
    "en": {
        "thank you": "q",
        "lol": "w",
        "bye": "e",
        "ultimate": "r",
    },
}

# --- komendy dodatkowe ------------------------------------------------

# Krotkie miedzynarodowe skroty aktywne zawsze.
EXTRAS_UNIVERSAL: dict[str, str] = {
    "flash": FLASH,
    "tp": SUMM2,
    "esc": "escape",
    "stop": "s",
}

EXTRAS_BY_LANG: dict[str, dict[str, str]] = {
    "en": {
        "heal": SUMM2, "barrier": SUMM2, "shield": SUMM2, "cleanse": SUMM2,
        "clean": SUMM2, "ignite": SUMM2, "exhaust": SUMM2, "ghost": SUMM2,
        "teleport": SUMM2, "smite": SUMM2,
        "back": "b", "recall": "b", "base": "b",
        "shop": "p", "store": "p",
        "escape": "escape", "cancel": "escape",
        "random": "random",
        "halt": "s",
    },
    "pl": {
        "flasz": FLASH, "blysk": FLASH, "flas": FLASH, "bo jest": FLASH,
        "zlasz": FLASH, "klasz": FLASH, "slasz": FLASH,
        "hil": SUMM2, "leczenie": SUMM2, "uzdrowienie": SUMM2,
        "bariera": SUMM2, "tarcza": SUMM2, "oczyszczenie": SUMM2,
        "podpalenie": SUMM2, "ignajt": SUMM2, "wyczerpanie": SUMM2,
        "duch": SUMM2, "teleportacja": SUMM2, "teleport": SUMM2,
        "karanie": SUMM2, "smajt": SUMM2,
        "zatrzymaj": "s", "stoj": "s",
        "baza": "b", "powrot": "b",
        "sklep": "p",
        "anuluj": "escape",
        "losowa": "random", "losowo": "random", "cokolwiek": "random",
        "niewygodnie mi sie siedzi": "escape",
        "niewdzieczna gowno gra": "escape",
        "no i wylaczam streama": "escape",
    },
    "de": {
        "blitz": FLASH,
        "heilung": SUMM2, "barriere": SUMM2, "läuterung": SUMM2,
        "entzünden": SUMM2, "erschöpfung": SUMM2, "geist": SUMM2,
        "teleport": SUMM2, "teleportation": SUMM2, "zerschmettern": SUMM2,
        "stopp": "s", "halt": "s",
        "zurück": "b", "basis": "b",
        "laden": "p", "shop": "p",
        "abbrechen": "escape",
    },
    "fr": {
        "saut éclair": FLASH, "éclair": FLASH,
        "soin": SUMM2, "barrière": SUMM2, "purge": SUMM2,
        "embrasement": SUMM2, "épuisement": SUMM2, "fantôme": SUMM2,
        "téléportation": SUMM2, "téléport": SUMM2, "châtiment": SUMM2,
        "retour": "b", "base": "b",
        "boutique": "p",
        "annuler": "escape",
    },
    "es": {
        "destello": FLASH,
        "curación": SUMM2, "barrera": SUMM2, "purificar": SUMM2,
        "prender": SUMM2, "agotamiento": SUMM2, "fantasmal": SUMM2,
        "teletransporte": SUMM2, "castigo": SUMM2,
        "para": "s", "alto": "s",
        "atrás": "b", "base": "b",
        "tienda": "p",
        "cancelar": "escape",
    },
    "it": {
        "lampo": FLASH,
        "cura": SUMM2, "barriera": SUMM2, "purificazione": SUMM2,
        "incendiare": SUMM2, "sfinimento": SUMM2, "fantasma": SUMM2,
        "teletrasporto": SUMM2, "punizione": SUMM2,
        "indietro": "b", "base": "b",
        "negozio": "p",
        "annulla": "escape",
    },
    "pt": {
        "curar": SUMM2, "cura": SUMM2, "barreira": SUMM2, "purificar": SUMM2,
        "incendiar": SUMM2, "exaustão": SUMM2, "fantasma": SUMM2,
        "teleporte": SUMM2, "golpear": SUMM2,
        "para": "s",
        "voltar": "b", "base": "b",
        "loja": "p",
        "cancelar": "escape",
    },
    "ru": {
        "флэш": FLASH, "скачок": FLASH,
        "лечение": SUMM2, "исцеление": SUMM2, "барьер": SUMM2,
        "очищение": SUMM2, "поджог": SUMM2, "воспламенение": SUMM2,
        "истощение": SUMM2, "призрак": SUMM2, "телепорт": SUMM2,
        "телепортация": SUMM2, "кара": SUMM2,
        "стоп": "s",
        "назад": "b", "база": "b",
        "магазин": "p",
        "отмена": "escape",
    },
    "tr": {
        "flaş": FLASH,
        "iyileştirme": SUMM2, "bariyer": SUMM2, "arındırma": SUMM2,
        "tutuşturma": SUMM2, "bitkinlik": SUMM2, "hayalet": SUMM2,
        "ışınlanma": SUMM2, "çarpma": SUMM2,
        "dur": "s",
        "geri": "b", "üs": "b",
        "market": "p",
        "iptal": "escape",
    },
    "ko": {
        "점멸": FLASH, "플래시": FLASH,
        "전멸": FLASH, "전면": FLASH,
        "회복": SUMM2, "힐": SUMM2, "방어막": SUMM2, "배리어": SUMM2,
        "정화": SUMM2, "점화": SUMM2, "탈진": SUMM2, "유체화": SUMM2,
        "순간이동": SUMM2, "텔포": SUMM2, "강타": SUMM2,
        "정지": "s", "멈춰": "s",
        "귀환": "b",
        "상점": "p",
        "취소": "escape",
    },
    "ja": {
        "フラッシュ": FLASH,
        "回復": SUMM2, "ヒール": SUMM2, "バリア": SUMM2,
        "クレンズ": SUMM2, "浄化": SUMM2, "イグナイト": SUMM2, "点火": SUMM2,
        "イグゾースト": SUMM2, "ゴースト": SUMM2,
        "テレポート": SUMM2, "スマイト": SUMM2,
        "ストップ": "s", "止まれ": "s",
        "リコール": "b", "帰還": "b",
        "ショップ": "p",
        "キャンセル": "escape",
    },
    # Whisper potrafi zwrocic zapis uproszczony albo tradycyjny niezaleznie od
    # locale, wiec slownik zh zawiera oba.
    "zh": {
        "闪现": FLASH, "閃現": FLASH, "閃線": FLASH, "闪线": FLASH,
        "治疗": SUMM2, "治療": SUMM2, "护盾": SUMM2, "護盾": SUMM2,
        "屏障": SUMM2,
        "净化": SUMM2, "淨化": SUMM2, "点燃": SUMM2, "點燃": SUMM2,
        "虚弱": SUMM2, "虛弱": SUMM2,
        "疾跑": SUMM2, "幽灵疾步": SUMM2, "幽靈疾步": SUMM2,
        "传送": SUMM2, "傳送": SUMM2, "惩戒": SUMM2, "懲戒": SUMM2,
        "停止": "s", "停": "s",
        "回城": "b",
        "商店": "p",
        "取消": "escape",
    },
    "th": {
        "แฟลช": FLASH,
        "ฮีล": SUMM2, "รักษา": SUMM2, "เกราะ": SUMM2,
        "จุดไฟ": SUMM2, "โกสต์": SUMM2,
        "เทเลพอร์ต": SUMM2, "สไมท์": SUMM2,
        "หยุด": "s",
        "กลับฐาน": "b", "กลับ": "b",
        "ร้านค้า": "p",
        "ยกเลิก": "escape",
    },
    "vi": {
        "tốc biến": FLASH,
        "hồi máu": SUMM2, "trị thương": SUMM2, "lá chắn": SUMM2,
        "khiên": SUMM2, "kiệt sức": SUMM2, "thiêu đốt": SUMM2,
        "tốc hành": SUMM2, "thanh tẩy": SUMM2,
        "dịch chuyển": SUMM2, "trừng phạt": SUMM2,
        "dừng": "s", "dừng lại": "s",
        "về nhà": "b",
        "cửa hàng": "p",
        "hủy": "escape",
    },
    "id": {
        "penyembuhan": SUMM2, "heal": SUMM2, "penghalang": SUMM2,
        "pembersihan": SUMM2, "bakar": SUMM2, "kelelahan": SUMM2,
        "hantu": SUMM2, "teleportasi": SUMM2, "smite": SUMM2,
        "berhenti": "s",
        "kembali": "b",
        "toko": "p",
        "batal": "escape",
    },
    "ar": {
        "فلاش": FLASH,
        "علاج": SUMM2, "شفاء": SUMM2, "حاجز": SUMM2,
        "تطهير": SUMM2, "إشعال": SUMM2, "إنهاك": SUMM2,
        "شبح": SUMM2, "انتقال": SUMM2, "نقل": SUMM2, "ضربة": SUMM2,
        "توقف": "s", "قف": "s",
        "عودة": "b",
        "متجر": "p",
        "إلغاء": "escape",
    },
    "cs": {
        "blesk": FLASH,
        "léčení": SUMM2, "bariéra": SUMM2, "očista": SUMM2,
        "zapálení": SUMM2, "vyčerpání": SUMM2, "duch": SUMM2,
        "teleport": SUMM2, "úder": SUMM2,
        "stůj": "s",
        "zpět": "b", "základna": "b",
        "obchod": "p",
        "zrušit": "escape",
    },
    "el": {
        "φλας": FLASH,
        "θεραπεία": SUMM2, "φράγμα": SUMM2, "κάθαρση": SUMM2,
        "ανάφλεξη": SUMM2, "εξάντληση": SUMM2, "φάντασμα": SUMM2,
        "τηλεμεταφορά": SUMM2, "σμάιτ": SUMM2,
        "σταμάτα": "s", "στοπ": "s",
        "πίσω": "b", "βάση": "b",
        "μαγαζί": "p",
        "ακύρωση": "escape",
    },
    "hu": {
        "villanás": FLASH,
        "gyógyítás": SUMM2, "pajzs": SUMM2, "tisztítás": SUMM2,
        "felgyújtás": SUMM2, "kimerítés": SUMM2, "szellem": SUMM2,
        "teleport": SUMM2, "lesújtás": SUMM2,
        "állj": "s",
        "vissza": "b", "bázis": "b",
        "bolt": "p",
        "mégse": "escape",
    },
    "ro": {
        "vindecare": SUMM2, "barieră": SUMM2, "purificare": SUMM2,
        "aprindere": SUMM2, "epuizare": SUMM2, "fantomă": SUMM2,
        "teleportare": SUMM2, "lovitură": SUMM2,
        "oprește": "s",
        "înapoi": "b", "bază": "b",
        "magazin": "p",
        "anulează": "escape",
    },
}

# --- slowa laczace w lancuchach komend --------------------------------

# Wypowiadajac lancuch ludzie wtracaja spojniki: "kju i wu", "q then w".
# Takie slowa sa pomijane, ale dopiero gdy nie sa komenda: polskie "a" znaczy
# E, wiec najpierw zawsze probujemy dopasowania.
CONNECTORS_BY_LANG: dict[str, set[str]] = {
    "pl": {"i", "oraz", "potem", "nastepnie", "plus", "no", "to", "tez"},
    "en": {"and", "then", "plus", "also"},
    "de": {"und", "dann", "danach"},
    "fr": {"et", "puis", "ensuite"},
    "es": {"y", "luego", "despues"},
    "it": {"poi", "dopo"},
    "pt": {"depois", "entao"},
    "ru": {"потом", "затем", "далее"},
    "tr": {"sonra", "ardindan"},
    "cs": {"pak", "potom"},
    "el": {"και", "μετα"},
    "hu": {"aztan", "utana"},
    "ro": {"apoi", "dupa"},
    "id": {"lalu", "kemudian"},
    "vi": {"roi", "sau do"},
    "th": {"แลว"},
    "ko": {"그리고", "다음"},
    "ja": {"それから", "つぎ"},
    "zh": {"然后", "接着"},
    "ar": {"ثم"},
}


def combo_connectors(locale: str) -> set[str]:
    """Slowa do pominiecia w lancuchu komend dla danego jezyka."""
    return CONNECTORS_BY_LANG.get(language_prefix(locale), CONNECTORS_BY_LANG["en"])


SUPPORTED_PREFIXES = sorted(set(EXTRAS_BY_LANG) | set(LETTERS_BY_LANG))


def language_prefix(locale: str) -> str:
    """pl_PL -> pl, zh_TW -> zh."""
    return (locale or "pl_PL").split("_")[0].lower()
