# Асинхронный парсер товаров с nsk.pulscen.ru

Скрипт парсит **все товары** с сайта Pulscen (Новосибирск) и сохраняет их в локальную MongoDB и JSON‑файл.

## Требования

- Python 3.10+
- Локально запущенный MongoDB (по умолчанию на `mongodb://localhost:27017`)

## Установка

```bash
pip install -r requirements.txt
```

## Использование

Скрипт `parse_product.py` запускается с URL страницы товара.
Пример:

```bash
python parse_product.py https://nsk.pulscen.ru/products/vstraivayemy_kompyuter_na_din_reyku_np_6111_l2_j6412_4g_ssd512g_271899908
```

Результат выводится в формате JSON.
