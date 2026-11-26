"""Slovenské popisy hodnôt VERIS pre aplikáciu.

Model aj databáza pracujú s pôvodnými hodnotami (napríklad hacking:SQLi). Preklad sa používa
iba na zobrazenie cez format_func, takže vstup do opatrenia.py sa nemení.
"""

AKTOR_TYPY = {
    "external": "Vonkajší útočník",
    "internal": "Zamestnanec",
    "partner": "Partner",
    "unknown": "Neznámy",
}

AKCIA_TYPY = {
    "hacking": "Hacking",
    "malware": "Malvér",
    "social": "Sociálne inžinierstvo",
    "error": "Chyba",
    "misuse": "Zneužitie oprávnení",
    "physical": "Fyzický útok",
    "environmental": "Prírodné vplyvy",
    "unknown": "Neznámy",
}

AKTOR_VARIETY = {
    "Acquaintance": "známy obete",
    "Activist": "aktivista",
    "Competitor": "konkurent",
    "Customer": "zákazník",
    "Force majeure": "vyššia moc",
    "Former employee": "bývalý zamestnanec",
    "Nation-state": "štát",
    "Organized crime": "organizovaný zločin",
    "Other": "iný",
    "State-affiliated": "napojený na štát",
    "Terrorist": "terorista",
    "Unaffiliated": "nezávislý jednotlivec",
    "Unknown": "neznámy",
    "Call center": "call centrum",
    "Cashier": "pokladník",
    "Developer": "vývojár",
    "Doctor or nurse": "lekár alebo sestra",
    "End-user": "bežný používateľ",
    "Executive": "vedenie",
    "Finance": "financie",
    "Guard": "strážnik",
    "Helpdesk": "helpdesk",
    "Human resources": "personálne oddelenie",
    "Maintenance": "údržba",
    "Manager": "manažér",
    "System admin": "správca systému",
}

AKCIA_VARIETY = {
    # chyby
    "Classification error": "chybná klasifikácia",
    "Data entry error": "chyba pri zadávaní údajov",
    "Disposal error": "chybná likvidácia",
    "Gaffe": "nedbalé vyzradenie",
    "Loss": "strata",
    "Maintenance error": "chyba pri údržbe",
    "Malfunction": "porucha",
    "Misconfiguration": "chybná konfigurácia",
    "Misdelivery": "doručenie nesprávnemu adresátovi",
    "Programming error": "chyba v programe",
    "Publishing error": "chybné zverejnenie",
    # hacking
    "Abuse of functionality": "zneužitie funkcie aplikácie",
    "AitM": "útok sprostredkovateľa (AitM)",
    "Backdoor": "zadné vrátka",
    "Brute force": "hádanie hesiel hrubou silou",
    "Buffer overflow": "pretečenie zásobníka",
    "DoS": "odopretie služby (DoS)",
    "Exploit misconfig": "zneužitie chybnej konfigurácie",
    "Exploit vuln": "zneužitie zraniteľnosti",
    "Forced browsing": "vynútené prehliadanie",
    "Path traversal": "prechod adresármi",
    "SQLi": "SQL injection",
    "Use of stolen creds": "ukradnuté prihlasovacie údaje",
    "XSS": "cross-site scripting (XSS)",
    # malvér
    "Adminware": "nástroje správcu",
    "Backdoor or C2": "zadné vrátka alebo riadiaci server",
    "C2": "riadiaci server (C2)",
    "Capture app data": "zachytávanie údajov aplikácie",
    "Capture stored data": "zber uložených údajov",
    "Destroy data": "zničenie údajov",
    "Disable controls": "vypnutie ochrany",
    "Downloader": "sťahovač ďalšieho malvéru",
    "Export data": "vynášanie údajov",
    "Packet sniffer": "odpočúvanie sieťovej prevádzky",
    "Password dumper": "získavanie hesiel",
    "RAM scraper": "čítanie pamäte RAM",
    "Ransomware": "ransomvér",
    "Rootkit": "rootkit",
    "Scan network": "skenovanie siete",
    "Spam": "rozosielanie spamu",
    "Spyware/Keylogger": "spyvér alebo keylogger",
    # zneužitie oprávnení
    "Data mishandling": "nesprávne zaobchádzanie s údajmi",
    "Email misuse": "zneužitie e-mailu",
    "Illicit content": "nelegálny obsah",
    "Knowledge abuse": "zneužitie znalostí",
    "Net misuse": "zneužitie siete",
    "Possession abuse": "zneužitie zvereného majetku",
    "Privilege abuse": "zneužitie oprávnení",
    "Snap picture": "odfotenie údajov",
    "Unapproved hardware": "neschválený hardvér",
    "Unapproved software": "neschválený softvér",
    "Unapproved workaround": "obchádzanie postupov",
    # fyzický útok
    "Assault": "napadnutie",
    "Bypassed controls": "obídenie ochrany",
    "Disabled controls": "vyradenie ochrany",
    "Skimmer": "skimmer",
    "Snooping": "sliedenie",
    "Surveillance": "sledovanie",
    "Tampering": "neoprávnená úprava zariadenia",
    "Theft": "krádež",
    # sociálne inžinierstvo
    "Bribery": "úplatok",
    "Extortion": "vydieranie",
    "Forgery": "falšovanie",
    "Influence": "ovplyvňovanie",
    "Phishing": "phishing",
    "Pretexting": "podvodná zámienka",
    # spoločné
    "Other": "iné",
    "Unknown": "neznáme",
}

AKCIA_VEKTORY = {
    "Carelessness": "nepozornosť",
    "Inadequate personnel": "nedostatok personálu",
    "Inadequate processes": "nedostatočné postupy",
    "Inadequate technology": "nedostatočná technológia",
    "Random error": "náhodná chyba",
    "Backdoor": "zadné vrátka",
    "Command shell": "príkazový riadok",
    "Desktop sharing": "zdieľanie plochy",
    "Desktop sharing software": "softvér na zdieľanie plochy",
    "Partner": "cez partnera",
    "Physical access": "fyzický prístup",
    "VPN": "VPN",
    "Web application": "webová aplikácia",
    "Direct install": "priama inštalácia",
    "Download by malware": "stiahnuté iným malvérom",
    "Email attachment": "príloha e-mailu",
    "Email link": "odkaz v e-maile",
    "Remote injection": "vzdialené vloženie",
    "Web application - download": "stiahnutie z webu",
    "Web application - drive-by": "nákaza pri návšteve webu",
    "LAN access": "prístup z lokálnej siete",
    "Non-corporate": "mimo firemných zariadení",
    "Remote access": "vzdialený prístup",
    "Partner facility": "priestory partnera",
    "Partner vehicle": "vozidlo partnera",
    "Personal residence": "bydlisko",
    "Personal vehicle": "osobné vozidlo",
    "Public facility": "verejný priestor",
    "Public vehicle": "verejná doprava",
    "Victim grounds": "areál organizácie",
    "Victim public area": "verejná časť priestorov organizácie",
    "Victim secure area": "zabezpečená časť priestorov organizácie",
    "Victim work area": "pracovisko organizácie",
    "Documents": "dokumenty",
    "Email": "e-mail",
    "In-person": "osobne",
    "Phone": "telefón",
    "SMS": "SMS",
    "Software": "softvér",
    "Other": "iné",
    "Unknown": "neznámy",
}

AKTIVUM_KATEGORIE = {
    "M": "Nosič dát",
    "N": "Sieťové zariadenie",
    "P": "Osoba",
    "S": "Server",
    "T": "Terminál",
    "U": "Zariadenie používateľa",
}

AKTIVUM_VARIETY = {
    "Disk drive": "pevný disk",
    "Disk media": "disk (CD, DVD)",
    "Documents": "dokumenty",
    "Flash drive": "USB kľúč",
    "Payment card": "platobná karta",
    "Tapes": "pásky",
    "Camera": "kamera",
    "Firewall": "firewall",
    "PBX": "telefónna ústredňa",
    "Router or switch": "smerovač alebo prepínač",
    "Telephone": "telefón",
    "WLAN": "Wi-Fi sieť",
    "Call center": "call centrum",
    "Cashier": "pokladník",
    "Customer": "zákazník",
    "End-user or employee": "používateľ alebo zamestnanec",
    "Executive": "vedenie",
    "Finance": "financie",
    "Helpdesk": "helpdesk",
    "Human resources": "personalista",
    "Partner": "partner",
    "System admin": "správca systému",
    "Authentication": "autentifikácia",
    "Backup": "zálohy",
    "Code repository": "repozitár kódu",
    "DNS": "DNS",
    "Database": "databáza",
    "Directory": "adresárová služba",
    "File": "súborový server",
    "ICS": "priemyselný riadiaci systém",
    "Mail": "poštový server",
    "Mainframe": "sálový počítač",
    "POS controller": "riadenie pokladníc",
    "Payment switch": "platobná brána",
    "Remote access": "vzdialený prístup",
    "Web application": "webová aplikácia",
    "ATM": "bankomat",
    "Gas terminal": "terminál čerpacej stanice",
    "Kiosk": "kiosk",
    "PED pad": "platobný terminál s PIN",
    "Desktop": "stolný počítač",
    "Desktop or laptop": "stolný počítač alebo notebook",
    "Laptop": "notebook",
    "Media": "médium",
    "Mobile phone": "mobilný telefón",
    "POS terminal": "pokladničný terminál",
    "Tablet": "tablet",
    "Other": "iné",
    "Unknown": "neznáme",
}

TYPY_DAT = {
    "Bank": "Bankové údaje",
    "Classified": "Utajované skutočnosti",
    "Copyrighted": "Autorské diela",
    "Credentials": "Prihlasovacie údaje",
    "Internal": "Interné údaje",
    "Medical": "Zdravotné údaje",
    "Other": "Iné",
    "Payment": "Platobné karty",
    "Personal": "Osobné údaje",
    "Secrets": "Obchodné tajomstvo",
    "Sensitive Personal": "Citlivé osobné údaje",
    "Source code": "Zdrojový kód",
    "System": "Systémové údaje",
    "Unknown": "Neznáme",
    "Virtual currency": "Virtuálna mena",
}

MOTIV = {
    "Convenience": "Pohodlnosť",
    "Espionage": "Špionáž",
    "Fear": "Strach",
    "Financial": "Finančný zisk",
    "Fun": "Zábava",
    "Grudge": "Pomsta",
    "Ideology": "Ideológia",
    "Other": "Iný",
    "Secondary": "Prostriedok ďalšieho útoku",
    "Unknown": "Neznámy",
}

SPOSOB_ODHALENIA = {
    "external": "Tretia strana",
    "internal": "Vlastné zistenie",
    "partner": "Partner",
    "other": "Iný",
    "unknown": "Neznámy",
}

KRAJINY = {
    "US": "Spojené štáty", "GB": "Spojené kráľovstvo", "CA": "Kanada", "Unknown": "Neznáma", "iná": "Iná krajina",
    "AE": "Spojené arabské emiráty", "AM": "Arménsko", "AR": "Argentína", "AT": "Rakúsko", "AU": "Austrália",
    "AZ": "Azerbajdžan", "BD": "Bangladéš", "BE": "Belgicko", "BR": "Brazília", "CH": "Švajčiarsko",
    "CK": "Cookove ostrovy", "CL": "Čile", "CN": "Čína", "CY": "Cyprus", "CZ": "Česko", "DE": "Nemecko",
    "DK": "Dánsko", "EC": "Ekvádor", "EG": "Egypt", "ES": "Španielsko", "FI": "Fínsko", "FR": "Francúzsko",
    "HK": "Hongkong", "ID": "Indonézia", "IE": "Írsko", "IL": "Izrael", "IN": "India", "IR": "Irán",
    "IT": "Taliansko", "JP": "Japonsko", "KE": "Keňa", "KP": "Severná Kórea", "KR": "Južná Kórea",
    "KZ": "Kazachstan", "LT": "Litva", "MX": "Mexiko", "MY": "Malajzia", "NG": "Nigéria", "NL": "Holandsko",
    "NO": "Nórsko", "NZ": "Nový Zéland", "PA": "Panama", "PE": "Peru", "PH": "Filipíny", "PK": "Pakistan",
    "PL": "Poľsko", "PR": "Portoriko", "RO": "Rumunsko", "RU": "Rusko", "SE": "Švédsko", "SG": "Singapur",
    "SY": "Sýria", "TH": "Thajsko", "TR": "Turecko", "TW": "Taiwan", "UA": "Ukrajina",
    "UM": "Menšie odľahlé ostrovy USA", "VE": "Venezuela", "VN": "Vietnam", "ZA": "Južná Afrika",
    "SK": "Slovensko", "HU": "Maďarsko", "SI": "Slovinsko", "HR": "Chorvátsko", "PT": "Portugalsko",
    "GR": "Grécko", "BG": "Bulharsko", "LV": "Lotyšsko", "EE": "Estónsko", "IS": "Island", "LU": "Luxembursko",
    "SA": "Saudská Arábia", "QA": "Katar", "CO": "Kolumbia", "LK": "Srí Lanka", "NP": "Nepál", "GH": "Ghana",
}


def _prefixed(value, types, details):
    """typ:podrobnosť -> 'Typ · podrobnosť'."""
    prefix, _, rest = value.partition(":")
    if not rest:
        return details.get(value, value)
    return f"{types.get(prefix, prefix)} · {details.get(rest, rest)}"


def _asset(value):
    category, separator, rest = value.partition(" - ")
    if not separator:
        return {"Other": "Iné aktívum", "Unknown": "Neznáme aktívum"}.get(value, value)
    return f"{AKTIVUM_KATEGORIE.get(category, category)} · {AKTIVUM_VARIETY.get(rest, rest)}"


def _plain(mapping):
    return lambda value: mapping.get(value, value)


FORMATTERS = {
    "aktor_typy": _plain(AKTOR_TYPY),
    "akcia_typy": _plain(AKCIA_TYPY),
    "aktor_variety": lambda value: _prefixed(value, AKTOR_TYPY, AKTOR_VARIETY),
    "akcia_variety": lambda value: _prefixed(value, AKCIA_TYPY, AKCIA_VARIETY),
    "akcia_vektory": lambda value: _prefixed(value, AKCIA_TYPY, AKCIA_VEKTORY),
    "aktivum_variety": _asset,
    "typy_dat": _plain(TYPY_DAT),
    "motiv": _plain(MOTIV),
    "sposob_odhalenia": _plain(SPOSOB_ODHALENIA),
    "krajina": _plain(KRAJINY),
}


def label(field, value):
    """Slovenský popis hodnoty poľa formulára. Neznáme pole alebo hodnotu vráti s veľkým začiatočným písmenom."""
    text = FORMATTERS[field](value) if field in FORMATTERS else str(value)
    return text[:1].upper() + text[1:]


def formatter(field):
    return lambda value: label(field, value)

