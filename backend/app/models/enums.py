from enum import StrEnum


class Sex(StrEnum):
    male = "male"
    female = "female"


class ActivityLevel(StrEnum):
    sedentary = "sedentary"      # masa başı, egzersiz yok
    light = "light"              # haftada 1-3 gün hafif egzersiz
    moderate = "moderate"        # haftada 3-5 gün orta egzersiz
    active = "active"            # haftada 6-7 gün yoğun egzersiz
    very_active = "very_active"  # fiziksel iş + günlük antrenman


class Goal(StrEnum):
    lose = "lose"
    maintain = "maintain"
    gain = "gain"


class StorageLocation(StrEnum):
    fridge = "fridge"    # Buzdolabı
    freezer = "freezer"  # Buzluk / dondurucu


class BaseUnit(StrEnum):
    """Her malzeme tek bir temel birimde tutulur; miktar karşılaştırmaları bu birimde yapılır."""

    g = "g"
    ml = "ml"
    piece = "adet"


class Category(StrEnum):
    """Bring! tarzı alışveriş listesi reyonları."""

    produce = "Manav"
    dairy = "Süt Ürünleri"
    meat = "Et & Balık"
    bakery = "Fırın"
    staples = "Temel Gıda"
    frozen = "Dondurulmuş"
    spices = "Baharat & Sos"
    beverages = "İçecek"
    other = "Diğer"


class MealType(StrEnum):
    breakfast = "breakfast"
    lunch = "lunch"
    dinner = "dinner"
    snack = "snack"


class ChainKind(StrEnum):
    discount = "discount"          # indirim marketi (BİM, A101, ŞOK…)
    supermarket = "supermarket"    # süpermarket (Migros, CarrefourSA…)
    hypermarket = "hypermarket"    # hipermarket formatı (5M Migros, CarrefourSA Hiper…)
    premium = "premium"            # gurme/premium (Macrocenter)
    wholesale = "wholesale"        # toptan / cash & carry (Metro, Bizim Toptan)
    cooperative = "cooperative"    # kooperatif (Tarım Kredi)
    regional = "regional"          # bölgesel zincir
