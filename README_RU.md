# SnappyMovement

[English](README.md) | [Русский](README_RU.md)

SnappyMovement делает движение в Borderlands 3 менее ватным и более отзывчивым, не повышая штатную максимальную скорость ходьбы и спринта.

Базовые профили разгона/торможения сохранены, а дополнительные функции движения включаются отдельно.

## Возможности

- Более быстрый разгон и торможение на земле без изменения штатной максимальной скорости.
- Три готовых профиля: Soft, Near Instant и Instant, плюс ручной Custom.
- **Air Control Override:** усиливает управление в воздухе относительно штатного `0.6`. При очень высоком Max Acceleration разница становится малозаметной.
- **Auto Sprint:** поддерживает штатный sprint intent игры.
- **Auto Sprint Walk Override:** Disabled, удержание Sprint для ходьбы или переключение ходьба/автоспринт по Sprint.
- **Sprint in All Directions:** поднимает штатный предел угла спринта до 180°, не меняя скорость спринта.
- **Remember Sprint:** восстанавливает sprint intent после цепочек прыжок/скольжение, когда Auto Sprint выключен.
- **Crouch Landing Slide:** Off, Slide on Crouch Hold или Slide on Crouch Tap.
- Значения повторно применяются после респавна/смены карты и восстанавливаются при отключении мода.

## Профили

### Soft
- `MaxAcceleration`: `8000`
- `BrakingDecelerationWalking`: `10000`

### Near Instant
- `MaxAcceleration`: `30000`
- `BrakingDecelerationWalking`: `40000`

Профиль по умолчанию.

### Instant
- `MaxAcceleration`: `100000`
- `BrakingDecelerationWalking`: `120000`

### Custom
Ручная настройка разгона и торможения. Изменение любого из этих двух слайдеров переключает профиль на **Custom**.

## Настройка

Доступна через **MODS -> SnappyMovement -> Options**.

- **Profile:** Soft / Near Instant / Instant / Custom
- **Max Acceleration:** `1000-150000`, шаг `500`
- **Braking Deceleration Walking:** `1000-180000`, шаг `500`
- **Air Control Override:** Off / On
- **Air Control:** `0.6-20.0`, шаг `0.1`
- **Remember Sprint:** Off / On
- **Auto Sprint:** Off / On
- **Auto Sprint Walk Override:** Disabled / Hold Sprint Input to Walk / Toggle Sprint Input to Walk
- **Sprint in All Directions:** Off / On
- **Crouch Landing Slide:** Off / Slide on Crouch Hold / Slide on Crouch Tap

## Требования

- Borderlands 3
- [BL3 PythonSDK / Oak Mod Manager](https://github.com/bl-sdk/oak-mod-manager/releases/latest)

Для установки и обновления SDK используйте [официальную инструкцию BL3 SDK / Oak](https://bl-sdk.github.io/oak-mod-db/).

## Установка мода

1. Установите или обновите BL3 PythonSDK / Oak по официальной инструкции.
2. Скачайте `SnappyMovement.sdkmod` из [GitHub Releases](https://github.com/Last1SiN/SnappyMovement/releases/latest).
3. При полностью закрытой Borderlands 3 скопируйте `.sdkmod` целиком в `Borderlands 3\sdk_mods\`. Распаковывать его не нужно.
4. Запустите игру, откройте **MODS -> SnappyMovement**, включите мод и настройте его через **Options**.

Для обновления замените существующий `.sdkmod` новым и перезапустите игру.

## Совместимость и поведение

- Область действия: runtime movement component локального игрока и штатные sprint/crouch intent.
- Кооператив: **Unknown** — клиентский сценарий против хоста без мода пока не проверен.
- Мод **не** записывает `Velocity`, `MaxWalkSpeed`, `MaxSprintSpeed`, `GroundFriction`, высоту/гравитацию прыжка или скорость скольжения.
- Air Control Override меняет `AirControl` только когда функция включена.
- Sprint in All Directions меняет `MaxSprintAngle` только когда функция включена.
- Лицензия: **GNU GPLv3 с [дополнительными условиями происхождения по Section 7](ADDITIONAL_TERMS.md)**.

## Credits

**Development:** Sol / GPT-5.6 Sol  
**Design, testing & QA:** Last1SiN

**BL3 PythonSDK / Oak Mod Manager:** создан [apple1417](https://github.com/apple1417) при участии проекта и контрибьюторов [BL-SDK](https://github.com/bl-sdk).
