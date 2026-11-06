# Как участвовать

[Українською](#українською) · [English](#english)

## Правка в браузере

1. Найдите файл. Со страницы сайта - кнопка «Предложить правку»; в репозитории - по идентификатору: процедура «Система фильтрационных лагерей» в Первой Русско-Чеченской войне - `campaigns/C1193/C1193.T0023.yml`.
2. Нажмите карандаш «Edit this file». GitHub предложит сделать копию репозитория - согласитесь.
3. Правьте текст в блоке `description:` своего языка (`ru`, `en` или `uk`). Одна фраза - одна строка, абзац - пустая строка. Отступ в два пробела перед каждой строкой блока не трогайте.
4. Внизу нажмите «Propose changes», напишите, что и почему изменили, и «Create pull request».

Поля `created`, `modified`, `version`, `campaign_name` и `technique_name` не трогайте: их ставит автоматика при принятии правки. Названия кампании и техники в файле процедуры - копии из файлов кампании и техники, чтобы было видно, о чём текст; правятся они там.

## Сноски

Каждый факт - со сноской на источник. Источник есть в архиве - поставьте его номер: `(Citation: 1068)`; номера - в `MATERIALS.md` и на https://archive.decolonial.ist. Нет - поставьте в сноску ссылку, библиографию словами или файл, остальное сделаем мы:

```
…держали до 400 человек одновременно(Citation: https://memohrc.org/ru/reports/...).
…насчитал в Пятигорске 120 задержанных(Citation: Доклад МККК о Чечне, апрель 1995).
…(Citation: sources/doklad-mkkk-1995.pdf)      # файл положите в папку sources/ в том же pull request
```

Такой pull request проверка пометит «источники на приёмке»: Архивариус заведёт карточки, выдаст номера и заменит сноски в вашей ветке. От вас больше ничего не нужно.

## Что проверяется автоматически

На каждый pull request: форма файла по схеме (`schema/`), существование всего, на что файл ссылается (техника, актор, инструмент, номер карточки в архиве), совпадение набора сносок в трёх языках. Красная проверка - текст ошибки под pull request, правьте и дополняйте тот же pull request.

Содержание проверяет человек: куратор читает правку и отвечает в pull request. Два главных правила прозы: текст читается без исторической подготовки; коротко и без украшений.

## Что не на сайте

Папка `unpublished/` повторяет раскладку базы и держит то, чего на сайте нет: без причины в файле, причина у куратора. Снять текст с сайта или вернуть - перенести файл между `campaigns/` и `unpublished/campaigns/` одним pull request. Поля «опубликовано» в файлах нет.

## Без правки

Ошибка факта, нет источника, предложение новой процедуры или материала - issue по шаблону. Чем точнее указано место (идентификатор файла, фраза) и источник, тем быстрее.

## Лицензия

Отправляя pull request, вы соглашаетесь с `LICENSE.md`: тексты CC BY-SA 4.0, код Apache-2.0.

---

## Українською

### Правка в браузері

1. Знайдіть файл. Зі сторінки сайту - кнопка «Запропонувати правку»; у репозиторії - за ідентифікатором: процедура «Система фільтраційних таборів» у Першій російсько-чеченській війні - `campaigns/C1193/C1193.T0023.yml`.
2. Натисніть олівець «Edit this file». GitHub запропонує зробити копію репозиторію - погодьтеся.
3. Правте текст у блоці `description:` своєї мови (`ru`, `en` або `uk`). Одна фраза - один рядок, абзац - порожній рядок. Відступ у два пробіли перед кожним рядком блоку не чіпайте.
4. Унизу натисніть «Propose changes», напишіть, що і чому змінили, та «Create pull request».

Поля `created`, `modified`, `version`, `campaign_name` і `technique_name` не чіпайте: їх ставить автоматика, коли правку приймають. Назви кампанії й техніки у файлі процедури - копії з файлів кампанії та техніки, щоб було видно, про що текст; правлять їх там.

### Зноски

Кожен факт - зі зноскою на джерело. Джерело є в архіві - поставте його номер: `(Citation: 1068)`; номери - у `MATERIALS.md` і на https://archive.decolonial.ist. Немає - поставте у зноску посилання, бібліографію словами або файл, решту зробимо ми:

```
…тримали до 400 людей одночасно(Citation: https://memohrc.org/ru/reports/...).
…нарахував у П'ятигорську 120 затриманих(Citation: Доповідь МКЧХ про Чечню, квітень 1995).
…(Citation: sources/dopovid-mkchh-1995.pdf)      # файл покладіть у папку sources/ у тому ж pull request
```

Такий pull request перевірка позначить «джерела на прийманні»: Архіваріус заведе картки, видасть номери та замінить зноски у вашій гілці. Від вас більше нічого не потрібно.

### Що перевіряється автоматично

На кожен pull request: форма файлу за схемою (`schema/`), існування всього, на що файл посилається (техніка, актор, інструмент, номер картки в архіві), однаковий набір зносок у трьох мовах. Червона перевірка - текст помилки під pull request, правте й доповнюйте той самий pull request.

Зміст перевіряє людина: куратор читає правку й відповідає в pull request. Два головні правила прози: текст читається без історичної підготовки; коротко й без прикрас.

### Що не на сайті

Папка `unpublished/` повторює розкладку бази й тримає те, чого на сайті немає: без причини у файлі, причина в куратора. Зняти текст із сайту або повернути - перенести файл між `campaigns/` і `unpublished/campaigns/` одним pull request. Поля «опубліковано» у файлах немає.

### Без правки

Помилка факту, немає джерела, пропозиція нової процедури чи матеріалу - issue за шаблоном. Чим точніше вказано місце (ідентифікатор файлу, фраза) та джерело, тим швидше.

### Ліцензія

Надсилаючи pull request, ви погоджуєтеся з `LICENSE.md`: тексти CC BY-SA 4.0, код Apache-2.0.

---

## English

### Editing in the browser

1. Find the file. From a page on the site - the "Suggest an edit" button; in the repository - by id: the procedure "System of Filtration Camps" in the First Russo-Chechen War is `campaigns/C1193/C1193.T0023.yml`.
2. Click the pencil "Edit this file". GitHub will offer to make a copy of the repository - accept.
3. Edit the text in the `description:` block of your language (`ru`, `en` or `uk`). One sentence per line, a blank line between paragraphs. Do not touch the two-space indentation in front of each line of the block.
4. At the bottom click "Propose changes", write what you changed and why, then "Create pull request".

Do not touch the fields `created`, `modified`, `version`, `campaign_name` and `technique_name`: automation sets them when the edit is accepted. The campaign and technique names in a procedure file are copies from the campaign and technique files, so that the reader sees what the text is about; they are edited there.

### Citations

Every fact carries a citation to a source. If the source is in the archive, use its number: `(Citation: 1068)`; the numbers are in `MATERIALS.md` and at https://archive.decolonial.ist. If it is not, put a link, a bibliography line or a file into the citation, and we do the rest:

```
…held up to 400 people at a time(Citation: https://memohrc.org/ru/reports/...).
…counted 120 detainees in Pyatigorsk(Citation: ICRC report on Chechnya, April 1995).
…(Citation: sources/icrc-report-1995.pdf)      # put the file into the sources/ folder in the same pull request
```

The check will mark such a pull request "sources pending": the archivist creates the cards, assigns the numbers and replaces the citations in your branch. Nothing more is needed from you.

### What is checked automatically

On every pull request: the file shape against the schema (`schema/`), the existence of everything the file refers to (technique, actor, tool, card number in the archive), the same set of citations in all three languages. A red check shows the error text under the pull request; fix it and add to the same pull request.

Content is reviewed by a human: the curator reads the edit and replies in the pull request. The two main rules of the prose: the text reads without any background in history; short and without ornament.

### What is not on the site

The `unpublished/` folder mirrors the layout of the base and holds what is not on the site: no reason in the file, the reason is with the curator. To take a text off the site or bring it back, move the file between `campaigns/` and `unpublished/campaigns/` in one pull request. There is no "published" field in the files.

### Without editing

A factual error, a missing source, a proposal for a new procedure or material - an issue from a template. The more precisely the place (file id, sentence) and the source are given, the faster.

### License

By submitting a pull request you agree to `LICENSE.md`: texts CC BY-SA 4.0, code Apache-2.0.
