# SnappyMovement

[English](README.md) | [Русский](README_RU.md)

SnappyMovement делает движение в Borderlands 3 менее ватным и более прямым.

Персонаж быстрее набирает скорость, быстрее останавливается после отпускания движения, но максимальная скорость ходьбы и спринта остаётся штатной. То есть мод меняет именно отзывчивость управления, а не делает персонажа быстрее.

Есть три готовых профиля и Custom-режим для ручной настройки.

## Возможности

- Быстрее реагирует на начало движения.
- Меньше скользит после отпускания клавиши или стика.
- Не повышает обычную максимальную скорость ходьбы и спринта.
- Три готовых профиля: Soft, Near Instant и Instant.
- Custom-режим с отдельной настройкой разгона и торможения.
- Изменения применяются сразу, пока мод включён.
- Настройки автоматически возвращаются после респавна и смены карты.
- При отключении мод восстанавливает исходные значения движения.

## Профили

### Soft

- `MaxAcceleration`: `8000`
- `BrakingDecelerationWalking`: `10000`

Мягкое повышение отзывчивости с сохранением большей части исходного ощущения переходов.

### Near Instant

- `MaxAcceleration`: `30000`
- `BrakingDecelerationWalking`: `40000`

Профиль по умолчанию.

### Instant

- `MaxAcceleration`: `100000`
- `BrakingDecelerationWalking`: `120000`

Самый агрессивный готовый профиль.

### Custom

Ручная настройка двух слайдеров. Изменение любого слайдера автоматически переключает профиль на **Custom**.

## Настройка

Доступна через **MODS -> SnappyMovement -> Options**.

- **Profile:** Soft / Near Instant / Instant / Custom
- **Max Acceleration:** `1000-150000`, шаг `500`
- **Braking Deceleration Walking:** `1000-180000`, шаг `500`

## Требования

- Borderlands 3
- [BL3 PythonSDK / Oak Mod Manager](https://github.com/bl-sdk/oak-mod-manager/releases/latest)

Для установки и обновления SDK используйте [официальную инструкцию BL3 SDK / Oak](https://bl-sdk.github.io/oak-mod-db/).

## Установка мода

1. Установите или обновите BL3 PythonSDK / Oak по официальной инструкции выше.
2. Скачайте `SnappyMovement.sdkmod` из [GitHub Releases](https://github.com/Last1SiN/SnappyMovement/releases/latest).
3. При полностью закрытой Borderlands 3 скопируйте `.sdkmod` целиком в `Borderlands 3\sdk_mods\`. Сам `.sdkmod` распаковывать не нужно.
4. Удалите старые `No_Movement_Inertia_*.bl3hotfix`, если они остались, чтобы они не меняли те же movement properties одновременно.
5. Запустите игру, откройте **MODS -> SnappyMovement**, включите мод и выберите профиль или настройте слайдеры через **Options**.

Для обновления замените существующий `.sdkmod` новым файлом и перезапустите игру.

## Совместимость и лицензия

- Область действия: runtime movement component локального игрока.
- Кооператив: **Unknown** — сценарий, где мод установлен только у клиента, а у хоста его нет, пока не проверен.
- Мод намеренно не изменяет максимальную скорость движения, `GroundFriction`, параметры прыжка, air control или slide speed.
- Лицензия: **GPL-3.0**

## Credits

**Development:** Sol / GPT-5.6 Sol  
**Design, testing & QA:** Last1SiN

**BL3 PythonSDK / Oak Mod Manager:** создан [apple1417](https://github.com/apple1417) при участии проекта и контрибьюторов [BL-SDK](https://github.com/bl-sdk).
