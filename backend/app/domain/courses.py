"""Tarif türü (sofradaki yeri): çorba, ana yemek, yan yemek (pilav/makarna/börek yanında), salata/meze, kahvaltı,
ara öğün. Planlayıcı öğle/akşam öğününü bu türlerden menü olarak kurar."""

import re

COURSES = ("breakfast", "soup", "main", "side", "salad", "snack")
COURSE_LABELS = {"breakfast": "Kahvaltı", "soup": "Çorba", "main": "Ana yemek", "side": "Yan yemek",
                 "salad": "Salata / meze", "snack": "Ara öğün"}

_SALAD = re.compile(r"salata|cacık|haydari|humus|ezme|piyaz|kısır|babagannuş|muhammara|şakşuka|meze|tarator", re.I)
_SIDE = re.compile(r"pilav|pilavı|bulgur|kuskus|erişte|patates kızartması|patates püresi", re.I)
# Pilav adı geçse de etli/tavuklu olanlar tek başına ana yemektir
_MAIN_HINT = re.compile(r"tavuk|etli|kıymalı|köfte|kebap|kebabı|balık|levrek|hamsi|somon|karides|perde", re.I)


# Adından çıkarılamayanlar için elle belirlenen türler
OVERRIDES = {
    "tereyağlı makarna": "side", "fırında baharatlı patates": "side", "tereyağlı pirinç pilavı": "side",
    "şehriyeli pirinç pilavı": "side", "domatesli bulgur pilavı": "side", "bulgur pilavı": "side",
    "baharatlı iç pilav": "side", "sebzeli erişte": "side", "peynirli makarna": "main",
}


def classify(name: str, meal_type: str, group: str | None = None) -> str:
    if name.lower() in OVERRIDES:
        return OVERRIDES[name.lower()]
    if meal_type == "breakfast":
        return "breakfast"
    if re.search(r"çorba", name, re.I) or (group or "").startswith("Çorba"):
        return "soup"
    if _SALAD.search(name) or (group or "").startswith("Salata"):
        return "salad" if meal_type != "snack" or _SALAD.search(name) else "snack"
    if _SIDE.search(name) and not _MAIN_HINT.search(name):
        return "side"
    if meal_type == "snack":
        return "snack"
    return "main"
