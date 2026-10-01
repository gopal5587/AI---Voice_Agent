import re

STOPWORDS = set("""
a an the is are was were be been being am do does did doing have has had having i me my we our you your he she it its they them
their what which who whom this that these those of at by for with about against between into through during before after above
below to from up down in out on off over under again further then once here there when where why how all any both each few more
most other some such no nor not only own same so than too very can will just should now would could tell know want please if or
and but also get got much many okay ok hi hello yes yeah sir madam maam as well really like even still ever
ang ng sa na ba po ko mo ako ikaw siya kami tayo kayo sila ito iyan yan yung mga lang din rin naman kasi pero at o kung para may
wala oo hindi opo ano paano bakit kailan saan sino
yang dan di ke dari ini itu saya aku kamu anda bapak ibu kak apa bagaimana gimana kenapa kapan dimana siapa ada tidak nggak gak
ga enggak sudah udah belum bisa mau akan dengan untuk pada juga atau tapi kalau kok sih dong ya iya nih tuh deh berapa hari
s t d ll re ve m
""".split())

TOKEN = re.compile(r"[a-z0-9]+(?:[.,][0-9]+)?", re.I)


def tokenize(text: str) -> list[str]:
    return [t for t in (m.group(0).lower() for m in TOKEN.finditer(text)) if t not in STOPWORDS]


def stem(token: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if len(token) > len(suffix) + 3 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def terms(text: str) -> list[str]:
    return [stem(t) for t in tokenize(text)]
