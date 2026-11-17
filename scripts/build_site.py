#!/usr/bin/env python3
"""Rebuild catalog facts from the factory cards and write the static site."""

import html
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://profdst.ru"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

BLURBS = {
    "mini-pogruzchiki": "{short} — компактный погрузчик с бортовым поворотом для дворов, складов и благоустройства, где полноразмерная машина не проходит.",
    "ekskavatory-pogruzchiki": "{short} совмещает ковш экскаватора и фронтальный погрузчик: одна машина закрывает копку и погрузку на дорожных и коммунальных работах.",
    "gusenichnye-ekskavatory": "{short} для котлованов, траншей и карьера, где нужна устойчивость на мягком и неровном грунте.",
    "frontalnye-pogruzchiki": "{short} для инертных материалов, снега и планировки площадок.",
    "kolyesnye-ekskavatory": "{short} переезжает между объектами своим ходом — удобный формат для городских работ по Республике Татарстан.",
    "gusenichnye-mini-ekskavatory": "{short} для узких проездов, ремонта сетей и небольших площадок.",
}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": BASE + "/"})
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.read().decode("utf-8", "replace")


def clean(value: str) -> str:
    value = re.sub(r"<br\s*/?>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def esc(value: str) -> str:
    return (
        (value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def tech_block(page: str) -> str:
    match = re.search(r'id="tabnav-tech"(.*)$', page, re.S)
    block = match.group(1) if match else page
    cut = block.find("premium-equipment")
    return block[:cut] if cut > 0 else block


def parse_groups(block: str):
    grouped = []
    parts = re.split(r'<h2 class="sec-title">', block)
    if len(parts) > 1:
        for part in parts[1:]:
            title = clean(part.split("</h2>", 1)[0])
            rows = rows_from(part, "spec-name", "spec-val")
            if title and rows:
                grouped.append({"title": title, "rows": rows})
    accordion = []
    parts = re.split(r'class="sp-label-text">', block)
    if len(parts) > 1:
        for part in parts[1:]:
            title = clean(part.split("</span>", 1)[0])
            rows = rows_from(part, "sp-row-label", "sp-row-value")
            if title and rows:
                accordion.append({"title": title, "rows": rows})
    flat = rows_from(block, "spec-name", "spec-val")
    candidates = [grouped, accordion]
    if flat:
        candidates.append([{"title": "Характеристики", "rows": flat}])
    best = max(candidates, key=lambda groups: sum(len(group["rows"]) for group in groups), default=[])
    return best


def rows_from(block: str, name_class: str, value_class: str):
    rows = []
    seen = set()
    pattern = (
        rf'class="{name_class}">\s*(.*?)\s*</(?:div|span)>\s*'
        rf'<[^>]*class="{value_class}[^"]*"[^>]*>\s*(.*?)\s*</(?:div|span)>'
    )
    for name, value in re.findall(pattern, block, re.S):
        name, value = clean(name), clean(value)
        key = (name.lower(), value.lower())
        if not name or not value or key in seen:
            continue
        seen.add(key)
        rows.append({"name": name, "value": value})
    return rows


def parse_kpis(block: str):
    kpis = []
    pattern = (
        r'class="kpi-num">\s*(.*?)\s*<span class="kpi-unit">\s*(.*?)\s*</span>\s*</div>\s*'
        r'<div class="kpi-label">\s*(.*?)\s*</div>'
    )
    for value, unit, label in re.findall(pattern, block, re.S):
        kpis.append({"value": clean(value), "unit": clean(unit), "label": clean(label)})
    return kpis


def short_name(name: str) -> str:
    if "Профессионал" in name:
        return name.split("Профессионал", 1)[1].strip()
    return name


def highlights(product, limit=3):
    preferred = ("мощност", "грузопод", "масса", "объём ковша", "объем ковша", "ковша", "глубина", "высота выгрузки")
    pool = [(item["label"], f'{item["value"]} {item["unit"]}'.strip()) for item in product["kpis"]]
    for group in product["groups"]:
        for row in group["rows"]:
            if any(token in row["name"].lower() for token in preferred):
                pool.append((row["name"], row["value"]))
    picked = []
    seen = set()
    for label, value in pool:
        if label.lower() in seen:
            continue
        seen.add(label.lower())
        picked.append({"label": label, "value": value})
        if len(picked) == limit:
            return picked
    for group in product["groups"]:
        for row in group["rows"]:
            if row["name"].lower() in seen:
                continue
            picked.append({"label": row["name"], "value": row["value"]})
            if len(picked) == limit:
                return picked
    return picked


def head(title, description, depth):
    prefix = "../" * depth
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <link rel="icon" href="{prefix}assets/logo.jpg">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Unbounded:wght@500;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="{prefix}assets/site.css">
</head>
<body>
<a class="skip" href="#main">К содержанию</a>
<header class="site-header">
  <div class="wrap topbar">
    <a class="brand" href="{prefix}index.html">
      <img src="{prefix}assets/logo.jpg" alt="Альфа Машинери">
      <span class="brand-text"><b>Альфа Машинери</b><small>Официальный дилер по Республике Татарстан</small></span>
    </a>
    <nav class="nav" id="nav">
      <a href="{prefix}index.html">Главная</a>
      <a href="{prefix}catalog/index.html">Каталог</a>
      <a href="{prefix}index.html#lizing">Лизинг</a>
      <a href="{prefix}index.html#servis">Сервис</a>
      <a href="{prefix}index.html#kontakty">Контакты</a>
    </nav>
    <div class="top-actions">
      <a class="wa" href="https://wa.me/79177562606" aria-label="WhatsApp">WA</a>
      <a class="phone" href="tel:+79177562606">+7 917 756-26-06</a>
      <a class="btn btn-primary" href="{prefix}index.html#zayavka">Получить предложение</a>
    </div>
    <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="nav">Меню</button>
  </div>
</header>
<main id="main">
"""


def footer(depth):
    prefix = "../" * depth
    return f"""</main>
<footer class="site-footer">
  <div class="wrap footer-grid">
    <div>
      <h2>Альфа Машинери</h2>
      <p>Официальный дилер завода «Профессионал» по Республике Татарстан. Дорожно-строительная техника, лизинг и запуск на объекте.</p>
    </div>
    <div>
      <h2>Разделы</h2>
      <ul>
        <li><a href="{prefix}catalog/index.html">Каталог</a></li>
        <li><a href="{prefix}index.html#lizing">Лизинг</a></li>
        <li><a href="{prefix}index.html#servis">Сервис</a></li>
        <li><a href="{prefix}index.html#kontakty">Контакты</a></li>
        <li><a href="{prefix}privacy/index.html">Конфиденциальность</a></li>
        <li><a href="{prefix}consent/index.html">Согласие на данные</a></li>
        <li><button type="button" data-cookie-open>Настройки куки</button></li>
      </ul>
    </div>
    <div>
      <h2>Казань</h2>
      <p>Советский район, жилой массив Самосырово<br>
      <a href="tel:+79177562606">+7 917 756-26-06</a><br>
      <a href="mailto:alfa-mash@bk.ru">alfa-mash@bk.ru</a><br>
      Пн–пт, 9:00–18:00</p>
    </div>
  </div>
</footer>
<div class="cookie-bar" data-cookie hidden>
  <div class="cookie-copy">
    <b>Куки и счётчики</b>
    <p>Сайт можно смотреть без аналитики и рекламы. Кнопка «Разрешить» включает счётчики визитов и рекламы. «Отказаться» оставляет сайт без них. Текст заявки в счётчики не уходит. <a href="{prefix}privacy/index.html">Политика конфиденциальности</a></p>
  </div>
  <div class="cookie-actions">
    <button type="button" class="btn btn-ghost" data-cookie-reject>Отказаться</button>
    <button type="button" class="btn btn-primary" data-cookie-save>Разрешить</button>
  </div>
</div>
<script src="{prefix}assets/site.js"></script>
</body>
</html>
"""


def options(products, selected):
    chunks = ['<option value="Нужна помощь с выбором">Нужна помощь с выбором</option>']
    for product in products:
        label = product["short"]
        current = " selected" if product["short"] == selected else ""
        chunks.append(f'<option value="{esc(label)}"{current}>{esc(label)}</option>')
    return "\n".join(chunks)


def lead_form(products, selected, depth):
    prefix = "../" * depth
    return f"""
<form class="form" data-lead>
  <label>Имя
    <input name="name" autocomplete="name" required>
  </label>
  <label>Телефон
    <input name="phone" autocomplete="tel" inputmode="tel" placeholder="+7 900 000-00-00" required>
  </label>
  <label>Техника
    <select name="model">{options(products, selected)}</select>
  </label>
  <label>Город или объект
    <input name="place" placeholder="Казань, Набережные Челны…">
  </label>
  <label>Комментарий
    <textarea name="comment" placeholder="Грунт, объём работ, срок"></textarea>
  </label>
  <p class="form-error" hidden></p>
  <button class="btn btn-primary" type="submit">Получить предложение</button>
  <p class="form-note">Нажимая кнопку, вы даёте <a href="{prefix}consent/index.html">согласие</a> на обработку имени, телефона и текста заявки, чтобы мы перезвонили. Его можно отозвать письмом на alfa-mash@bk.ru.</p>
</form>
<div class="success" hidden>
  <p>Заявка собрана. Отправьте её менеджеру или позвоните — так она точно дойдёт.</p>
  <textarea readonly></textarea>
  <div class="actions">
    <a class="btn btn-primary" data-mail href="mailto:alfa-mash@bk.ru">Открыть письмо</a>
    <a class="btn btn-ghost" data-wa href="https://wa.me/79177562606">WhatsApp</a>
    <a class="btn btn-ghost" href="tel:+79177562606">Позвонить</a>
  </div>
</div>
"""


def machine_card(product, depth):
    prefix = "../" * depth
    facts = "".join(
        f"<div><dt>{esc(item['label'])}</dt><dd>{esc(item['value'])}</dd></div>"
        for item in product["highlights"]
    )
    image = product["image"]
    photo = (
        f'<img src="{prefix}{esc(image)}" alt="{esc(product["name"])}">'
        if image
        else ""
    )
    href = f"{prefix}catalog/{esc(product['slug'])}/index.html"
    return f"""
<article class="machine" data-category="{esc(product["category"])}">
  <a class="machine-photo" href="{href}">{photo}</a>
  <div class="machine-body">
    <div class="badges"><span>Сделано в РФ</span></div>
    <h3><a href="{href}">{esc(product["short"])}</a></h3>
    <dl class="specs-mini">{facts}</dl>
    <div class="card-actions">
      <a class="btn btn-ghost" href="{href}">Подробнее</a>
      <a class="btn btn-primary" href="{href}#zayavka">Предложение</a>
    </div>
  </div>
</article>
"""


def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main():
    import sys

    catalog = json.loads((ROOT / "data" / "catalog.json").read_text(encoding="utf-8"))
    offline = "--offline" in sys.argv
    products = []
    for product in catalog["products"]:
        if not offline:
            page = fetch(product["source"])
            block = tech_block(page)
            product["kpis"] = parse_kpis(block)
            product["groups"] = parse_groups(block)
        product["short"] = short_name(product["name"])
        product["highlights"] = highlights(product)
        product["blurb"] = BLURBS[product["category"]].format(short=product["short"])
        products.append(product)
        print(f'{product["short"]}: {len(product["kpis"])} kpi, {sum(len(g["rows"]) for g in product["groups"])} specs')

    catalog["products"] = products
    (ROOT / "data" / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    description = "Дорожно-строительная техника завода «Профессионал» в Республике Татарстан: мини-погрузчики, экскаваторы и фронтальные погрузчики. Поставка, лизинг и запуск от Альфа Машинери, Казань."
    counts = []
    for category in catalog["categories"]:
        count = sum(1 for product in products if product["category"] == category["slug"])
        counts.append({**category, "count": count})

    home_cards = [
        "mini-pogruzchik-professional-pm-1250",
        "ekskavator-pogruzchik-professional-pb-991-raznovelikie-kolyesa-",
        "gusenichnyy-ekskavator-professional-pb225",
        "frontalnyy-pogruzchik-professional-pb50-g-p-5-t-gabaritnyy",
        "kolyesnyy-ekskavator-professional-pb155w",
        "gusenichnyy-mini-ekskavator-professional-pb060-yanmar",
    ]
    by_slug = {product["slug"]: product for product in products}
    picks = [by_slug[slug] for slug in home_cards]
    hero = by_slug["frontalnyy-pogruzchik-professional-pb50-g-p-5-t-gabaritnyy"]

    cats_html = "\n".join(
        f'<a class="cat-card" href="catalog/index.html#{esc(item["slug"])}"><strong>{esc(item["title"])}</strong><span>{item["count"]} {"модель" if item["count"] == 1 else "модели" if 2 <= item["count"] <= 4 else "моделей"}</span></a>'
        for item in counts
    )
    model_blocks = []
    for category in counts:
        group = [product for product in products if product["category"] == category["slug"]]
        model_blocks.append(
            f'<div class="model-block"><h3>{esc(category["title"])}</h3><div class="rail">'
            + "".join(machine_card(product, 0) for product in group)
            + "</div></div>"
        )
    cities = ["Казань", "Набережные Челны", "Нижнекамск", "Альметьевск", "Елабуга", "Зеленодольск", "Бугульма", "Чистополь"]
    city_html = "".join(f"<li>{esc(city)}</li>" for city in cities)
    home = head("Альфа Машинери — официальный дилер «Профессионал» по Республике Татарстан", description, 0)
    home += f"""
<section class="hero" data-hero>
  <div class="hero-slide is-on" style="background-image:url('{esc(hero["image"])}')"></div>
  <div class="hero-slide" style="background-image:url('assets/machines/ekskavator-pogruzchik-professional-pb-991-raznovelikie-kolyesa-.jpg')"></div>
  <div class="wrap hero-layout">
    <div class="hero-panel">
      <p class="eyebrow">Официальный дилер · Республика Татарстан</p>
      <h1 data-hero-title>PB50</h1>
      <p class="hero-sub" data-hero-sub>Фронтальный погрузчик, 5 тонн</p>
      <dl class="hero-stats">
        <div><dt data-stat-label>Мощность</dt><dd data-stat-value>220 л.с.</dd></div>
        <div><dt data-stat-label>Грузоподъёмность</dt><dd data-stat-value>5 000 кг</dd></div>
        <div><dt data-stat-label>Скорость</dt><dd data-stat-value>36 км/ч</dd></div>
      </dl>
      <div class="hero-actions">
        <a class="btn btn-primary" href="#zayavka">Получить предложение</a>
        <div class="hero-nav">
          <button type="button" data-hero-prev aria-label="Предыдущий слайд">‹</button>
          <span data-hero-count>01</span>
          <button type="button" data-hero-next aria-label="Следующий слайд">›</button>
        </div>
      </div>
    </div>
  </div>
</section>
<div class="wrap cat-row">
  {cats_html}
</div>
<section class="section" id="modeli">
  <div class="wrap">
    <h2>19 моделей</h2>
    <p class="section-lead">Мини-погрузчики, экскаваторы и фронтальные погрузчики завода «Профессионал». Цена — по запросу, поставка по Республике Татарстан.</p>
    {"".join(model_blocks)}
  </div>
</section>
<section class="section" id="diler">
  <div class="wrap band">
    <article class="panel">
      <p class="eyebrow">Альфа Машинери</p>
      <h2>Официальный дилер по Республике Татарстан</h2>
      <p>Поставляем дорожно-строительную технику завода «Профессионал»: подбираем модель, готовим коммерческое предложение и сопровождаем запуск.</p>
      <ul class="checklist">
        <li>Подбор техники под грунт, объём работ и бюджет</li>
        <li>Продажа и лизинг</li>
        <li>Сервис, ТО и запасные части после поставки</li>
      </ul>
    </article>
    <article class="panel">
      <h2>Куда привозим</h2>
      <p>Работаем по всей Республике Татарстан. Офис продаж — в Казани.</p>
      <ul class="cities">{city_html}</ul>
    </article>
  </div>
</section>
<section class="section" id="lizing">
  <div class="wrap band">
    <article class="panel">
      <h2>Лизинг</h2>
      <p>Готовим заявку в лизинговую компанию. Модели завода можно рассматривать для закупки по 44-ФЗ и 223-ФЗ: перед договором сверим, что комплектация есть в реестре Минпромторга.</p>
      <ul class="checklist">
        <li>Срок и аванс подбираем вместе с лизинговой компанией</li>
        <li>Платёж в блоке справа — пример при удорожании 10% в год</li>
        <li>Точную сумму называет менеджер после выбора машины</li>
      </ul>
    </article>
    <form class="panel lease" data-lease>
      <h2>Пример платежа</h2>
      <label>Стоимость техники, ₽
        <input name="price" type="number" min="500000" step="100000" value="6000000">
      </label>
      <label>Аванс <span data-advance>20%</span>
        <input name="advance" type="range" min="5" max="49" value="20">
      </label>
      <label>Срок <span data-term>36 мес.</span>
        <input name="term" type="range" min="12" max="84" step="6" value="36">
      </label>
      <div class="lease-out">
        <span>Ориентировочный платёж</span>
        <b data-payment>—</b>
      </div>
      <p>Расчёт информационный и не является публичной офертой.</p>
      <a class="btn btn-primary" href="#zayavka">Получить точный расчёт</a>
    </form>
  </div>
</section>
<section class="section" id="servis">
  <div class="wrap">
    <h2>Сервис и запчасти</h2>
    <p class="section-lead">После поставки техника остаётся на сопровождении Альфа Машинери.</p>
    <div class="point-grid">
      <article class="point"><b>Выезд на объект</b><p>Диагностика и работы на площадке заказчика по Республике Татарстан.</p></article>
      <article class="point"><b>Регламентное ТО</b><p>Обслуживание по наработке и рекомендациям завода.</p></article>
      <article class="point"><b>Запасные части</b><p>Подбор по модели и узлу, чтобы машина меньше стояла.</p></article>
    </div>
  </div>
</section>
<section class="section" id="kontakty">
  <div class="wrap band">
    <article class="panel">
      <p class="eyebrow">Офис продаж</p>
      <h2>Казань</h2>
      <p>Республика Татарстан, Советский район, жилой массив Самосырово.</p>
      <p class="contact-line">Телефон <a href="tel:+79177562606">+7 917 756-26-06</a><br>Почта <a href="mailto:alfa-mash@bk.ru">alfa-mash@bk.ru</a><br>Пн–пт, 9:00–18:00</p>
    </article>
    <div class="panel" id="zayavka">
      <h2>Нужна техника или консультация?</h2>
      <p>Оставьте телефон. Перезвоним и подготовим предложение по Республике Татарстан.</p>
      {lead_form(products, "", 0)}
    </div>
  </div>
</section>
"""
    home += footer(0)
    write(ROOT / "index.html", home)

    filters = ['<button type="button" data-filter="all" class="is-on">Все 19</button>']
    for item in counts:
        filters.append(
            f'<button type="button" data-filter="{esc(item["slug"])}">{esc(item["title"])}</button>'
        )
    catalog_page = head("Каталог техники «Профессионал» — Альфа Машинери", description, 1)
    catalog_page += f"""
<section class="section">
  <div class="wrap">
    <p class="eyebrow">Каталог</p>
    <h1>19 моделей по Республике Татарстан</h1>
    <p class="section-lead">Характеристики взяты с карточек завода «Профессионал». Комплектацию перед договором подтверждаем отдельно.</p>
    <div class="filters" data-filters>{"".join(filters)}</div>
    <div class="card-grid">{"".join(machine_card(product, 1) for product in products)}</div>
  </div>
</section>
"""
    catalog_page += footer(1)
    write(ROOT / "catalog" / "index.html", catalog_page)

    for product in products:
        groups = "".join(
            "<section class=\"spec-group\"><h2>"
            + esc(group["title"])
            + "</h2>"
            + "".join(
                f'<div class="spec-row"><span>{esc(row["name"])}</span><b>{esc(row["value"])}</b></div>'
                for row in group["rows"]
            )
            + "</section>"
            for group in product["groups"]
        )
        spec_count = sum(len(group["rows"]) for group in product["groups"])
        if not groups:
            groups = "<p class=\"photo-note\">Полный лист характеристик пришлём вместе с ценой.</p>"
        elif spec_count < 8:
            groups += "<p class=\"photo-note\">На карточке завода опубликован короткий список. Полный лист пришлём вместе с ценой.</p>"
        kpis = "".join(
            f'<div class="kpi"><b>{esc(item["value"])} {esc(item["unit"])}</b><span>{esc(item["label"])}</span></div>'
            for item in product["kpis"]
        )
        page = head(f'{product["short"]} — официальный дилер по Республике Татарстан', product["blurb"], 2)
        page += f"""
<section class="section">
  <div class="wrap">
    <p class="crumb"><a href="../../index.html">Главная</a> / <a href="../index.html">Каталог</a> / {esc(product["categoryTitle"])}</p>
    <div class="product-layout">
      <div>
        <p class="eyebrow">{esc(product["categoryTitle"])}</p>
        <h1>{esc(product["short"])}</h1>
        <p class="lede">{esc(product["blurb"])}</p>
        <div class="stage"><img src="../../{esc(product["image"])}" alt="{esc(product["name"])}"></div>
        <p class="photo-note">Фото завода «Профессионал». <a href="{esc(product["source"])}">Карточка на сайте завода</a>.</p>
        <div class="kpi-row">{kpis}</div>
        {groups}
      </div>
      <aside class="panel" id="zayavka">
        <h2>Запросить {esc(product["short"])}</h2>
        <p>Напишите, где будет работать машина. Перезвоним и назовём цену с доставкой по Республике Татарстан.</p>
        {lead_form(products, product["short"], 2)}
      </aside>
    </div>
  </div>
</section>
"""
        page += footer(2)
        write(ROOT / "catalog" / product["slug"] / "index.html", page)

    privacy = head("Политика конфиденциальности — Альфа Машинери", "Как Альфа Машинери обрабатывает имя, телефон и отметку о куки на сайте dstprof.ru.", 1)
    privacy += """
<section class="section">
  <div class="wrap legal">
    <p class="eyebrow">Документ</p>
    <h1>Политика конфиденциальности</h1>
    <p class="lede">Сайт dstprof.ru принадлежит Альфа Машинери, официальному дилеру завода «Профессионал» по Республике Татарстан. Дата редакции: 17 ноября 2026 года.</p>
    <h2>Какие данные приходят с заявки</h2>
    <p>Если вы заполняете форму, мы получаем имя, телефон и то, что вы сами написали: модель, город или объект, комментарий. Заявка не сохраняется в базе сайта. После проверки открывается письмо на alfa-mash@bk.ru или чат WhatsApp, и текст уходит туда только если вы сами нажимаете отправку.</p>
    <h2>Зачем они нужны</h2>
    <p>Чтобы перезвонить, подобрать технику и подготовить предложение по Республике Татарстан. Других целей у этих данных нет: мы не передаём их для рекламы и не составляем из них портрет посетителя.</p>
    <h2>Два разных согласия</h2>
    <p>Заявка и счётчики — разные цели, поэтому и согласия разные. На заявку человек соглашается кнопкой «Получить предложение». На счётчики — кнопкой «Разрешить» в плашке. Текст согласия на заявку: <a href="../consent/index.html">согласие на обработку данных заявки</a>.</p>
    <h2>Куки</h2>
    <p>Аналитические и рекламные счётчики не запускаются, пока человек не нажмёт «Разрешить». Кнопка «Отказаться» оставляет сайт без счётчиков. Имя и телефон из заявки в счётчики не отправляются.</p>
    <p>Выбор хранится в вашем браузере. Изменить его можно внизу страницы, пункт «Настройки куки». Если счётчик принадлежит иностранному сервису, сведения о визите могут обрабатываться за пределами России, и только после этого разрешения.</p>
    <h2>Кому это видно</h2>
    <p>Заявку видит менеджер Альфа Машинери. Письмо уходит на alfa-mash@bk.ru. Если вы сами открываете WhatsApp, сообщение обрабатывает этот сервис. Данные о визите видит только тот счётчик, который вы разрешили.</p>
    <h2>Сколько храним</h2>
    <p>Переписку по заявке храним, пока готовим предложение и отвечаем на вопросы, либо до отзыва согласия. Если дело доходит до договора, документы хранятся столько, сколько требует учёт. Отметку о куки хранит только ваш браузер, пока вы её не сотрёте.</p>
    <h2>Ваши действия</h2>
    <p>Можно спросить, какие данные по вам есть, попросить их исправить или удалить, и отозвать согласие. Напишите на <a href="mailto:alfa-mash@bk.ru">alfa-mash@bk.ru</a> или позвоните <a href="tel:+79177562606">+7 917 756-26-06</a>, пн–пт, 9:00–18:00. Отозвать куки можно там же или через «Настройки куки».</p>
    <h2>Контакты</h2>
    <p>Альфа Машинери. Казань, Советский район, жилой массив Самосырово. Телефон +7 917 756-26-06, почта alfa-mash@bk.ru.</p>
  </div>
</section>
"""
    privacy += footer(1)
    write(ROOT / "privacy" / "index.html", privacy)

    consent = head("Согласие на обработку персональных данных — Альфа Машинери", "Отдельное согласие на обработку имени, телефона и текста заявки с сайта dstprof.ru.", 1)
    consent += """
<section class="section">
  <div class="wrap legal">
    <p class="eyebrow">Документ</p>
    <h1>Согласие на обработку персональных данных</h1>
    <p class="lede">Согласие даётся нажатием кнопки «Получить предложение» в форме заявки. Отдельная галочка не нужна. К куки и рекламным счётчикам это согласие не относится. Дата редакции: 17 ноября 2026 года.</p>
    <h2>Кто обрабатывает</h2>
    <p>Альфа Машинери, официальный дилер завода «Профессионал» по Республике Татарстан. Казань, Советский район, жилой массив Самосырово. Телефон +7 917 756-26-06, почта alfa-mash@bk.ru.</p>
    <h2>Зачем</h2>
    <p>Чтобы связаться с вами, подобрать дорожно-строительную технику и подготовить предложение по Республике Татарстан.</p>
    <h2>Какие данные</h2>
    <p>Имя, телефон, выбранная техника, город или объект и комментарий — только то, что вы сами вписали в форму.</p>
    <h2>Какие действия</h2>
    <p>Сбор, запись, хранение, использование и удаление. Передача менеджеру Альфа Машинери по почте alfa-mash@bk.ru. Если вы сами нажимаете WhatsApp, текст заявки уходит в этот сервис.</p>
    <h2>Срок</h2>
    <p>До отзыва согласия либо пока готовится предложение и идёт переписка по нему. Документы по заключённому договору хранятся столько, сколько требует учёт.</p>
    <h2>Как отозвать</h2>
    <p>Напишите на <a href="mailto:alfa-mash@bk.ru">alfa-mash@bk.ru</a> или позвоните <a href="tel:+79177562606">+7 917 756-26-06</a>. Отзыв не влияет на законность обработки до момента отзыва. Каталог можно смотреть и не оставляя заявку.</p>
    <p><a href="../privacy/index.html">Политика конфиденциальности</a></p>
  </div>
</section>
"""
    consent += footer(1)
    write(ROOT / "consent" / "index.html", consent)

    print("pages", 4 + len(products))


if __name__ == "__main__":
    main()
