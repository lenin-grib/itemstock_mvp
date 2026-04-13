from rapidfuzz import process, fuzz
import pandas as pd
from utils import normalize, extract_brand, transliterate_cyrillic_to_latin

def brands_match(brand_a, brand_b):
    if not brand_a or not brand_b:
        return False

    if brand_a == brand_b:
        return True

    translit_a = transliterate_cyrillic_to_latin(brand_a)
    translit_b = transliterate_cyrillic_to_latin(brand_b)

    if translit_a == translit_b:
        return True

    return fuzz.ratio(translit_a, translit_b) >= 90

def load_excel_catalog(file):
    df = pd.read_excel(file)

    # Берём нужные колонки
    df = df.iloc[:, [2, 3, 4]]  # C, D, E

    df.columns = ["name", "pack", "price"]

    # убираем пустые строки
    df = df.dropna(subset=["name", "price"])

    # нормализация
    df["name_norm"] = df["name"].apply(normalize)
    df["brand_norm"] = df["name_norm"].apply(extract_brand)

    return df

def match_prices(log_df, catalog_df, price_col_name):

    def find_match(sku):
        sku_norm = normalize(sku)
        sku_brand = extract_brand(sku_norm)

        if not sku_brand:
            return pd.Series({
                price_col_name: None,
                f"{price_col_name}_match": None,
                f"{price_col_name}_score": None
            })

        brand_candidates = catalog_df[catalog_df["brand_norm"].apply(lambda b: brands_match(sku_brand, b))]
        if brand_candidates.empty:
            return pd.Series({
                price_col_name: None,
                f"{price_col_name}_match": None,
                f"{price_col_name}_score": None
            })

        candidate_names = brand_candidates["name_norm"].tolist()
        match = process.extractOne(
            sku_norm,
            candidate_names,
            scorer=fuzz.token_set_ratio  # лучше для длинных строк
        )

        if match and match[1] > 65:  # чуть снижаем порог
            matched_name = match[0]

            row = brand_candidates[brand_candidates["name_norm"] == matched_name].iloc[0]

            return pd.Series({
                price_col_name: row["price"],
                "pack": row["pack"],
                f"{price_col_name}_match": row["name"],
                f"{price_col_name}_score": match[1]
            })

        return pd.Series({
            price_col_name: None,
            "pack": None,
            f"{price_col_name}_match": None,
            f"{price_col_name}_score": None
        })

    matches = log_df["sku"].apply(find_match)

    return pd.concat([log_df, matches], axis=1)

def enrich_with_prices(log_df, excel_file):
    catalog = load_excel_catalog(excel_file)

    log_df = match_prices(log_df, catalog, "price_excel")

    return log_df

