# Основной файл миссии: облёт Муны и возврат на Кербин с посадкой
# Удалены модули посадки на Муну, добавлены этапы возврата и посадки на Кербин.

import krpc
import time
import _thread as thread
# Импортируем только нужные модули
import toLKO                    # Взлёт и выход на орбиту Кербина
import munTransfer              # Перелёт к Муне
import stageMonitor             # Автосброс ступеней

# =============================================================================
# 1. ПОДКЛЮЧЕНИЕ К ИГРЕ И ЗАПУСК МОНИТОРИНГА СТУПЕНЕЙ
# =============================================================================
connection = krpc.connect("Connection")
space_center = connection.space_center
vessel = space_center.active_vessel

args = [vessel]
thread.start_new_thread(stageMonitor.monitor, tuple(args))

# =============================================================================
# 2. ВЗЛЁТ И ВЫХОД НА ОРБИТУ КЕРБИНА
# =============================================================================
print("Этап 1: Взлёт и выход на орбиту Кербина")
toLKO.engage(vessel, space_center, connection, 0.5)

# =============================================================================
# 3. ПЕРЕЛЁТ К МУНЕ (ГОМАНОВСКАЯ ТРАЕКТОРИЯ)
# =============================================================================
print("Этап 2: Перелёт к Муне")
munTransfer.engage(vessel, space_center, connection)

# Вычисляем время до входа в сферу влияния Муны и до её перицентра
time_to_warp = vessel.orbit.next_orbit.time_to_periapsis + vessel.orbit.time_to_soi_change
space_center.warp_to(space_center.ut + time_to_warp - 300)  # Останавливаемся за 5 минут до перицентра

# =============================================================================
# 4. МАНЁВР ВОЗВРАТА (РАЗГОН В ПЕРИЦЕНТРЕ МУНЫ)
# =============================================================================
print("Этап 3: Подготовка к манёвру возврата")

# Ожидаем приближения к перицентру (осталось 10 секунд)

while vessel.orbit.time_to_periapsis > 10:
    # Используй ускорение времени, если далеко от перицентра
    if vessel.orbit.time_to_periapsis > 60:
        space_center.rails_warp_factor = 5
    else:
        space_center.rails_warp_factor = 0
    time.sleep(0.5)
space_center.rails_warp_factor = 0


# Ориентируем корабль по вектору скорости (prograde) – направление разгона
vessel.auto_pilot.engage()
vessel.auto_pilot.reference_frame = vessel.orbital_reference_frame
vessel.auto_pilot.target_direction = (0.0, 1.0, 0.0)  # Prograde
vessel.auto_pilot.wait()
print("Ориентация на prograde завершена")

# Включаем двигатель на полную тягу на фиксированное время.
# ВНИМАНИЕ: длительность импульса (burn_duration) нужно подобрать под ваш корабль!
# Она должна быть такой, чтобы после выхода из сферы Муны перицентр орбиты вокруг Кербина
# оказался в атмосфере (ниже 70 км). Рекомендуется начать с 15 секунд и корректировать.
burn_duration = 15.0
print(f"Начинаем разгон длительностью {burn_duration} секунд")
vessel.control.throttle = 1.0
time.sleep(burn_duration)
vessel.control.throttle = 0.0
vessel.auto_pilot.disengage()
print("Манёвр возврата выполнен")

# =============================================================================
# ЭТАП 4: КОРРЕКЦИЯ ТРАЕКТОРИИ ДЛЯ ВОЗВРАТА НА КЕРБИН
# =============================================================================
print("Этап 4: Возврат к Кербину")

# Ждём, пока не окажемся в сфере Кербина (после вылета из сферы Муны)
while vessel.orbit.body.name != "Kerbin":
    time.sleep(1)

print("Мы на орбите Кербина. Текущие параметры:")
print(f"Апогей: {vessel.orbit.apoapsis_altitude/1000:.1f} км, Перигей: {vessel.orbit.periapsis_altitude/1000:.1f} км")

# Если перицентр уже ниже 70 км, корабль сам войдёт в атмосферу
if vessel.orbit.periapsis_altitude < 70000:
    print("Перигей в атмосфере. Коррекция не требуется.")
else:
    print("Перигей слишком высок. Ожидаем апоцентра для корректирующего торможения...")

    # Ждём подлёта к апоцентру (до него должно остаться ~30 секунд)
    while vessel.orbit.time_to_apoapsis > 30:
        if vessel.orbit.time_to_apoapsis > 120:
            space_center.rails_warp_factor = 4   # ускоряем время вдали от апоцентра
        else:
            space_center.rails_warp_factor = 0
        time.sleep(0.5)
    space_center.rails_warp_factor = 0
    print("Подлетаем к апоцентру. Готовимся к торможению.")

    # Целевая высота перицентра (30 км, гарантированный вход в атмосферу)
    target_pe_alt = 30000
    target_pe_radius = vessel.orbit.body.equatorial_radius + target_pe_alt

    GM = vessel.orbit.body.gravitational_parameter
    r_ap = vessel.orbit.apoapsis
    a_current = vessel.orbit.semi_major_axis

    # Текущая скорость в апоцентре
    v_ap_current = (GM * (2/r_ap - 1/a_current))**0.5

    # Большая полуось целевой орбиты с тем же апоцентром
    a_target = (r_ap + target_pe_radius) / 2
    v_ap_target = (GM * (2/r_ap - 1/a_target))**0.5

    deltaV = v_ap_current - v_ap_target  # положительная, торможение
    print(f"Потребная дельта V: {deltaV:.1f} м/с")

    # Ориентация на ретроград (торможение)
    vessel.auto_pilot.engage()
    vessel.auto_pilot.reference_frame = vessel.orbital_reference_frame
    vessel.auto_pilot.target_direction = (0.0, -1.0, 0.0)  # retrograde
    vessel.auto_pilot.wait()
    print("Ориентация завершена.")

    # Выполняем импульс с контролем дельты
    vessel.control.throttle = 0.5   # половинная тяга для точности
    initial_speed = vessel.flight(vessel.orbit.body.reference_frame).speed
    achieved_dv = 0.0

    while achieved_dv < deltaV:
        time.sleep(0.1)
        current_speed = vessel.flight(vessel.orbit.body.reference_frame).speed
        achieved_dv = initial_speed - current_speed
        print(f"Набрано дельты: {achieved_dv:.1f} из {deltaV:.1f}")

    vessel.control.throttle = 0.0
    vessel.auto_pilot.disengage()
    print("Коррекция завершена.")
    print(f"Новый перигей: {vessel.orbit.periapsis_altitude/1000:.1f} км")

# Далее — ожидание входа в атмосферу и посадка
print("Ожидание входа в атмосферу...")
while vessel.orbit.periapsis_altitude > 70000:
    if vessel.orbit.time_to_periapsis > 60:
        space_center.rails_warp_factor = 4
    else:
        space_center.rails_warp_factor = 0
    time.sleep(1)
space_center.rails_warp_factor = 0

print("Вход в атмосферу. Начинаем спуск.")
# Далее ваша логика посадки (ориентация, парашюты и т.д.)

# =============================================================================
# 6. ВХОД В АТМОСФЕРУ И ПОСАДКА
# =============================================================================
print("Этап 5: Вход в атмосферу и посадка")

# Ориентируем корабль теплозащитным экраном вперёд (ретроград поверхности)
vessel.auto_pilot.engage()
vessel.auto_pilot.reference_frame = vessel.surface_velocity_reference_frame
vessel.auto_pilot.target_direction = (0.0, -1.0, 0.0)  # Ретроград
vessel.auto_pilot.wait()

# Убираем солнечные панели и антенны, чтобы они не сгорели (если есть)
vessel.control.solar_panels = False
vessel.control.antennas = False

# Ждём снижения до высоты, безопасной для раскрытия парашютов
print("Ожидание безопасной высоты для парашютов...")
while True:
    flight_info = vessel.flight()
    altitude = flight_info.mean_altitude
    speed = flight_info.speed
    if altitude < 5000 and speed < 250:  # Условия можно настроить
        print(f"Высота: {altitude:.0f} м, скорость: {speed:.0f} м/с — раскрываем парашюты")
        vessel.control.parachutes = True
        break
    time.sleep(0.5)

# Ожидание посадки
print("Парашюты раскрыты, ждём касания...")
while vessel.flight().surface_altitude > 5:
    time.sleep(1)

# Завершение миссии
vessel.control.throttle = 0.0
vessel.auto_pilot.disengage()
vessel.control.sas = True
print("=" * 50)
print("МИССИЯ УСПЕШНО ЗАВЕРШЕНА! КОРАБЛЬ ВЕРНУЛСЯ НА КЕРБИН.")
print("=" * 50)