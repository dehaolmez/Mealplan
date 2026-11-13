"""Katalog malzemesi → Market Fiyatı ürün eşleştirme kuralları.

Her kural: arama sözcüğü (q), izin verilen ana kategoriler (cats), başlıkta bulunması gereken ifadelerden en az
biri (any), bulunmaması gerekenler (exclude). Karşılaştırmalar Türkçe karakterleri sadeleştirilmiş küçük harfle
yapılır. Kurallar 13.11.2026'da Etimesgut verisiyle ayarlandı; kaçan ürün olursa buradan güncellenir.
"""

SPECIAL_PRODUCE = ["kokteyl", "cherry", "seker domates", "kurutulmus", "suyu", "tursu", "sos", "aromali", "cips"]

RULES: dict[str, dict] = {
    "Domates": {"q": "domates", "cats": ["Sebze"], "any": ["domates"], "exclude": SPECIAL_PRODUCE},
    "Salatalık": {"q": "salatalık", "cats": ["Sebze"], "any": ["salatalik"], "exclude": SPECIAL_PRODUCE},
    "Kuru soğan": {"q": "soğan", "cats": ["Sebze"], "any": ["sogan"], "exclude": ["yesil", "taze", "mor", "arpacik"]},
    "Sarımsak": {"q": "sarımsak", "cats": ["Sebze"], "any": ["sarimsak"], "exclude": ["tursu", "toz"]},
    "Patates": {"q": "patates", "cats": ["Sebze"], "any": ["patates"], "exclude": ["tatli", "cips", "kizartmalik"]},
    "Havuç": {"q": "havuç", "cats": ["Sebze"], "any": ["havuc"], "exclude": ["suyu"]},
    "Kabak": {"q": "kabak", "cats": ["Sebze"], "any": ["kabak"], "exclude": ["cekirdek", "bal kabagi"]},
    "Patlıcan": {"q": "patlıcan", "cats": ["Sebze"], "any": ["patlican"], "exclude": ["kozlenmis", "konserve"]},
    "Sivri biber": {"q": "sivri biber", "cats": ["Sebze"], "any": ["sivri"], "exclude": ["tursu"]},
    "Kırmızı biber": {"q": "kırmızı biber", "cats": ["Sebze"], "any": ["kirmizi biber", "kapya"], "exclude": ["toz", "pul"]},
    "Ispanak": {"q": "ıspanak", "cats": ["Sebze", "Hazır Yemekler"], "any": ["ispanak"], "exclude": ["borek", "yemegi", "pizza"]},
    "Marul": {"q": "marul", "cats": ["Sebze"], "any": ["marul"], "exclude": ["mix", "karisik"]},
    "Maydanoz": {"q": "maydanoz", "cats": ["Sebze"], "any": ["maydanoz"], "exclude": []},
    "Limon": {"q": "limon", "cats": ["Meyve", "Sebze"], "any": ["limon"], "exclude": ["suyu", "sos", "aromali", "tuzu"], "size": 100},
    "Elma": {"q": "elma", "cats": ["Meyve"], "any": ["elma"], "exclude": ["suyu", "kuru", "cips", "pure", "sirke"]},
    "Muz": {"q": "muz", "cats": ["Meyve"], "any": ["muz"], "exclude": ["kuru", "cips"]},
    "Mantar": {"q": "mantar", "cats": ["Sebze"], "any": ["mantar"], "exclude": ["konserve", "dilimli kavanoz"]},
    "Brokoli": {"q": "brokoli", "cats": ["Sebze", "Hazır Yemekler"], "any": ["brokoli"], "exclude": ["pizza", "corba"]},
    "Süt": {"q": "süt 1 lt", "cats": ["Süt"], "any": ["sut"],
            "exclude": ["cilek", "kakao", "muz", "cikolata", "aroma", "laktozsuz", "keci", "bebek", "devam", "bisküvi",
                        "kahve", "barista", "protein", "6x", "x180", "x200"], "size": 100},
    "Yoğurt": {"q": "yoğurt", "cats": ["Yoğurt"], "any": ["yogurt"],
               "exclude": ["meyveli", "cilek", "aroma", "kitirli", "icme", "musli", "granola", "bal"], "size": 100},
    "Beyaz peynir": {"q": "beyaz peynir", "cats": ["Peynir"], "any": ["beyaz peynir"], "exclude": ["light", "keci", "koyun"]},
    "Kaşar peyniri": {"q": "kaşar peyniri", "cats": ["Peynir"], "any": ["kasar"], "exclude": ["light", "rende", "dilim"]},
    "Tereyağı": {"q": "tereyağı", "cats": ["Tereyağı ve Margarin"], "any": ["tereyag"], "exclude": ["margarin", "dilimli"]},
    "Yumurta": {"q": "yumurta", "cats": ["Yumurta"], "any": ["yumurta"], "exclude": ["bildircin", "haslanmis"]},
    "Krema": {"q": "krema", "cats": ["Diğer Süt Ürünleri"], "any": ["krema"], "exclude": ["bitkisel", "sprey", "cirpilmis"]},
    "Tavuk göğsü": {"q": "tavuk göğsü", "cats": ["Beyaz Et"], "any": ["gogus", "bonfile", "fileto"],
                    "exclude": ["acili", "soslu", "marine", "pane", "nugget", "doner", "izgara dilim"]},
    "Tavuk but": {"q": "tavuk but", "cats": ["Beyaz Et"], "any": ["but"], "exclude": ["acili", "soslu", "marine", "pane", "kanat"]},
    "Kıyma": {"q": "kıyma", "cats": ["Kırmızı Et"], "any": ["kiyma"], "exclude": ["kofte", "tavuk"]},
    "Kuşbaşı et": {"q": "kuşbaşı", "cats": ["Kırmızı Et"], "any": ["kusbasi"], "exclude": ["pide", "kavurma"]},
    "Somon": {"q": "somon", "cats": ["Taze Deniz Ürünleri", "Deniz Ürünleri"], "any": ["somon"],
              "exclude": ["fume", "zeytinyagli", "konserve", "poset", "salata"]},
    "Sucuk": {"q": "dana sucuk", "cats": ["Şarküteri"], "any": ["sucuk"], "exclude": ["dilimli", "cips", "pizza", "pilic", "hindi", "tavuk"]},
    "Ekmek": {"q": "ekmek", "cats": ["Ekmek ve Unlu Mamüller"], "any": ["ekmek"],
              "exclude": ["eksi", "tam bugday", "lavas", "pide", "tost", "hamburger", "galeta", "kepek", "cavdar", "kg"]},
    "Lavaş": {"q": "lavaş", "cats": ["Ekmek ve Unlu Mamüller"], "any": ["lavas"], "exclude": ["tam bugday", "taco", "tortilla"]},
    "Pirinç": {"q": "pirinç", "cats": ["Bakliyat"], "any": ["pirinc"], "exclude": ["basmati", "jasmine", "esmer", "sushi", "risotto", "kirik"]},
    "Bulgur": {"q": "pilavlık bulgur", "cats": ["Bakliyat"], "any": ["pilavlik"], "exclude": ["glutensiz"]},
    "Makarna": {"q": "makarna", "cats": ["Mantı Makarna ve Erişte"], "any": ["makarna"], "exclude": ["glutensiz", "tam bugday", "baklagil"]},
    "Kırmızı mercimek": {"q": "kırmızı mercimek", "cats": ["Bakliyat"], "any": ["kirmizi mercimek"], "exclude": ["organik"]},
    "Nohut": {"q": "nohut", "cats": ["Bakliyat"], "any": ["nohut"], "exclude": ["organik", "haslanmis", "leblebi"]},
    "Un": {"q": "un", "cats": ["Un ve İrmik"], "any": ["un"], "exclude": ["unlu", "glutensiz", "misir", "pirinc", "irmik", "tam bugday", "nisasta"]},
    "Yulaf": {"q": "yulaf ezmesi", "cats": ["Kahvaltılık Gevrek Bar ve Granola"], "any": ["yulaf ezmesi"], "exclude": ["glutensiz", "kakaolu", "meyveli"]},
    "Zeytinyağı": {"q": "zeytinyağı", "cats": ["Sıvı Yağlar"], "any": ["zeytinyag"], "exclude": ["sprey"]},
    "Ayçiçek yağı": {"q": "ayçiçek yağı", "cats": ["Sıvı Yağlar"], "any": ["aycicek"], "exclude": ["sprey"]},
    "Domates salçası": {"q": "domates salçası", "cats": ["Salça"], "any": ["domates salca"], "exclude": []},
    "Konserve domates": {"q": "doğranmış domates", "cats": ["Salça", "Konserve"], "any": ["domates"], "exclude": ["salca", "pure"]},
    "Zeytin": {"q": "zeytin", "cats": ["Zeytin"], "any": ["zeytin"], "exclude": ["ezmesi", "dolgulu", "yagi"]},
    "Bal": {"q": "çiçek balı", "cats": ["Bal ve Reçel"], "any": ["bal"], "exclude": ["tup", "petek", "pekmez"]},
    "Dondurulmuş bezelye": {"q": "dondurulmuş bezelye", "cats": ["Hazır Yemekler"], "any": ["bezelye"], "exclude": []},
    "Dondurulmuş karışık sebze": {"q": "dondurulmuş sebze", "cats": ["Hazır Yemekler"], "any": ["sebze", "garnitur"], "exclude": ["corba", "pizza"]},
}

# Market Fiyatı'ndaki market adı → katalog zincir slug'ı
MARKET_TO_CHAIN = {
    "bim": "bim",
    "a101": "a101",
    "sok": "sok",
    "migros": "migros",
    "carrefour": "carrefoursa",
    "hakmar": "hakmar",
    "tarim_kredi": "tarim-kredi",
}


# Otomatik çıkarılamayan veya yanlış eşleşen genişletilmiş katalog malzemeleri (elle)
MANUAL_EXTRA: dict[str, dict] = {
    "Barbunya (kuru)": {"q": "barbunya", "cats": ["Bakliyat"], "any": ["barbunya"], "exclude": ["konserve", "pilaki"]},
    "Bakla (kuru)": {"q": "kuru bakla", "cats": ["Bakliyat"], "any": ["bakla"], "exclude": []},
    "Köz patlıcan (konserve)": {"q": "közlenmiş patlıcan", "cats": ["Konserve"], "any": ["kozlenmis patlican", "koz patlican"], "exclude": []},
    "Haşlanmış mısır (konserve)": {"q": "mısır konservesi", "cats": ["Konserve"], "any": ["misir"], "exclude": ["patlamis", "cips", "gevrek"]},
    "Kus-kus": {"q": "kuskus", "cats": ["Mantı Makarna ve Erişte", "Bakliyat"], "any": ["kuskus", "kus kus"], "exclude": []},
    "Tavuk kanat": {"q": "piliç kanat", "cats": ["Beyaz Et"], "any": ["kanat"], "exclude": ["soslu", "acili", "marine", "pane"]},
    "Bütün tavuk": {"q": "bütün piliç", "cats": ["Beyaz Et"], "any": ["butun"], "exclude": ["gogus", "soslu"]},
    "Kuzu kuşbaşı": {"q": "kuzu kuşbaşı", "cats": ["Kırmızı Et"], "any": ["kuzu"], "exclude": ["kofte", "kavurma", "kiyma", "pirzola"]},
    "Kuzu pirzola": {"q": "kuzu pirzola", "cats": ["Kırmızı Et"], "any": ["pirzola"], "exclude": []},
    "Kakao": {"q": "kakao", "cats": ["Pasta Malzemeleri"], "any": ["kakao"], "exclude": ["dondurma", "icecek", "sut"]},
    "Çam fıstığı": {"q": "çam fıstığı", "cats": ["Kuruyemiş ve Kuru Meyve", "Pasta Malzemeleri"], "any": ["cam fistig"], "exclude": []},
    "Zencefil (taze)": {"q": "zencefil", "cats": ["Sebze"], "any": ["zencefil"], "exclude": ["toz", "cay"]},
    "Yer Elması": {"q": "yer elması", "cats": ["Sebze"], "any": ["yer elmasi"], "exclude": []},
    "Dövme buğday": {"q": "dövme", "cats": ["Bakliyat"], "any": ["dovme"], "exclude": []},
    "Çedar": {"q": "cheddar", "cats": ["Peynir"], "any": ["cheddar", "cedar"], "exclude": []},
    "Keçi Peyniri": {"q": "keçi peyniri", "cats": ["Peynir"], "any": ["keci"], "exclude": []},
    "Köy peyniri": {"q": "köy peyniri", "cats": ["Peynir"], "any": ["koy peyniri"], "exclude": []},
    "Manda yoğurdu": {"q": "manda yoğurdu", "cats": ["Yoğurt"], "any": ["manda"], "exclude": []},
    "Koyun Yoğurdu": {"q": "koyun yoğurdu", "cats": ["Yoğurt"], "any": ["koyun"], "exclude": []},
    "Hindistan cevizi rendesi": {"q": "hindistan cevizi", "cats": ["Pasta Malzemeleri", "Kuruyemiş ve Kuru Meyve"], "any": ["hindistan cevizi"], "exclude": ["sut", "yag"]},
}


def _load_extra() -> None:
    """Genişletilmiş katalog için veriden çıkarılmış kurallar (scripts/generate_mf_rules.py)."""
    import json
    from pathlib import Path

    path = Path(__file__).with_name("marketfiyati_rules_extra.json")
    if path.exists():
        for name, rule in json.loads(path.read_text(encoding="utf-8")).items():
            if rule and name not in RULES:
                RULES[name] = rule
    RULES.update(MANUAL_EXTRA)


_load_extra()
