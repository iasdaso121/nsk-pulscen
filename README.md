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

python parse_product.py https://nsk.pulscen.ru/products/vstraivayemy_kompyuter_na_din_reyku_np_6111_l2_j6412_4g_ssd512g_271899908 -v

```

Результат выводится в формате JSON.

### Сбор подкатегорий

Для получения списка подкатегорий со страницы родительской категории используйте скрипт `parse_categories.py`:

```bash
python parse_categories.py https://nsk.pulscen.ru/price/computer -v
```

Скрипт вернёт JSON-массив с названиями и ссылками на найденные подкатегории.

### Сбор ссылок на товары

Для получения всех ссылок на товары из выбранной подкатегории используйте
скрипт `parse_product_links.py`:

```bash
python parse_product_links.py https://nsk.pulscen.ru/price/1901-nastolnye-kompjutery -v
```

Скрипт обходит все страницы подкатегории, учитывая пагинацию, и выводит
JSON-массив с названием и URL каждого найденного товара.

### Полный сбор товаров

Чтобы собрать все товары из родительской категории, сохранить их в MongoDB и JSONL‑файл, запустите `parse_all_products.py`:

```bash
python parse_all_products.py https://nsk.pulscen.ru/price/computer -v -o products.jsonl
```

По умолчанию данные сохраняются в базу `pulscen` на `mongodb://localhost:27017` и в файл `products.jsonl`.

