# DECOLONIAL.IST - база знаний о российском колониализме

[Українською](#українською) · [English](#english)

База знаний о том, как Россия колонизирует народы: действия империи описаны в структуре [MITRE ATT&CK](https://attack.mitre.org), с позиции колонизированных. Сайт - https://decolonial.ist. Здесь лежат сами данные сайта: один YAML-файл на сущность, проза - Markdown внутри файла.

## Устройство

| Папка | Что внутри | Имя файла |
|---|---|---|
| `tactics/` | тактики - цели колонизатора | `TA0001.yml` |
| `techniques/` | техники и подтехники - как он действует | `T0023.yml`, `T0162.004.yml` |
| `actors/` | акторы - кто действует | `G0013.yml` |
| `tools/` | инструменты | `S0010.yml` |
| `campaigns/` | кампании - период или система политики против народа; в папке кампании её описание и процедуры | `C1193/C1193.yml` |
| `campaigns/<кампания>/` | процедуры - конкретное применение техники в кампании, главный текст базы | `C1193/C1193.T0023.yml` |
| `sources/` | файлы источников, которые ждут приёмки в архив; в `main` пуста | |
| `unpublished/` | то, чего на сайте нет, той же раскладкой; сайт и экспорт папку не читают, проверяется только форма файлов. Снять с сайта или вернуть - перенос файла одним pull request | `unpublished/campaigns/C0052/C0052.T0128.yml` |

Имя файла - только идентификатор; названия на трёх языках (`ru`, `en`, `uk`) внутри. В прозе одна фраза - одна строка, абзац - пустая строка: так правка в pull request видна по фразе. Правила прозы - в `CONTRIBUTING.md`.

Источники живут в архиве https://archive.decolonial.ist: сноска в тексте - номер карточки, `(Citation: 1068)`; список номеров - `MATERIALS.md`. Нет вашего источника - поставьте в сноску ссылку, библиографию словами или файл из `sources/`, номер выдаст Архивариус.

## Как предложить правку

1. Откройте файл на GitHub и нажмите карандаш «Edit» (или кнопку «Предложить правку» на странице сайта).
2. Исправьте текст, внизу нажмите «Propose changes»: GitHub сам создаст копию и pull request.
3. Проверки формы пройдут автоматически; содержание читает куратор и отвечает в pull request.

Заметили ошибку, но править не хотите - создайте issue по шаблону. Подробности - `CONTRIBUTING.md`.

Лицензия: тексты CC BY-SA 4.0, код Apache-2.0 - `LICENSE.md`.

---

## Українською

База знань про те, як Росія колонізує народи: дії імперії описані в структурі [MITRE ATT&CK](https://attack.mitre.org), з позиції колонізованих. Сайт - https://decolonial.ist. Тут лежать самі дані сайту: один YAML-файл на сутність, проза - Markdown усередині файлу.

### Устрій

| Папка | Що всередині | Ім'я файлу |
|---|---|---|
| `tactics/` | тактики - цілі колонізатора | `TA0001.yml` |
| `techniques/` | техніки й підтехніки - як він діє | `T0023.yml`, `T0162.004.yml` |
| `actors/` | актори - хто діє | `G0013.yml` |
| `tools/` | інструменти | `S0010.yml` |
| `campaigns/` | кампанії - період або система політики проти народу; у папці кампанії її опис і процедури | `C1193/C1193.yml` |
| `campaigns/<кампанія>/` | процедури - конкретне застосування техніки в кампанії, головний текст бази | `C1193/C1193.T0023.yml` |
| `sources/` | файли джерел, які чекають на приймання в архів; у `main` порожня | |
| `unpublished/` | те, чого на сайті немає, тією самою розкладкою; сайт і експорт папку не читають, перевіряється лише форма файлів. Зняти з сайту або повернути - перенесення файлу одним pull request | `unpublished/campaigns/C0052/C0052.T0128.yml` |

Ім'я файлу - лише ідентифікатор; назви трьома мовами (`ru`, `en`, `uk`) усередині. У прозі одна фраза - один рядок, абзац - порожній рядок: так правка в pull request видна за фразою. Правила прози - у `CONTRIBUTING.md`.

Джерела живуть в архіві https://archive.decolonial.ist: зноска в тексті - номер картки, `(Citation: 1068)`; список номерів - `MATERIALS.md`. Немає вашого джерела - поставте у зноску посилання, бібліографію словами або файл із `sources/`, номер видасть Архіваріус.

### Як запропонувати правку

1. Відкрийте файл на GitHub і натисніть олівець «Edit» (або кнопку «Запропонувати правку» на сторінці сайту).
2. Виправте текст, унизу натисніть «Propose changes»: GitHub сам створить копію та pull request.
3. Перевірки форми пройдуть автоматично; зміст читає куратор і відповідає в pull request.

Помітили помилку, але правити не хочете - створіть issue за шаблоном. Докладно - `CONTRIBUTING.md`.

Ліцензія: тексти CC BY-SA 4.0, код Apache-2.0 - `LICENSE.md`.

---

## English

A knowledge base on how Russia colonises peoples: the empire's actions described in the [MITRE ATT&CK](https://attack.mitre.org) structure, from the perspective of the colonised. Site - https://decolonial.ist. This repository holds the site's data itself: one YAML file per entity, prose as Markdown inside the file.

### Layout

| Folder | What is inside | File name |
|---|---|---|
| `tactics/` | tactics - the coloniser's goals | `TA0001.yml` |
| `techniques/` | techniques and sub-techniques - how it acts | `T0023.yml`, `T0162.004.yml` |
| `actors/` | actors - who acts | `G0013.yml` |
| `tools/` | tools | `S0010.yml` |
| `campaigns/` | campaigns - a period or a system of policy against a people; the campaign folder holds its description and its procedures | `C1193/C1193.yml` |
| `campaigns/<campaign>/` | procedures - a concrete application of a technique in a campaign, the main text of the base | `C1193/C1193.T0023.yml` |
| `sources/` | source files awaiting intake into the archive; empty in `main` | |
| `unpublished/` | what is not on the site, in the same layout; the site and the export do not read this folder, only the file shape is checked. To take off the site or bring back - move the file in one pull request | `unpublished/campaigns/C0052/C0052.T0128.yml` |

The file name is the identifier only; the names in three languages (`ru`, `en`, `uk`) are inside. In the prose, one sentence per line, a blank line between paragraphs: this way an edit in a pull request is visible sentence by sentence. The rules of the prose are in `CONTRIBUTING.md`.

Sources live in the archive https://archive.decolonial.ist: a citation in the text is a card number, `(Citation: 1068)`; the list of numbers is `MATERIALS.md`. If your source is not there, put a link, a bibliography line or a file from `sources/` into the citation; the archivist assigns the number.

### How to propose an edit

1. Open the file on GitHub and click the pencil "Edit" (or the "Suggest an edit" button on a page of the site).
2. Fix the text, click "Propose changes" at the bottom: GitHub creates the copy and the pull request for you.
3. The shape checks run automatically; the content is read by the curator, who replies in the pull request.

Spotted an error but do not want to edit - open an issue from a template. Details - `CONTRIBUTING.md`.

License: texts CC BY-SA 4.0, code Apache-2.0 - `LICENSE.md`.
