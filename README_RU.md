# SnappyMovement

**Мод PythonSDK / Oak для Borderlands 3**

Текущий релиз: **v1.0**

> Готовые к установке `.sdkmod` публикуются в разделе **Releases**.  
> Файлы в репозитории являются исходниками мода.

SnappyMovement делает наземное управление в Borderlands 3 более отзывчивым, уменьшая ощущение инерции при разгоне и остановке без повышения штатной максимальной скорости персонажа.

Мод меняет только `MaxAcceleration` и `BrakingDecelerationWalking` у локального игрока. Он намеренно не меняет максимальную скорость ходьбы, максимальную скорость спринта, `GroundFriction`, параметры прыжка, air control и slide speed.

## Возможности

- Уменьшает вязкость при старте наземного движения.
- Уменьшает инерцию остановки после отпускания movement input.
- Не повышает штатные максимальные walk/sprint speed.
- Не изменяет `GroundFriction`.
- Содержит три готовых профиля и ручную настройку.
- Изменения настроек применяются сразу, пока мод включён.
- После респавна/смены карты выбранные значения автоматически применяются к новому pawn локального игрока.
- При отключении мода восстанавливаются значения movement component, сохранённые до вмешательства SnappyMovement.
- При нормальной работе мод не засоряет игровой лог; записываются только ошибки.

## Профили

### Soft

- `MaxAcceleration`: `8000`
- `BrakingDecelerationWalking`: `10000`

Более мягкое повышение отзывчивости с сохранением части исходного ощущения переходов.

### Near Instant

- `MaxAcceleration`: `30000`
- `BrakingDecelerationWalking`: `40000`

Профиль по умолчанию и исходная рекомендуемая настройка v0.2.

### Instant

- `MaxAcceleration`: `100000`
- `BrakingDecelerationWalking`: `120000`

Самый агрессивный готовый профиль.

### Custom

Ручная настройка двух слайдеров.

Изменение любого слайдера автоматически переключает профиль на **Custom**.

## Настройка

Доступна через **MODS -> SnappyMovement -> Options**.

- **Profile:** Soft / Near Instant / Instant / Custom
- **Max Acceleration:** `1000-150000`, шаг `500`
- **Braking Deceleration Walking:** `1000-180000`, шаг `500`

Выбор одного из трёх готовых профилей автоматически записывает его значения в оба слайдера.

SnappyMovement **не** изменяет `MaxWalkSpeed`, `MaxSprintSpeed` и `GroundFriction`.

## Требования

- Borderlands 3.
- [BL3 PythonSDK / Oak Mod Manager v1.11+ — актуальный стабильный релиз](https://github.com/bl-sdk/oak-mod-manager/releases/latest).
- [Официальная инструкция по установке BL3 SDK](https://bl-sdk.github.io/oak-mod-db/).

Oak Mod Manager v1.11 уже включает Mods Base 1.12, BL3 Mod Menu 1.8, Console Mod Menu 1.6, Keybinds 2.6, pyunrealsdk 1.10.0, UI Utils 1.4 и unrealsdk 3.2.0. При использовании этой или более новой совместимой версии Oak отдельно скачивать эти компоненты обычно не нужно.

## Установка

1. **Полностью закройте Borderlands 3.**
2. Если BL3 PythonSDK / Oak ещё не установлен или его нужно обновить, откройте [актуальный стабильный релиз Oak Mod Manager](https://github.com/bl-sdk/oak-mod-manager/releases/latest).
3. В разделе **Assets** скачайте именно **`bl3-sdk.zip`**, а не архивы `Source code`.
4. Найдите корневую папку Borderlands 3. В Steam: **Библиотека -> ПКМ по Borderlands 3 -> Управление -> Просмотреть локальные файлы**.
5. Распакуйте содержимое `bl3-sdk.zip` прямо в корневую папку Borderlands 3, согласившись на объединение папок/файлов и замену файлов при запросе. Полная процедура, включая Proton/Linux, находится в [официальной инструкции BL3 SDK](https://bl-sdk.github.io/oak-mod-db/).
6. Один раз запустите Borderlands 3 и убедитесь, что в главном меню появился пункт **MODS**.
7. Скачайте актуальный релиз SnappyMovement.
8. Полностью закройте игру и скопируйте `SnappyMovement.sdkmod` **не распаковывая** в:

   `Borderlands 3\sdk_mods\`

9. Удалите старые `No_Movement_Inertia_*.bl3hotfix` из папки `ohl-mods` OpenHotfixLoader, чтобы они не применяли те же movement properties одновременно с SnappyMovement.
10. Запустите/перезапустите Borderlands 3, откройте **MODS -> SnappyMovement**, включите мод и откройте **Options** для выбора профиля или ручной настройки.

Для обновления SnappyMovement замените существующий `SnappyMovement.sdkmod` новой версией и перезапустите игру.

## Совместимость и лицензия

- Персонажи: мод работает с runtime movement component локального игрока.
- Кооператив: **ClientSide**.
- Мод намеренно не изменяет `GroundFriction`, максимальную скорость движения, параметры прыжка, air control и slide speed.
- Лицензия: **GPL-3.0**

## Credits

- **Development:** Sol / GPT-5.6 Sol
- **Design, testing & QA:** Last1SiN
- **BL3 PythonSDK / Oak Mod Manager:** создан [apple1417](https://github.com/apple1417) при участии проекта и контрибьюторов [BL-SDK](https://github.com/bl-sdk).
