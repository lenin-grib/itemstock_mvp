import streamlit as st
from parser import load_multiple_files

st.title("📦 Загрузка логов продаж")

uploaded_files = st.file_uploader(
    "Загрузи до 12 файлов логов",
    type=["xlsx"],
    accept_multiple_files=True
)

if uploaded_files:
    if len(uploaded_files) > 12:
        st.warning("Можно загрузить максимум 12 файлов")
    else:
        df = load_multiple_files(uploaded_files)

        st.success(f"Загружено строк: {len(df)}")

        st.write("Пример данных:")
        st.dataframe(df.head(10))

        st.write("Агрегация по SKU:")
        summary = (
            df.sort_values(["sku", "date"])
              .groupby("sku", as_index=False)
              .agg({
                  "outbound": "sum",
                  "inbound": "sum",
                  "остаток на складе": "last"
              })
              .set_index("sku")
        )
        st.dataframe(summary)